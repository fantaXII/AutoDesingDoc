from __future__ import annotations


class DocNamer:
    _SUFFIX = "_design.md"
    _SEP = "__"  # repo_name과 folder_path 사이 구분자 (단일 _ 보다 repo이름 충돌 방지)

    @staticmethod
    def to_doc_name(repo_name: str, folder_path: str) -> str:
        """
        폴더 경로를 문서 파일명으로 변환.

        repo_name과 folder 구분자로 __ (이중 언더스코어) 사용.
        폴더 내부 / 구분자는 _ (단일 언더스코어) 사용.

        Examples:
          to_doc_name("my-backend", "src/api/users") → "my-backend__src_api_users_design.md"
          to_doc_name("my_backend", "src/api")       → "my_backend__src_api_design.md"
          to_doc_name("my-backend", "")              → "my-backend__root_design.md"

        Note: 폴더명에 언더스코어가 포함된 경우(예: api_v2) from_doc_name 복원이 부정확할 수 있음.
        """
        normalized = folder_path.strip("/").replace("/", "_") if folder_path else "root"
        return f"{repo_name}{DocNamer._SEP}{normalized}{DocNamer._SUFFIX}"

    @staticmethod
    def to_docs_path(repo_name: str, folder_path: str, docs_prefix: str = "docs/") -> str:
        """docs 레포 내 전체 경로 반환."""
        return docs_prefix + DocNamer.to_doc_name(repo_name, folder_path)

    @staticmethod
    def from_doc_name(doc_name: str) -> tuple[str, str]:
        """
        문서 파일명에서 (repo_name, folder_path) 복원.

        Example: "my-backend__src_api_users_design.md" → ("my-backend", "src/api/users")
                 "my_backend__src_api_design.md"        → ("my_backend", "src/api")

        규칙: 첫 번째 __ (이중 언더스코어) 이전이 repo_name,
              이후가 folder_path (단일 _ → / 로 변환).

        Note: 폴더명에 언더스코어가 있으면(예: src/api_v2 → src/api/v2) 복원이 부정확.
              실행 경로에서는 이 메서드 대신 FolderAction.child_folder_paths를 사용할 것.
        """
        name = doc_name.removesuffix("_design.md")
        sep_idx = name.find(DocNamer._SEP)
        if sep_idx == -1:
            return name, ""
        repo_name = name[:sep_idx]
        folder_part = name[sep_idx + len(DocNamer._SEP):]
        if folder_part == "root":
            folder_path = ""
        else:
            folder_path = folder_part.replace("_", "/")
        return repo_name, folder_path
