from __future__ import annotations

from pathlib import Path

from .models import MetadataContext


def load_template(template_path: Path) -> str:
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "{title}\n\n{body}\n"


def compile_description(template: str, metadata: MetadataContext, title: str, body: str) -> str:
    keyword_block = "\n".join(f"- {keyword}" for keyword in metadata.keywords)
    values = {
        "title": title,
        "body": body,
        "artists": ", ".join(metadata.artists),
        "keywords": keyword_block,
        "summary": metadata.summary,
        "bpm": f"{metadata.bpm:.2f}" if metadata.bpm is not None else "",
        "key": metadata.key or "",
    }
    return template.format(**values).strip()
