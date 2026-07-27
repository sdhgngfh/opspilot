from __future__ import annotations

import hashlib
import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import Settings

SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}


def _title_from_markdown(text: str, path: Path) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def _access_policy(settings: Settings) -> dict[str, dict[str, object]]:
    if not settings.access_policy_path.exists():
        return {}
    value = json.loads(settings.access_policy_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("文档访问策略必须是 JSON 对象")
    return value


def load_source_documents(
    knowledge_dir: Path,
    settings: Settings | None = None,
) -> list[Document]:
    policy = _access_policy(settings) if settings is not None else {}
    documents: list[Document] = []
    for path in sorted(knowledge_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative_source = path.relative_to(knowledge_dir).as_posix()
        source_policy = policy.get(relative_source, {})
        access_metadata = {
            "allowed_roles": source_policy.get("allowed_roles", ["*"]),
            "allowed_departments": source_policy.get(
                "allowed_departments", ["*"]
            ),
            "classification": source_policy.get("classification", "internal"),
        }
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(path)
            title = (
                str(reader.metadata.title)
                if reader.metadata and reader.metadata.title
                else path.stem
            )
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": relative_source,
                                "title": title,
                                "page": page_number,
                                **access_metadata,
                            },
                        )
                    )
        else:
            text = path.read_text(encoding="utf-8")
            if text.strip():
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": relative_source,
                            "title": _title_from_markdown(text, path),
                            "page": 1,
                            **access_metadata,
                        },
                    )
                )
    return documents


def split_documents(documents: list[Document], settings: Settings) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        seed = (
            f"{chunk.metadata['source']}:{chunk.metadata.get('page', 1)}:"
            f"{chunk.metadata.get('start_index', 0)}:{chunk.page_content}"
        )
        chunk.metadata["chunk_id"] = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return chunks


def corpus_fingerprint(knowledge_dir: Path, settings: Settings) -> str:
    digest = hashlib.sha256()
    digest.update(f"{settings.chunk_size}:{settings.chunk_overlap}".encode())
    if settings.access_policy_path.exists():
        digest.update(settings.access_policy_path.read_bytes())
    for path in sorted(knowledge_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            digest.update(path.relative_to(knowledge_dir).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()
