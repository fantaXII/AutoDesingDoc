from __future__ import annotations

import subprocess
from .base import ChangedFile, DocFile, VCSAdapter


class PerforceAdapter(VCSAdapter):
    """P4 CLI를 subprocess로 래핑한 Perforce 구현체 (stub)."""

    def __init__(self, server: str, depot: str, client: str, password: str):
        self._server = server
        self._depot = depot
        self._client = client
        self._env = {"P4PORT": server, "P4CLIENT": client, "P4PASSWD": password}

    def _p4(self, *args: str) -> str:
        result = subprocess.run(
            ["p4", *args],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, **self._env},
        )
        if result.returncode != 0:
            raise RuntimeError(f"p4 command failed: {result.stderr}")
        return result.stdout

    def get_changed_files(self, commit_hash: str) -> list[ChangedFile]:
        output = self._p4("describe", "-s", commit_hash)
        files: list[ChangedFile] = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("... //"):
                parts = line.split()
                depot_path = parts[1]
                action = parts[2] if len(parts) > 2 else "edit"
                local_path = depot_path.replace(self._depot, "").lstrip("/")
                status_map = {"add": "added", "edit": "modified", "delete": "deleted", "move/add": "renamed"}
                status = status_map.get(action, "modified")
                files.append(ChangedFile(path=local_path, status=status))
        return files

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> str:
        depot_path = f"{self._depot}/{file_path}"
        if ref != "HEAD":
            depot_path = f"{depot_path}@{ref}"
        return self._p4("print", "-q", depot_path)

    def list_files(self, folder: str = "", ref: str = "HEAD") -> list[str]:
        depot_path = f"{self._depot}/{folder}/..." if folder else f"{self._depot}/..."
        output = self._p4("files", depot_path)
        files = []
        for line in output.splitlines():
            if "#" in line:
                depot_file = line.split("#")[0].strip()
                local = depot_file.replace(self._depot, "").lstrip("/")
                if "delete" not in line:
                    files.append(local)
        return files

    def commit_files(self, files: list[DocFile], message: str) -> str:
        raise NotImplementedError("Perforce commit_files not implemented — use p4 submit workflow")

    def file_exists(self, file_path: str, ref: str = "HEAD") -> bool:
        try:
            self.get_file_content(file_path, ref)
            return True
        except RuntimeError:
            return False
