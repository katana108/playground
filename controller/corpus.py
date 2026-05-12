from __future__ import annotations

from pathlib import Path


def load_shared_corpus(repo_root: Path) -> str:
    parts: list[str] = []

    manifest = repo_root / "docs" / "literature-packet.md"
    if manifest.exists():
        parts.append(manifest.read_text(encoding="utf-8").strip())

    materials_dir = repo_root / "docs" / "literature"
    if materials_dir.exists():
        for path in sorted(materials_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(f"# {path.name}\n\n{text}")

    return "\n\n".join(part for part in parts if part).strip()
