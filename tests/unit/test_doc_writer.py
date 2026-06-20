import pytest
import yaml
from datetime import datetime, timezone
from src.document.doc_writer import DocWriter, DocMetadata


@pytest.fixture
def writer():
    return DocWriter()


@pytest.fixture
def sample_metadata():
    return DocMetadata(
        last_updated=datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc),
        trigger_file="src/api/router.py",
        total_files=32,
        status="active",
        source_repo="my-backend",
        folder_path="src/api",
        doc_version=1,
    )


class TestDocWriter:
    def test_generates_valid_yaml_frontmatter(self, writer, sample_metadata):
        result = writer.generate(sample_metadata, "## 개요\n내용")
        assert result.startswith("---\n")
        assert "---" in result[4:]

    def test_frontmatter_contains_required_fields(self, writer, sample_metadata):
        result = writer.generate(sample_metadata, "body")
        frontmatter_text = result.split("---")[1]
        fm = yaml.safe_load(frontmatter_text)
        assert "last_updated" in fm
        assert "trigger_file" in fm
        assert "total_files" in fm
        assert "status" in fm

    def test_total_files_is_integer(self, writer, sample_metadata):
        result = writer.generate(sample_metadata, "body")
        fm = yaml.safe_load(result.split("---")[1])
        assert isinstance(fm["total_files"], int)

    def test_body_follows_frontmatter(self, writer, sample_metadata):
        body = "## 개요\n테스트 내용"
        result = writer.generate(sample_metadata, body)
        assert body in result

    def test_parse_metadata_roundtrip(self, writer, sample_metadata):
        content = writer.generate(sample_metadata, "body")
        parsed = writer.parse_metadata(content)
        assert parsed is not None
        assert parsed.total_files == sample_metadata.total_files
        assert parsed.status == sample_metadata.status
        assert parsed.source_repo == sample_metadata.source_repo
        assert parsed.folder_path == sample_metadata.folder_path

    def test_parse_metadata_returns_none_for_invalid(self, writer):
        assert writer.parse_metadata("no frontmatter here") is None

    def test_parse_metadata_returns_none_for_empty(self, writer):
        assert writer.parse_metadata("") is None

    def test_update_metadata_preserves_body(self, writer, sample_metadata):
        original_body = "## 개요\n원래 내용입니다."
        original = writer.generate(sample_metadata, original_body)
        new_meta = DocMetadata(
            last_updated=datetime(2026, 6, 21, 0, 0, 0, tzinfo=timezone.utc),
            trigger_file="src/new.py",
            total_files=40,
            status="active",
            source_repo="my-backend",
            folder_path="src/api",
            doc_version=2,
        )
        updated = writer.update_metadata(original, new_meta)
        assert "원래 내용입니다." in updated
        fm = yaml.safe_load(updated.split("---")[1])
        assert fm["total_files"] == 40
        assert fm["doc_version"] == 2

    def test_status_values(self, writer):
        for status in ("active", "merging", "archived"):
            meta = DocMetadata(
                last_updated=datetime(2026, 6, 20, tzinfo=timezone.utc),
                trigger_file="test.py",
                total_files=1,
                status=status,
                source_repo="repo",
                folder_path="",
            )
            content = writer.generate(meta, "body")
            parsed = writer.parse_metadata(content)
            assert parsed.status == status
