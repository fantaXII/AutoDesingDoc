from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FileSummary:
    file_path: str
    purpose: str
    key_concepts: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class LLMClient(ABC):
    @abstractmethod
    def summarize_file(
        self,
        file_path: str,
        content: str,
        folder_context: str = "",
    ) -> FileSummary:
        """단일 파일 요약. 소스 코드 블록 포함 금지."""
        ...

    @abstractmethod
    def synthesize_folder(
        self,
        folder_path: str,
        summaries: list[FileSummary],
        child_doc_summaries: dict[str, str],
    ) -> str:
        """폴더 단위 디자인 문서 본문 생성. 소스 코드 블록 포함 금지."""
        ...

    @abstractmethod
    def merge_into_parent(
        self,
        orphan_doc_content: str,
        parent_doc_content: str,
        folder_path: str,
    ) -> str:
        """삭제될 문서의 핵심 내용을 부모 문서에 병합한 새 부모 문서 본문 반환."""
        ...
