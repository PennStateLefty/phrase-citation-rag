"""Structural tests for sentcite.ingest (no Azure calls)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentcite.ingest import parse_pdf, upload_corpus


def _make_cfg(tmp_path: Path):
    from sentcite.config import AzureConfig

    return AzureConfig(
        storage_account="stg",
        storage_container_raw="raw-pdfs",
        storage_container_parsed="parsed",
        storage_connection_string="",
        docintel_endpoint="https://di.example.com/",
        docintel_key="",
        search_endpoint="",
        search_api_key="",
        search_index_chunks="c",
        search_index_sentences="s",
        foundry_name="",
        foundry_endpoint="",
        foundry_api_key="",
        foundry_project_name="",
        foundry_project_endpoint="",
        openai_api_version="",
        openai_chat_deployment="gpt-4.1",
        openai_embedding_deployment="",
        synth_gt_endpoint="https://synth",
        synth_gt_api_key="",
        synth_gt_deployment="",
        synth_gt_model="mistral",
        judge_endpoint="https://judge",
        judge_api_key="",
        judge_deployment="",
        judge_model="llama",
    )


def test_upload_corpus_uses_deterministic_blob_names(tmp_path, monkeypatch):
    pdf = tmp_path / "p587.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake\n")
    cfg = _make_cfg(tmp_path)

    fake_blob = MagicMock()
    fake_blob.exists.return_value = False
    fake_blob.url = "https://stg.blob.core.windows.net/raw-pdfs/irs_pub_587.pdf"
    fake_container = MagicMock()
    fake_container.get_blob_client.return_value = fake_blob
    fake_svc = MagicMock()
    fake_svc.get_container_client.return_value = fake_container

    with patch("sentcite.ingest._blob_service", return_value=fake_svc):
        out = upload_corpus([("irs_pub_587", pdf)], cfg=cfg)

    fake_container.get_blob_client.assert_called_with("irs_pub_587.pdf")
    fake_blob.upload_blob.assert_called_once()
    assert out[0].document_id == "irs_pub_587"
    assert out[0].sha256 == hashlib.sha256(b"%PDF-1.4 fake\n").hexdigest()


def test_upload_corpus_skips_existing_blob_when_not_overwriting(tmp_path):
    pdf = tmp_path / "p587.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake\n")
    cfg = _make_cfg(tmp_path)

    fake_blob = MagicMock()
    fake_blob.exists.return_value = True
    fake_container = MagicMock()
    fake_container.get_blob_client.return_value = fake_blob
    fake_svc = MagicMock()
    fake_svc.get_container_client.return_value = fake_container

    with patch("sentcite.ingest._blob_service", return_value=fake_svc):
        upload_corpus([("irs_pub_587", pdf)], cfg=cfg, overwrite=False)

    fake_blob.upload_blob.assert_not_called()


def test_parse_pdf_is_idempotent_when_artifacts_exist(tmp_path):
    pdf = tmp_path / "p587.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake\n")
    parsed_dir = tmp_path / "parsed"
    out_dir = parsed_dir / "irs_pub_587"
    out_dir.mkdir(parents=True)
    (out_dir / "layout.json").write_text("{}")
    (out_dir / "document.md").write_text("# hi\n")
    (out_dir / "meta.json").write_text(json.dumps({
        "document_id": "irs_pub_587",
        "filename": "p587.pdf",
        "blob_url": "",
        "sha256": "abc",
        "page_count": 10,
        "parsed_at": "2026-01-01T00:00:00+00:00",
    }))

    cfg = _make_cfg(tmp_path)
    with patch("sentcite.ingest._docintel_client") as di:
        r = parse_pdf(pdf, parsed_dir, document_id="irs_pub_587", cfg=cfg)

    di.assert_not_called()
    assert r.page_count == 10
    assert r.sha256 == "abc"


def test_parse_pdf_calls_layout_and_writes_artifacts(tmp_path):
    pdf = tmp_path / "p587.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake\n")
    cfg = _make_cfg(tmp_path)

    fake_result = MagicMock()
    fake_result.as_dict.return_value = {
        "content": "# Heading\n\nBody sentence.",
        "pages": [{"pageNumber": 1}, {"pageNumber": 2}],
        "apiVersion": "2024-11-30",
        "modelId": "prebuilt-layout",
    }
    fake_poller = MagicMock()
    fake_poller.result.return_value = fake_result
    fake_client = MagicMock()
    fake_client.begin_analyze_document.return_value = fake_poller

    with patch("sentcite.ingest._docintel_client", return_value=fake_client):
        r = parse_pdf(pdf, tmp_path / "parsed", document_id="irs_pub_587", cfg=cfg)

    assert r.page_count == 2
    assert Path(r.markdown_path).read_text().startswith("# Heading")
    meta = json.loads(Path(r.meta_json_path).read_text())
    assert meta["di_api_version"] == "2024-11-30"
    assert meta["di_model_id"] == "prebuilt-layout"
    fake_client.begin_analyze_document.assert_called_once()
