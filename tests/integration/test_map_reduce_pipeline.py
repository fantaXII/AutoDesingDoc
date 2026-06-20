import pytest
from unittest.mock import MagicMock, call
from src.llm.base import FileSummary
from src.pipeline.file_mapper import FileMapper
from src.pipeline.folder_reducer import FolderReducer
from src.pipeline.cross_ref_linker import CrossRefLinker


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.summarize_file.return_value = FileSummary(
        file_path="test.py",
        purpose="테스트 파일",
        key_concepts=["TestClass"],
        dependencies=["pytest"],
    )
    llm.synthesize_folder.return_value = "## 개요\n테스트 폴더 요약\n\n## 핵심 컴포넌트\n내용"
    return llm


class TestFileMapper:
    def test_map_returns_summary_per_file(self, mock_llm):
        mapper = FileMapper(mock_llm)
        files = {"src/a.py": "class A: pass", "src/b.py": "def b(): pass"}
        summaries = mapper.map_files(files)
        assert len(summaries) == 2
        assert mock_llm.summarize_file.call_count == 2

    def test_map_single_file(self, mock_llm):
        mapper = FileMapper(mock_llm)
        result = mapper.map_file("src/a.py", "class A: pass")
        mock_llm.summarize_file.assert_called_once_with("src/a.py", "class A: pass", "")
        assert isinstance(result, FileSummary)

    def test_parallel_map_handles_errors_gracefully(self, mock_llm):
        mock_llm.summarize_file.side_effect = [
            FileSummary("a.py", "OK", [], []),
            Exception("API timeout"),
            FileSummary("c.py", "OK", [], []),
        ]
        mapper = FileMapper(mock_llm)
        files = {"a.py": "", "b.py": "", "c.py": ""}
        summaries = mapper.map_files(files)
        assert len(summaries) == 3
        error_summary = next(s for s in summaries if s.file_path == "b.py")
        assert error_summary.purpose == "요약 실패"

    def test_map_empty_files(self, mock_llm):
        mapper = FileMapper(mock_llm)
        assert mapper.map_files({}) == []
        mock_llm.summarize_file.assert_not_called()

    def test_map_passes_folder_context(self, mock_llm):
        mapper = FileMapper(mock_llm)
        mapper.map_files({"src/a.py": "code"}, folder_context="src/")
        mock_llm.summarize_file.assert_called_once_with("src/a.py", "code", "src/")


class TestFolderReducer:
    def test_reduce_calls_synthesize_with_summaries(self, mock_llm):
        reducer = FolderReducer(mock_llm)
        summaries = [FileSummary("a.py", "A 파일", ["A"], [])]
        result = reducer.reduce("src/", summaries)
        mock_llm.synthesize_folder.assert_called_once()
        assert isinstance(result, str)

    def test_reduce_passes_child_doc_summaries(self, mock_llm):
        reducer = FolderReducer(mock_llm)
        summaries = [FileSummary("a.py", "A 파일", [], [])]
        child_summaries = {"sub": "하위 폴더 요약"}
        reducer.reduce("src/", summaries, child_summaries)
        call_kwargs = mock_llm.synthesize_folder.call_args
        assert call_kwargs[1]["child_doc_summaries"] == child_summaries or \
               call_kwargs[0][2] == child_summaries

    def test_reduce_empty_summaries(self, mock_llm):
        reducer = FolderReducer(mock_llm)
        result = reducer.reduce("src/", [])
        assert isinstance(result, str)


class TestCrossRefLinker:
    @pytest.fixture
    def linker(self):
        return CrossRefLinker()

    def test_inject_links_adds_section(self, linker):
        content = "## 개요\n내용입니다."
        child_docs = {"api": "docs/repo_src_api_design.md"}
        result = linker.inject_links(content, child_docs)
        assert "Cross-Reference" in result
        assert "api 상세 설계" in result

    def test_inject_links_empty_child_docs(self, linker):
        content = "## 개요\n내용"
        result = linker.inject_links(content, {})
        assert result == content

    def test_extract_child_summary_from_overview(self, linker):
        content = "---\nstatus: active\n---\n\n## 개요\n이것은 핵심 요약입니다.\n\n## 핵심 컴포넌트\n내용"
        summary = linker.extract_child_summary(content, max_chars=100)
        assert "핵심 요약" in summary

    def test_extract_child_summary_truncates(self, linker):
        long_content = "---\n---\n\n## 개요\n" + "x" * 1000
        summary = linker.extract_child_summary(long_content, max_chars=50)
        assert len(summary) <= 50

    def test_extract_child_summary_fallback_to_body(self, linker):
        content = "---\nstatus: active\n---\n\nsome body content without overview"
        summary = linker.extract_child_summary(content)
        assert "some body content" in summary
