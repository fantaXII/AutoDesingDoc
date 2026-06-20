from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.llm.base import FileSummary, LLMClient

logger = logging.getLogger(__name__)


class FileMapper:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    def map_file(self, file_path: str, content: str, folder_context: str = "") -> FileSummary:
        """단일 파일 요약."""
        return self._llm.summarize_file(file_path, content, folder_context)

    def map_files(
        self,
        files: dict[str, str],
        folder_context: str = "",
        max_workers: int = 5,
    ) -> list[FileSummary]:
        """여러 파일을 병렬로 요약. 실패한 파일은 빈 요약으로 대체."""
        summaries: dict[str, FileSummary] = {}

        def _summarize(file_path: str, content: str) -> tuple[str, FileSummary]:
            try:
                summary = self._llm.summarize_file(file_path, content, folder_context)
            except Exception as e:
                logger.warning("Failed to summarize %s: %s", file_path, e)
                summary = FileSummary(
                    file_path=file_path,
                    purpose="요약 실패",
                    key_concepts=[],
                    dependencies=[],
                )
            return file_path, summary

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_summarize, path, content): path
                for path, content in files.items()
            }
            for future in as_completed(futures):
                path, summary = future.result()
                summaries[path] = summary

        # 입력 순서 유지
        return [summaries[p] for p in files if p in summaries]
