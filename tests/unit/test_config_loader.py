import pytest
from pathlib import Path
import yaml
from src.config_loader import load_config, AppConfig


@pytest.fixture
def sample_config_file(tmp_path):
    config = {
        "repositories": [
            {
                "name": "test-repo",
                "type": "github",
                "url": "https://github.com/org/test-repo",
                "branch": "main",
                "token_env": "GITHUB_TOKEN",
            }
        ],
        "filters": {
            "exclude_dirs": ["node_modules", ".venv"],
            "exclude_extensions": [".pyc", ".jpg"],
            "exclude_files": ["package-lock.json"],
        },
        "thresholds": {"create": 25, "delete": 10},
        "llm": {
            "map_model": "claude-haiku-4-5",
            "reduce_model": "claude-sonnet-4-6",
            "max_tokens_per_file": 4000,
            "temperature": 0.2,
        },
        "output": {
            "docs_repo_url": "https://github.com/org/docs",
            "docs_path": "docs/",
            "global_context_file": "docs/CLAUDE.md",
        },
    }
    config_file = tmp_path / "repos.yaml"
    config_file.write_text(yaml.dump(config))
    return config_file


class TestConfigLoader:
    def test_load_valid_config(self, sample_config_file):
        config = load_config(sample_config_file)
        assert isinstance(config, AppConfig)
        assert len(config.repositories) == 1
        assert config.repositories[0].name == "test-repo"
        assert config.repositories[0].type == "github"

    def test_filter_config_loaded(self, sample_config_file):
        config = load_config(sample_config_file)
        assert "node_modules" in config.filters.exclude_dirs
        assert ".pyc" in config.filters.exclude_extensions

    def test_threshold_config_loaded(self, sample_config_file):
        config = load_config(sample_config_file)
        assert config.thresholds.create == 25
        assert config.thresholds.delete == 10

    def test_llm_config_loaded(self, sample_config_file):
        config = load_config(sample_config_file)
        assert config.llm.map_model == "claude-haiku-4-5"
        assert config.llm.reduce_model == "claude-sonnet-4-6"

    def test_output_config_loaded(self, sample_config_file):
        config = load_config(sample_config_file)
        assert config.output.docs_path == "docs/"

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_defaults_applied_for_missing_fields(self, tmp_path):
        minimal = {"repositories": [], "filters": {}, "thresholds": {}, "llm": {}, "output": {}}
        f = tmp_path / "minimal.yaml"
        f.write_text(yaml.dump(minimal))
        config = load_config(f)
        assert config.thresholds.create == 25
        assert config.thresholds.delete == 10
        assert config.llm.temperature == 0.2
