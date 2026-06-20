from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath
from typing import Optional

import pathspec

from src.config_loader import FilterConfig


class FileFilter:
    def __init__(self, config: FilterConfig):
        self._config = config
        self._gitignore_spec: Optional[pathspec.PathSpec] = None
        self._exclude_extensions: frozenset[str] = frozenset(
            ext.lower() for ext in config.exclude_extensions
        )

    def load_gitignore(self, gitignore_content: str) -> None:
        """gitignore 내용을 로드해 pathspec으로 컴파일."""
        self._gitignore_spec = pathspec.PathSpec.from_lines(
            "gitignore", gitignore_content.splitlines()
        )

    def is_valid(self, file_path: str) -> bool:
        """파일이 유효한 분석 대상인지 반환."""
        path = PurePosixPath(file_path)

        # exclude_dirs: 경로 세그먼트 중 하나라도 포함되면 제외
        parts = path.parts
        for excluded_dir in self._config.exclude_dirs:
            if excluded_dir in parts:
                return False

        # exclude_extensions: 확장자 제외
        suffix = path.suffix.lower()
        if suffix in self._exclude_extensions:
            return False

        # exclude_files: glob 패턴 매치
        name = path.name
        for pattern in self._config.exclude_files:
            if fnmatch.fnmatch(name, pattern):
                return False

        # gitignore 패턴
        if self._gitignore_spec is not None and self._gitignore_spec.match_file(file_path):
            return False

        return True

    def filter_files(self, file_paths: list[str]) -> list[str]:
        """파일 목록에서 유효한 파일만 반환."""
        return [f for f in file_paths if self.is_valid(f)]
