from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DiffHunk:
    file_path: str
    old_content: str | None
    new_content: str | None
    raw_diff: str


class DiffAnalyzer:
    _FILE_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
    _OLD_FILE = re.compile(r"^--- a/(.+)$")
    _NEW_FILE = re.compile(r"^\+\+\+ b/(.+)$")
    _DEV_NULL = "/dev/null"

    def parse_diff(self, raw_diff: str) -> list[DiffHunk]:
        """unified diff 문자열을 파싱해 파일별 DiffHunk 목록 반환."""
        hunks: list[DiffHunk] = []
        current_file: str | None = None
        current_lines: list[str] = []
        is_new_file = False
        is_deleted_file = False

        for line in raw_diff.splitlines(keepends=True):
            header_match = self._FILE_HEADER.match(line.rstrip())
            if header_match:
                if current_file is not None:
                    hunks.append(self._build_hunk(current_file, current_lines, is_new_file, is_deleted_file))
                current_file = header_match.group(2)
                current_lines = [line]
                is_new_file = False
                is_deleted_file = False
                continue

            if line.startswith("--- "):
                if self._DEV_NULL in line:
                    is_new_file = True
            elif line.startswith("+++ "):
                if self._DEV_NULL in line:
                    is_deleted_file = True

            if current_file is not None:
                current_lines.append(line)

        if current_file is not None:
            hunks.append(self._build_hunk(current_file, current_lines, is_new_file, is_deleted_file))

        return hunks

    def _build_hunk(
        self,
        file_path: str,
        lines: list[str],
        is_new_file: bool,
        is_deleted_file: bool,
    ) -> DiffHunk:
        raw = "".join(lines)
        removed = "".join(l[1:] for l in lines if l.startswith("-") and not l.startswith("---"))
        added = "".join(l[1:] for l in lines if l.startswith("+") and not l.startswith("+++"))

        old_content = None if is_new_file else removed
        new_content = None if is_deleted_file else added
        return DiffHunk(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            raw_diff=raw,
        )

    def get_affected_folders(self, hunks: list[DiffHunk]) -> set[str]:
        """변경된 파일들이 속한 폴더 경로 집합 반환 (상위 폴더 포함)."""
        folders: set[str] = set()
        for hunk in hunks:
            path = hunk.file_path
            parts = path.split("/")
            for i in range(len(parts)):
                folder = "/".join(parts[:i])
                folders.add(folder)
        return folders
