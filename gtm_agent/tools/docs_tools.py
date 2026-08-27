"""Access to the standard tagging documentation.

Two sources are exposed to the agents:

* `default_docs/` - the standard documentation shipped with the project (GA4,
  Google Ads, Floodlight, naming and folder conventions).
* `custom_docs/`  - the user's own documentation, written by the
  `default-docs-builder` skill. When a custom file covers the same relative
  path, it TAKES PRECEDENCE over the default one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from typing import Optional

from ..config import settings

_MAX_DOC_CHARS = 60_000
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._\-/ ]+$")


def _sources() -> list[tuple[str, Path]]:
    return [
        ("custom", settings.custom_docs_dir),
        ("default", settings.default_docs_dir),
    ]


def _iter_docs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*.md") if p.is_file())


def _first_heading(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#"):
                    return line.lstrip("#").strip()
    except OSError:
        pass
    return path.stem.replace("_", " ")


def _resolve(doc_path: str) -> Optional[tuple[str, Path]]:
    """Resolve a relative doc path against both sources, safely."""
    candidate = doc_path.strip().lstrip("/\\")
    if not candidate or not _SAFE_NAME.match(candidate) or ".." in candidate:
        return None
    if not candidate.lower().endswith(".md"):
        candidate += ".md"

    for source, base in _sources():
        if not base.exists():
            continue
        target = (base / candidate).resolve()
        try:
            target.relative_to(base.resolve())
        except ValueError:  # attempt to escape the base directory
            continue
        if target.is_file():
            return source, target
    return None


def list_docs() -> dict[str, Any]:
    """List the tagging documentation available for consultation.

    ALWAYS call this before creating tags or auditing a container: this
    documentation defines which events, parameters and conventions the project
    considers correct. Documents from `custom` override those from `default`.

    Returns:
        A dict with `docs` (path, title, source, size_kb) and the directories
        that were searched.
    """
    docs: list[dict[str, Any]] = []
    for source, base in _sources():
        for path in _iter_docs(base):
            docs.append(
                {
                    "path": path.relative_to(base).as_posix(),
                    "title": _first_heading(path),
                    "source": source,
                    "size_kb": round(path.stat().st_size / 1024, 1),
                }
            )

    return {
        "count": len(docs),
        "docs": docs,
        "default_docs_dir": str(settings.default_docs_dir),
        "custom_docs_dir": str(settings.custom_docs_dir),
        "precedence": "Documents with source='custom' win over 'default'.",
    }


def read_doc(doc_path: str) -> dict[str, Any]:
    """Read one document from the standard or custom documentation.

    Args:
        doc_path: relative path as returned by `list_docs`
            (e.g. "ga4/events_ecommerce.md"). The .md extension is optional.

    Returns:
        A dict with `content`, or `error` when the document does not exist.
    """
    resolved = _resolve(doc_path)
    if not resolved:
        available = [d["path"] for d in list_docs()["docs"]]
        return {
            "error": "doc_not_found",
            "message": f"Document '{doc_path}' not found.",
            "available": available,
        }

    source, path = resolved
    content = path.read_text(encoding="utf-8")
    truncated = len(content) > _MAX_DOC_CHARS
    return {
        "path": doc_path,
        "source": source,
        "truncated": truncated,
        "content": content[:_MAX_DOC_CHARS],
    }


def search_docs(query: str) -> dict[str, Any]:
    """Search the documentation for a term and return the matching lines.

    Cheaper than reading a whole document when you are after one specific
    event, parameter or tag type.

    Args:
        query: the term to look for (e.g. "purchase", "Floodlight", "awct").

    Returns:
        A dict with `matches` (path, line, excerpt).
    """
    term = query.strip().lower()
    if not term:
        return {"error": "invalid_arguments", "message": "query must not be empty."}

    matches: list[dict[str, Any]] = []
    for source, base in _sources():
        for path in _iter_docs(base):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                if term in line.lower():
                    matches.append(
                        {
                            "path": path.relative_to(base).as_posix(),
                            "source": source,
                            "line": number,
                            "excerpt": line.strip()[:300],
                        }
                    )
                    if len(matches) >= 60:
                        return {
                            "query": query,
                            "count": len(matches),
                            "truncated": True,
                            "matches": matches,
                        }

    return {
        "query": query,
        "count": len(matches),
        "truncated": False,
        "matches": matches,
    }


def save_custom_doc(
    doc_path: str, content: str, overwrite: bool = False
) -> dict[str, Any]:
    """Write a document into the user's custom documentation.

    Used by the `default-docs-builder` skill to materialize the standard
    documentation the user defines. It only ever writes inside `custom_docs/`;
    it never touches `default_docs/`.

    Args:
        doc_path: relative file path inside custom_docs
            (e.g. "ga4/client_events.md"). Subfolders are created as needed.
        content: the complete Markdown content of the document.
        overwrite: when False (default), fail if the file already exists.

    Returns:
        A dict with the absolute path that was written.
    """
    candidate = doc_path.strip().lstrip("/\\")
    if not candidate or not _SAFE_NAME.match(candidate) or ".." in candidate:
        return {
            "error": "invalid_path",
            "message": (
                "doc_path must be a simple relative path, without '..'. "
                'e.g. "ga4/client_events.md".'
            ),
        }
    if not candidate.lower().endswith(".md"):
        candidate += ".md"

    base = settings.custom_docs_dir.resolve()
    target = (base / candidate).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {"error": "invalid_path", "message": "Path escapes custom_docs."}

    if target.exists() and not overwrite:
        return {
            "error": "already_exists",
            "message": (
                f"'{candidate}' already exists. Read it with read_doc, confirm "
                "with the user, then call again with overwrite=true."
            ),
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "saved": True,
        "path": candidate,
        "absolute_path": str(target),
        "bytes": len(content.encode("utf-8")),
    }
