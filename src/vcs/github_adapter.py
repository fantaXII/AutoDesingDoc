from __future__ import annotations

import base64
from typing import Any

from github import Github, GithubException
from github.Repository import Repository as GHRepo

from .base import ChangedFile, DocFile, VCSAdapter


class GitHubAdapter(VCSAdapter):
    def __init__(self, repo_full_name: str, token: str, branch: str = ""):
        self._gh = Github(token)
        self._repo: GHRepo = self._gh.get_repo(repo_full_name)
        self._branch = branch or self._repo.default_branch

    def get_changed_files(self, commit_hash: str) -> list[ChangedFile]:
        commit = self._repo.get_commit(commit_hash)
        result: list[ChangedFile] = []
        for f in commit.files:
            status = f.status
            if status == "renamed":
                result.append(ChangedFile(path=f.filename, status="renamed", old_path=f.previous_filename))
            elif status in ("added", "modified", "deleted"):
                result.append(ChangedFile(path=f.filename, status=status))
            else:
                result.append(ChangedFile(path=f.filename, status="modified"))
        return result

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> str:
        try:
            content_file = self._repo.get_contents(file_path, ref=ref)
            if isinstance(content_file, list):
                raise FileNotFoundError(f"Path is a directory: {file_path}")
            return base64.b64decode(content_file.content).decode("utf-8", errors="replace")
        except GithubException as e:
            if e.status == 404:
                raise FileNotFoundError(f"File not found: {file_path} @ {ref}") from e
            raise

    def list_files(self, folder: str = "", ref: str = "HEAD") -> list[str]:
        sha = ref if ref != "HEAD" else self._repo.get_branch(self._branch).commit.sha
        tree = self._repo.get_git_tree(sha, recursive=True)
        prefix = folder.rstrip("/") + "/" if folder else ""
        return [
            item.path
            for item in tree.tree
            if item.type == "blob" and (not prefix or item.path.startswith(prefix))
        ]

    def commit_files(self, files: list[DocFile], message: str, max_retries: int = 3) -> str:
        """Git Data API를 사용해 여러 파일을 단일 커밋으로 묶어 저장.

        동시 푸시로 non-fast-forward 충돌 시 최대 max_retries 회 재시도.
        """
        for attempt in range(max_retries):
            try:
                ref_obj = self._repo.get_git_ref(f"heads/{self._branch}")
                base_commit_sha = ref_obj.object.sha
                base_tree = self._repo.get_git_commit(base_commit_sha).tree

                blobs = []
                for doc_file in files:
                    if doc_file.content == "":
                        blobs.append(
                            {"path": doc_file.path, "mode": "100644", "type": "blob", "sha": None}
                        )
                    else:
                        blob = self._repo.create_git_blob(doc_file.content, "utf-8")
                        blobs.append(
                            {"path": doc_file.path, "mode": "100644", "type": "blob", "sha": blob.sha}
                        )

                new_tree = self._repo.create_git_tree(blobs, base_tree)
                new_commit = self._repo.create_git_commit(
                    message, new_tree, [self._repo.get_git_commit(base_commit_sha)]
                )
                ref_obj.edit(new_commit.sha)
                return new_commit.sha
            except GithubException as e:
                if attempt < max_retries - 1 and e.status in (409, 422):
                    continue
                raise
        raise RuntimeError("commit_files: 재시도 횟수 초과")

    def file_exists(self, file_path: str, ref: str = "HEAD") -> bool:
        try:
            self._repo.get_contents(file_path, ref=ref)
            return True
        except GithubException as e:
            if e.status == 404:
                return False
            raise
