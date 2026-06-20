from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import yaml


@dataclass
class DocMetadata:
    last_updated: datetime
    trigger_file: str
    total_files: int
    status: Literal["active", "merging", "archived"]
    source_repo: str
    folder_path: str
    doc_version: int = 1


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


class DocWriter:
    def generate(self, metadata: DocMetadata, body: str) -> str:
        """YAML Frontmatter + 본문을 합쳐 최종 마크다운 문자열 반환."""
        fm = self._metadata_to_dict(metadata)
        frontmatter = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"---\n{frontmatter}---\n\n{body}\n"

    def update_metadata(self, existing_content: str, new_metadata: DocMetadata) -> str:
        """기존 문서의 Frontmatter만 업데이트하고 본문은 유지."""
        match = _FRONTMATTER_RE.match(existing_content)
        body = existing_content[match.end():] if match else existing_content
        fm = self._metadata_to_dict(new_metadata)
        frontmatter = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"---\n{frontmatter}---\n\n{body}"

    def parse_metadata(self, content: str) -> DocMetadata | None:
        """문서에서 YAML Frontmatter를 파싱해 DocMetadata 반환. 없으면 None."""
        if not content.startswith("---"):
            return None
        match = _FRONTMATTER_RE.match(content)
        if not match:
            return None
        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None

        if not isinstance(fm, dict):
            return None

        required = {"last_updated", "trigger_file", "total_files", "status"}
        if not required.issubset(fm.keys()):
            return None

        last_updated = fm["last_updated"]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif not isinstance(last_updated, datetime):
            return None

        return DocMetadata(
            last_updated=last_updated,
            trigger_file=str(fm["trigger_file"]),
            total_files=int(fm["total_files"]),
            status=fm["status"],
            source_repo=str(fm.get("source_repo", "")),
            folder_path=str(fm.get("folder_path", "")),
            doc_version=int(fm.get("doc_version", 1)),
        )

    def _metadata_to_dict(self, metadata: DocMetadata) -> dict:
        iso = metadata.last_updated.isoformat()
        return {
            "last_updated": iso,
            "trigger_file": metadata.trigger_file,
            "total_files": metadata.total_files,
            "status": metadata.status,
            "source_repo": metadata.source_repo,
            "folder_path": metadata.folder_path,
            "doc_version": metadata.doc_version,
        }
