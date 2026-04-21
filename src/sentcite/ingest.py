"""Ingest: upload PDFs to Blob, invoke Document Intelligence Layout, persist parsed artifacts.

Auth: Entra ID via :class:`DefaultAzureCredential` on all three calls
(Blob, Document Intelligence). Caller needs:

* ``Storage Blob Data Contributor`` on the storage account.
* ``Cognitive Services User`` on the Document Intelligence account.

Outputs per document, under ``data/parsed/<document_id>/``:

* ``layout.json`` — raw DI ``AnalyzeResult`` serialized (pages, paragraphs,
  tables, spans, polygons). Downstream chunking uses the paragraph spans
  + page numbers to produce Sentence records.
* ``document.md`` — DI's Markdown rendering. Handy for humans reviewing
  ground-truth generation and for retrieval prompts that want a
  heading-aware view of the source.
* ``meta.json`` — our normalized record (document_id, filename, blob_url,
  sha256, page_count, parsed_at, di_api_version).

Idempotent: if a parsed artifact set exists on disk, :func:`parse_pdf`
skips unless ``force=True``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .config import AzureConfig

_CREDENTIAL: TokenCredential | None = None


def _credential() -> TokenCredential:
    global _CREDENTIAL
    if _CREDENTIAL is None:
        _CREDENTIAL = DefaultAzureCredential()
    return _CREDENTIAL


@dataclass(frozen=True)
class UploadedDoc:
    document_id: str
    filename: str
    blob_url: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ParsedDoc:
    document_id: str
    filename: str
    blob_url: str
    sha256: str
    page_count: int
    parsed_at: str
    layout_json_path: str
    markdown_path: str
    meta_json_path: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _blob_service(cfg: AzureConfig) -> BlobServiceClient:
    if not cfg.storage_account:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT is required for ingest.")
    return BlobServiceClient(
        account_url=f"https://{cfg.storage_account}.blob.core.windows.net",
        credential=_credential(),
    )


def _ensure_container(svc: BlobServiceClient, name: str) -> None:
    c = svc.get_container_client(name)
    try:
        c.create_container()
    except Exception:  # noqa: BLE001
        # Already exists (or we don't have create rights — upload will fail loudly).
        pass


def upload_corpus(
    pdfs: Iterable[tuple[str, Path]],
    *,
    cfg: AzureConfig | None = None,
    overwrite: bool = False,
) -> list[UploadedDoc]:
    """Upload ``(document_id, pdf_path)`` pairs to the raw container.

    Deterministic blob names: ``<document_id>.pdf``. Returns one
    :class:`UploadedDoc` per input. Safe to re-run — existing blobs are
    skipped unless ``overwrite=True``.
    """
    cfg = cfg or AzureConfig.from_env()
    svc = _blob_service(cfg)
    _ensure_container(svc, cfg.storage_container_raw)
    container = svc.get_container_client(cfg.storage_container_raw)

    uploaded: list[UploadedDoc] = []
    for document_id, pdf_path in pdfs:
        pdf_path = Path(pdf_path)
        if not pdf_path.is_file():
            raise FileNotFoundError(pdf_path)
        blob_name = f"{document_id}.pdf"
        blob = container.get_blob_client(blob_name)
        size = pdf_path.stat().st_size
        sha = _sha256(pdf_path)
        if blob.exists() and not overwrite:
            pass
        else:
            with pdf_path.open("rb") as f:
                blob.upload_blob(
                    f,
                    overwrite=True,
                    metadata={"document_id": document_id, "sha256": sha},
                )
        uploaded.append(
            UploadedDoc(
                document_id=document_id,
                filename=pdf_path.name,
                blob_url=blob.url,
                size_bytes=size,
                sha256=sha,
            )
        )
    return uploaded


def _docintel_client(cfg: AzureConfig) -> DocumentIntelligenceClient:
    if not cfg.docintel_endpoint:
        raise RuntimeError("AZURE_DOCINTEL_ENDPOINT is required for ingest.")
    return DocumentIntelligenceClient(
        endpoint=cfg.docintel_endpoint.rstrip("/"),
        credential=_credential(),
    )


def parse_pdf(
    pdf_path: Path,
    out_dir: Path,
    *,
    document_id: str,
    blob_url: str | None = None,
    cfg: AzureConfig | None = None,
    force: bool = False,
) -> ParsedDoc:
    """Run Document Intelligence Layout over ``pdf_path``; persist artifacts.

    The PDF is sent as raw bytes (``bytes_source``), so DI does not need
    blob read permissions — this keeps the auth story simple and avoids
    SAS URL generation.
    """
    cfg = cfg or AzureConfig.from_env()
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir) / document_id
    out_dir.mkdir(parents=True, exist_ok=True)
    layout_json = out_dir / "layout.json"
    markdown_path = out_dir / "document.md"
    meta_json = out_dir / "meta.json"

    if layout_json.exists() and markdown_path.exists() and meta_json.exists() and not force:
        meta = json.loads(meta_json.read_text())
        return ParsedDoc(
            document_id=document_id,
            filename=meta["filename"],
            blob_url=meta.get("blob_url", ""),
            sha256=meta["sha256"],
            page_count=meta["page_count"],
            parsed_at=meta["parsed_at"],
            layout_json_path=str(layout_json),
            markdown_path=str(markdown_path),
            meta_json_path=str(meta_json),
        )

    data = pdf_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    client = _docintel_client(cfg)
    poller = client.begin_analyze_document(
        "prebuilt-layout",
        AnalyzeDocumentRequest(bytes_source=data),
        output_content_format=DocumentContentFormat.MARKDOWN,
    )
    result = poller.result()
    result_dict = result.as_dict()

    layout_json.write_text(json.dumps(result_dict, ensure_ascii=False))
    markdown_path.write_text(result_dict.get("content", ""))

    page_count = len(result_dict.get("pages", []))
    parsed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = {
        "document_id": document_id,
        "filename": pdf_path.name,
        "blob_url": blob_url or "",
        "sha256": sha,
        "page_count": page_count,
        "parsed_at": parsed_at,
        "di_api_version": result_dict.get("apiVersion") or result_dict.get("api_version", ""),
        "di_model_id": result_dict.get("modelId") or result_dict.get("model_id", ""),
    }
    meta_json.write_text(json.dumps(meta, indent=2))

    return ParsedDoc(
        document_id=document_id,
        filename=pdf_path.name,
        blob_url=blob_url or "",
        sha256=sha,
        page_count=page_count,
        parsed_at=parsed_at,
        layout_json_path=str(layout_json),
        markdown_path=str(markdown_path),
        meta_json_path=str(meta_json),
    )


def ingest_and_parse(
    pdfs: Iterable[tuple[str, Path]],
    *,
    parsed_dir: Path,
    cfg: AzureConfig | None = None,
    force: bool = False,
    overwrite_blob: bool = False,
) -> list[ParsedDoc]:
    """Upload then parse every ``(document_id, pdf_path)`` pair.

    Returns one :class:`ParsedDoc` per input. Designed to be re-runnable;
    uploads are skipped if the blob exists and parsing is skipped if the
    artifact set exists on disk (both overridable with the flags).
    """
    cfg = cfg or AzureConfig.from_env()
    pdfs = list(pdfs)
    uploaded = upload_corpus(pdfs, cfg=cfg, overwrite=overwrite_blob)
    uploaded_by_id = {u.document_id: u for u in uploaded}
    out: list[ParsedDoc] = []
    for document_id, pdf_path in pdfs:
        u = uploaded_by_id[document_id]
        out.append(
            parse_pdf(
                pdf_path,
                parsed_dir,
                document_id=document_id,
                blob_url=u.blob_url,
                cfg=cfg,
                force=force,
            )
        )
    return out


def uploaded_to_dict(u: UploadedDoc) -> dict:
    return asdict(u)


def parsed_to_dict(p: ParsedDoc) -> dict:
    return asdict(p)
