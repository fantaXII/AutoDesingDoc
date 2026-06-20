from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ChangedFile:
    path: str
    status: Literal["added", "modified", "deleted", "renamed"]
    old_path: str | None = None


@dataclass
class DocFile:
    path: str
    content: str
    encoding: str = "utf-8"


class VCSAdapter(ABC):
    @abstractmethod
    def get_changed_files(self, commit_hash: str) -> list[ChangedFile]:
        """커밋에서 변경된 파일 목록 반환."""
        ...

    @abstractmethod
    def get_file_content(self, file_path: str, ref: str = "HEAD") -> str:
        """특정 커밋/브랜치의 파일 내용 반환. 파일 없으면 FileNotFoundError."""
        ...

    @abstractmethod
    def list_files(self, folder: str = "", ref: str = "HEAD") -> list[str]:
        """폴더 하위의 모든 파일 경로 목록 반환 (재귀)."""
        ...

    @abstractmethod
    def commit_files(self, files: list[DocFile], message: str) -> str:
        """파일 목록을 커밋하고 커밋 SHA 반환."""
        ...

    @abstractmethod
    def file_exists(self, file_path: str, ref: str = "HEAD") -> bool:
        """파일 존재 여부 확인."""
        ...
