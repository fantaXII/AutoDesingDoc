from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class RepoConfig:
    name: str
    type: Literal["github", "perforce"]
    url: str
    branch: str = "main"
    token_env: str = "GITHUB_TOKEN"
    server: str = ""
    depot: str = ""
    client_env: str = "P4CLIENT"
    password_env: str = "P4PASSWD"


@dataclass
class FilterConfig:
    exclude_dirs: list[str] = field(default_factory=list)
    exclude_extensions: list[str] = field(default_factory=list)
    exclude_files: list[str] = field(default_factory=list)


@dataclass
class ThresholdConfig:
    create: int = 25
    delete: int = 10


@dataclass
class LLMConfig:
    map_model: str = "claude-haiku-4-5"
    reduce_model: str = "claude-sonnet-4-6"
    max_tokens_per_file: int = 4000
    temperature: float = 0.2


@dataclass
class OutputConfig:
    docs_repo_url: str = ""
    docs_path: str = "docs/"
    global_context_file: str = "docs/CLAUDE.md"


@dataclass
class AppConfig:
    repositories: list[RepoConfig]
    filters: FilterConfig
    thresholds: ThresholdConfig
    llm: LLMConfig
    output: OutputConfig


def load_config(config_path: str | Path) -> AppConfig:
    """repos.yaml을 파싱해 AppConfig를 반환. 파일 없으면 FileNotFoundError."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    repositories = [
        RepoConfig(
            name=r["name"],
            type=r["type"],
            url=r.get("url", ""),
            branch=r.get("branch", "main"),
            token_env=r.get("token_env", "GITHUB_TOKEN"),
            server=r.get("server", ""),
            depot=r.get("depot", ""),
            client_env=r.get("client_env", "P4CLIENT"),
            password_env=r.get("password_env", "P4PASSWD"),
        )
        for r in data.get("repositories", [])
    ]

    filters_data = data.get("filters", {})
    filters = FilterConfig(
        exclude_dirs=filters_data.get("exclude_dirs", []),
        exclude_extensions=filters_data.get("exclude_extensions", []),
        exclude_files=filters_data.get("exclude_files", []),
    )

    thresholds_data = data.get("thresholds", {})
    thresholds = ThresholdConfig(
        create=thresholds_data.get("create", 25),
        delete=thresholds_data.get("delete", 10),
    )

    llm_data = data.get("llm", {})
    llm = LLMConfig(
        map_model=llm_data.get("map_model", "claude-haiku-4-5"),
        reduce_model=llm_data.get("reduce_model", "claude-sonnet-4-6"),
        max_tokens_per_file=llm_data.get("max_tokens_per_file", 4000),
        temperature=llm_data.get("temperature", 0.2),
    )

    output_data = data.get("output", {})
    output = OutputConfig(
        docs_repo_url=output_data.get("docs_repo_url", ""),
        docs_path=output_data.get("docs_path", "docs/"),
        global_context_file=output_data.get("global_context_file", "docs/CLAUDE.md"),
    )

    return AppConfig(
        repositories=repositories,
        filters=filters,
        thresholds=thresholds,
        llm=llm,
        output=output,
    )
