from __future__ import annotations

from src.llm.base import FileSummary, LLMClient


class FolderReducer:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    def reduce(
        self,
        folder_path: str,
        summaries: list[FileSummary],
        child_doc_summaries: dict[str, str] | None = None,
    ) -> str:
        """FileSummary 목록을 폴더 단위 디자인 문서 본문으로 합성."""
        return self._llm.synthesize_folder(
            folder_path=folder_path,
            summaries=summaries,
            child_doc_summaries=child_doc_summaries or {},
        )
