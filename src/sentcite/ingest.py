"""Ingest: upload PDFs to Blob and invoke Azure AI Document Intelligence.

Implementation pending — this module will be filled in during the
`ingest-parse` todo. Signatures here are the contract the notebook will
consume.
"""

from __future__ import annotations

from pathlib import Path


def upload_corpus(pdf_dir: Path) -> list[str]:
    """Upload every PDF under pdf_dir to the raw container. Returns blob URIs."""
    raise NotImplementedError


def parse_pdf(blob_uri: str, out_dir: Path) -> Path:
    """Invoke Document Intelligence Layout API on a blob; persist JSON+Markdown.

    Returns the path to the parsed JSON artifact.
    """
    raise NotImplementedError
