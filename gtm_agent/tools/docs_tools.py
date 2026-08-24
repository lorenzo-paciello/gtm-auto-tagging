"""Ferramentas de acesso a documentacao padrao de tagueamento.

Duas fontes sao expostas aos agentes:

* `default_docs/`  - documentacao padrao versionada com o projeto (GA4, Google
  Ads, Floodlight, convencoes de nomenclatura e pastas).
* `custom_docs/`   - documentacao do usuario, criada pela skill
  `default-docs-builder`. Quando um arquivo custom trata do mesmo assunto, ele
  tem PRECEDENCIA sobre o padrao.
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
    return [("custom", settings.custom_docs_dir), ("default", settings.default_docs_dir)]


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
    """Resolve um caminho relativo de doc contra as duas fontes, com seguranca."""
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
        except ValueError:  # tentativa de sair do diretorio base
            continue
        if target.is_file():
            return source, target
    return None


def list_docs() -> dict[str, Any]:
    """Lista a documentacao de tagueamento disponivel para consulta.

    Chame SEMPRE antes de criar tags ou auditar o container: e essa
    documentacao que define eventos, parametros e convencoes que o projeto
    considera corretos. Documentos em `custom` sobrepoem os `default`.

    Returns:
        Dicionario com `docs` (path, title, source, size_kb) e os diretorios
        consultados.
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
        "precedence": "Documentos com source='custom' prevalecem sobre 'default'.",
    }


def read_doc(doc_path: str) -> dict[str, Any]:
    """Le um documento da documentacao padrao ou customizada.

    Args:
        doc_path: caminho relativo retornado por `list_docs`
            (ex.: "ga4/events_ecommerce.md"). A extensao .md e opcional.

    Returns:
        Dicionario com `content`, ou `error` se o documento nao existir.
    """
    resolved = _resolve(doc_path)
    if not resolved:
        available = [d["path"] for d in list_docs()["docs"]]
        return {
            "error": "doc_not_found",
            "message": f"Documento '{doc_path}' nao encontrado.",
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
    """Busca um termo na documentacao e devolve os trechos correspondentes.

    Mais economico que ler um documento inteiro quando voce procura por um
    evento, parametro ou tipo de tag especifico.

    Args:
        query: termo a procurar (ex.: "purchase", "Floodlight", "awct").

    Returns:
        Dicionario com `matches` (path, line, excerpt).
    """
    term = query.strip().lower()
    if not term:
        return {"error": "invalid_arguments", "message": "query nao pode ser vazio."}

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

    return {"query": query, "count": len(matches), "truncated": False, "matches": matches}


def save_custom_doc(doc_path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
    """Grava um documento na documentacao customizada do usuario.

    Ferramenta usada pela skill `default-docs-builder` para materializar a
    documentacao padrao que o usuario definir. Escreve apenas dentro de
    `custom_docs/`; nunca altera `default_docs/`.

    Args:
        doc_path: caminho relativo do arquivo dentro de custom_docs
            (ex.: "ga4/eventos_do_cliente.md"). Subpastas sao criadas.
        content: conteudo Markdown completo do documento.
        overwrite: quando False (padrao), falha se o arquivo ja existir.

    Returns:
        Dicionario com o caminho absoluto gravado.
    """
    candidate = doc_path.strip().lstrip("/\\")
    if not candidate or not _SAFE_NAME.match(candidate) or ".." in candidate:
        return {
            "error": "invalid_path",
            "message": (
                "doc_path deve ser um caminho relativo simples, sem '..'. "
                'Ex.: "ga4/eventos_do_cliente.md".'
            ),
        }
    if not candidate.lower().endswith(".md"):
        candidate += ".md"

    base = settings.custom_docs_dir.resolve()
    target = (base / candidate).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {"error": "invalid_path", "message": "Caminho fora de custom_docs."}

    if target.exists() and not overwrite:
        return {
            "error": "already_exists",
            "message": (
                f"'{candidate}' ja existe. Leia com read_doc e confirme com o "
                "usuario antes de chamar novamente com overwrite=true."
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
