from __future__ import annotations

from src.llm.base import LLMClient
from .doc_writer import DocWriter, DocMetadata


class MergeHandler:
    def __init__(self, llm_client: LLMClient, doc_writer: DocWriter):
        self._llm = llm_client
        self._writer = doc_writer

    def merge_into_parent(
        self,
        orphan_doc_content: str,
        parent_doc_content: str,
        orphan_folder_path: str,
        new_metadata: DocMetadata,
    ) -> str:
        """
        삭제될 문서의 핵심 내용을 부모 문서에 병합한 완전한 문서 반환.
        LLM으로 병합 후 메타데이터를 갱신한다.
        """
        merged_body = self._llm.merge_into_parent(
            orphan_doc_content=orphan_doc_content,
            parent_doc_content=parent_doc_content,
            folder_path=orphan_folder_path,
        )
        return self._writer.update_metadata(
            existing_content=f"---\n---\n\n{merged_body}",
            new_metadata=new_metadata,
        )
