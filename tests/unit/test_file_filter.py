import pytest
from src.config_loader import FilterConfig
from src.counter.file_filter import FileFilter


@pytest.fixture
def filter_config():
    return FilterConfig(
        exclude_dirs=["node_modules", ".venv", "__pycache__"],
        exclude_extensions=[".pyc", ".jpg", ".png"],
        exclude_files=["package-lock.json"],
    )


@pytest.fixture
def file_filter(filter_config):
    return FileFilter(filter_config)


class TestFileFilter:
    def test_valid_python_file(self, file_filter):
        assert file_filter.is_valid("src/main.py") is True

    def test_valid_ts_file(self, file_filter):
        assert file_filter.is_valid("src/app.ts") is True

    def test_exclude_by_dir(self, file_filter):
        assert file_filter.is_valid("node_modules/lodash/index.js") is False

    def test_exclude_by_dir_nested(self, file_filter):
        assert file_filter.is_valid("src/.venv/lib/python3.11/site.py") is False

    def test_exclude_by_extension_jpg(self, file_filter):
        assert file_filter.is_valid("static/logo.png") is False

    def test_exclude_by_extension_pyc(self, file_filter):
        assert file_filter.is_valid("src/__pycache__/main.cpython-311.pyc") is False

    def test_exclude_by_filename_glob(self, file_filter):
        assert file_filter.is_valid("package-lock.json") is False

    def test_gitignore_pattern_dist(self, file_filter):
        file_filter.load_gitignore("dist/\nbuild/\n*.log")
        assert file_filter.is_valid("dist/bundle.js") is False

    def test_gitignore_pattern_log(self, file_filter):
        file_filter.load_gitignore("dist/\nbuild/\n*.log")
        assert file_filter.is_valid("server.log") is False

    def test_gitignore_does_not_exclude_valid(self, file_filter):
        file_filter.load_gitignore("dist/\nbuild/\n*.log")
        assert file_filter.is_valid("src/app.ts") is True

    def test_filter_files_returns_only_valid(self, file_filter):
        files = ["src/main.py", "node_modules/lib.js", "src/utils.py", "logo.png"]
        result = file_filter.filter_files(files)
        assert result == ["src/main.py", "src/utils.py"]

    def test_empty_file_list(self, file_filter):
        assert file_filter.filter_files([]) == []

    def test_pyc_excluded_regardless_of_dir(self, file_filter):
        assert file_filter.is_valid("any_dir/module.pyc") is False
