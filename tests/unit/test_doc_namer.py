import pytest
from src.document.doc_namer import DocNamer


class TestDocNamer:
    def test_nested_folder(self):
        assert DocNamer.to_doc_name("my-backend", "src/api/users") == "my-backend__src_api_users_design.md"

    def test_root_folder(self):
        assert DocNamer.to_doc_name("my-backend", "") == "my-backend__root_design.md"

    def test_single_level_folder(self):
        assert DocNamer.to_doc_name("game-engine", "engine") == "game-engine__engine_design.md"

    def test_docs_path_prefix(self):
        result = DocNamer.to_docs_path("my-backend", "src/api")
        assert result == "docs/my-backend__src_api_design.md"

    def test_docs_path_custom_prefix(self):
        result = DocNamer.to_docs_path("my-backend", "src/api", docs_prefix="output/")
        assert result == "output/my-backend__src_api_design.md"

    def test_roundtrip_nested(self):
        repo, folder = "my-backend", "src/api/users"
        doc_name = DocNamer.to_doc_name(repo, folder)
        restored_repo, restored_folder = DocNamer.from_doc_name(doc_name)
        assert restored_repo == repo
        assert restored_folder == folder

    def test_roundtrip_root(self):
        repo, folder = "my-backend", ""
        doc_name = DocNamer.to_doc_name(repo, folder)
        restored_repo, restored_folder = DocNamer.from_doc_name(doc_name)
        assert restored_repo == repo
        assert restored_folder == folder

    def test_roundtrip_underscore_repo_name(self):
        """언더스코어 포함 repo 이름도 올바르게 복원되어야 한다."""
        repo, folder = "my_backend", "src/api"
        doc_name = DocNamer.to_doc_name(repo, folder)
        restored_repo, restored_folder = DocNamer.from_doc_name(doc_name)
        assert restored_repo == repo
        assert restored_folder == folder

    def test_trailing_slash_stripped(self):
        result = DocNamer.to_doc_name("repo", "src/api/")
        assert result == "repo__src_api_design.md"

    def test_leading_slash_stripped(self):
        result = DocNamer.to_doc_name("repo", "/src/api")
        assert result == "repo__src_api_design.md"
