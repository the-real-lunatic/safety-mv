from __future__ import annotations

from pathlib import Path

from .pipeline import PipelineError


def read_pdf_texts(pdf_paths: list[str]) -> list[str]:
    if not pdf_paths:
        return []

    import logging

    log = logging.getLogger("safetymv.pdf")

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - import guard
        raise PipelineError("pypdf is required to read PDF files") from exc

    texts: list[str] = []
    for path_str in pdf_paths:
        path = Path(path_str)
        if not path.exists():
            raise PipelineError(f"pdf not found: {path}")
        reader = PdfReader(str(path))
        content_parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            content_parts.append(page_text)
        texts.append("\n".join(content_parts))
        log.info("pdf parsed", extra={"path": str(path), "chars": len(texts[-1])})
    return texts
