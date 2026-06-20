from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from src.config_loader import AppConfig, load_config
from src.counter.file_filter import FileFilter
from src.counter.hysteresis_evaluator import FolderAction, HysteresisDecision, HysteresisEvaluator
from src.document.doc_namer import DocNamer
from src.document.doc_writer import DocMetadata, DocWriter
from src.document.merge_handler import MergeHandler
from src.llm.claude_client import ClaudeClient
from src.pipeline.cross_ref_linker import CrossRefLinker
from src.pipeline.file_mapper import FileMapper
from src.pipeline.folder_reducer import FolderReducer
from src.trigger.ast_analyzer import ASTAnalyzer, RegexStructureAnalyzer
from src.trigger.diff_analyzer import DiffAnalyzer
from src.vcs.base import VCSAdapter
from src.vcs.github_adapter import GitHubAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def build_vcs_adapter(repo_config, config: AppConfig) -> VCSAdapter:
    if repo_config.type == "github":
        token = os.environ.get(repo_config.token_env, "")
        if not token:
            raise ValueError(f"Missing env var: {repo_config.token_env}")
        full_name = repo_config.url.rstrip("/").split("github.com/")[-1]
        return GitHubAdapter(full_name, token, branch=repo_config.branch)
    if repo_config.type == "perforce":
        from src.vcs.perforce_adapter import PerforceAdapter
        return PerforceAdapter(
            server=repo_config.server,
            depot=repo_config.depot,
            client=os.environ.get(repo_config.client_env, ""),
            password=os.environ.get(repo_config.password_env, ""),
        )
    raise ValueError(f"Unsupported VCS type: {repo_config.type}")


def build_docs_adapter(config: AppConfig) -> VCSAdapter:
    """중앙 docs 레포 어댑터 생성."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("Missing GITHUB_TOKEN for docs repo")
    full_name = config.output.docs_repo_url.rstrip("/").split("github.com/")[-1]
    return GitHubAdapter(full_name, token)


def count_folder_files(
    all_files: list[str],
    folder: str,
    file_filter: FileFilter,
) -> int:
    """폴더 하위 유효 파일 수 반환 (재귀)."""
    prefix = folder.rstrip("/") + "/" if folder else ""
    candidates = [f for f in all_files if f.startswith(prefix) or not folder]
    return len(file_filter.filter_files(candidates))


def get_all_folders(file_paths: list[str]) -> set[str]:
    """파일 목록에서 모든 폴더 경로 추출 (루트 포함)."""
    folders: set[str] = {""}
    for path in file_paths:
        parts = path.split("/")
        for i in range(1, len(parts)):
            folders.add("/".join(parts[:i]))
    return folders


def is_structural_change_for_file(
    file_path: str,
    old_content: str | None,
    new_content: str | None,
) -> bool:
    ext = Path(file_path).suffix
    if ext == ".py":
        analyzer = ASTAnalyzer()
        return analyzer.is_structural_change(old_content, new_content)
    regex_analyzer = RegexStructureAnalyzer()
    if old_content is None or new_content is None:
        return True
    return regex_analyzer.is_structural_change(file_path, old_content, new_content)


@click.command()
@click.option("--config", "config_path", default="config/repos.yaml", show_default=True)
@click.option("--repo", "repo_name", default="", help="처리할 레포 이름 (빈 문자열이면 전체)")
@click.option("--commit", "commit_sha", default="", help="트리거된 커밋 SHA")
@click.option("--dry-run", is_flag=True, help="실제 커밋 없이 예상 동작만 출력")
def main(config_path: str, repo_name: str, commit_sha: str, dry_run: bool) -> None:
    """Auto Design-Doc Generator 메인 진입점."""
    config = load_config(config_path)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY 환경 변수가 없습니다.")
        sys.exit(1)

    llm = ClaudeClient(config.llm, api_key)
    file_mapper = FileMapper(llm)
    folder_reducer = FolderReducer(llm)
    cross_ref = CrossRefLinker()
    doc_writer = DocWriter()
    merge_handler = MergeHandler(llm, doc_writer)
    hysteresis = HysteresisEvaluator(config.thresholds)

    target_repos = [r for r in config.repositories if not repo_name or r.name == repo_name]
    if not target_repos:
        logger.warning("처리할 레포가 없습니다: %s", repo_name)
        return

    docs_adapter = build_docs_adapter(config) if not dry_run else None

    for repo_config in target_repos:
        logger.info("처리 시작: %s (%s)", repo_config.name, repo_config.type)
        try:
            _process_repo(
                repo_config=repo_config,
                config=config,
                commit_sha=commit_sha,
                dry_run=dry_run,
                docs_adapter=docs_adapter,
                llm=llm,
                file_mapper=file_mapper,
                folder_reducer=folder_reducer,
                cross_ref=cross_ref,
                doc_writer=doc_writer,
                merge_handler=merge_handler,
                hysteresis=hysteresis,
            )
        except Exception as e:
            logger.error("레포 처리 실패 %s: %s", repo_config.name, e, exc_info=True)


def _process_repo(
    repo_config,
    config: AppConfig,
    commit_sha: str,
    dry_run: bool,
    docs_adapter,
    llm,
    file_mapper: FileMapper,
    folder_reducer: FolderReducer,
    cross_ref: CrossRefLinker,
    doc_writer: DocWriter,
    merge_handler: MergeHandler,
    hysteresis: HysteresisEvaluator,
) -> None:
    source_adapter = build_vcs_adapter(repo_config, config)
    file_filter = FileFilter(config.filters)

    # gitignore 로드 시도
    try:
        gitignore = source_adapter.get_file_content(".gitignore")
        file_filter.load_gitignore(gitignore)
    except FileNotFoundError:
        pass

    all_files = source_adapter.list_files()
    diff_analyzer = DiffAnalyzer()

    # 구조적 변경 파일 탐지
    structural_changed_folders: set[str] = set()
    if commit_sha:
        changed_files = source_adapter.get_changed_files(commit_sha)
        for cf in changed_files:
            old_content, new_content = None, None
            try:
                if cf.status != "added":
                    old_content = source_adapter.get_file_content(cf.old_path or cf.path, ref=f"{commit_sha}^")
            except FileNotFoundError:
                pass
            try:
                if cf.status != "deleted":
                    new_content = source_adapter.get_file_content(cf.path, ref=commit_sha)
            except FileNotFoundError:
                pass

            if is_structural_change_for_file(cf.path, old_content, new_content):
                folder = str(Path(cf.path).parent).replace("\\", "/")
                folder = "" if folder == "." else folder
                structural_changed_folders.update(_ancestor_folders(folder))
    else:
        structural_changed_folders = get_all_folders(all_files)

    # 폴더별 액션 결정
    all_folders = get_all_folders(all_files)
    actions: list[FolderAction] = []

    for folder in sorted(all_folders, key=lambda f: f.count("/")):
        file_count = count_folder_files(all_files, folder, file_filter)
        doc_path = DocNamer.to_docs_path(repo_config.name, folder, config.output.docs_path)
        doc_exists = docs_adapter.file_exists(doc_path) if docs_adapter else False
        has_change = folder in structural_changed_folders

        decision = hysteresis.decide(file_count, doc_exists, has_change)

        # 직접 하위 폴더 수집 (문서가 존재하거나 생성될 폴더만)
        direct_child_folders = [
            f for f in all_folders
            if f != folder
            and f.startswith((folder + "/") if folder else "")
            and "/" not in f[len(folder) + 1:]
            and hysteresis.decide(
                count_folder_files(all_files, f, file_filter),
                docs_adapter.file_exists(DocNamer.to_docs_path(repo_config.name, f, config.output.docs_path)) if docs_adapter else False,
            ) in (HysteresisDecision.CREATE, HysteresisDecision.UPDATE, HysteresisDecision.KEEP)
        ]
        child_doc_paths = [
            DocNamer.to_docs_path(repo_config.name, f, config.output.docs_path)
            for f in direct_child_folders
        ]

        parent_folder = str(Path(folder).parent).replace("\\", "/") if folder else None
        if parent_folder == ".":
            parent_folder = ""
        parent_doc = DocNamer.to_docs_path(repo_config.name, parent_folder, config.output.docs_path) if parent_folder is not None else None

        actions.append(FolderAction(
            folder_path=folder,
            decision=decision,
            file_count=file_count,
            doc_path=doc_path,
            child_doc_paths=child_doc_paths,
            child_folder_paths=direct_child_folders,
            parent_doc_path=parent_doc,
        ))

        if dry_run:
            click.echo(f"[DRY RUN] {decision.value.upper():8s} {doc_path} (files={file_count})")

    if dry_run:
        return

    docs_to_commit = []
    now = datetime.now(tz=timezone.utc)

    for action in actions:
        if action.decision == HysteresisDecision.SKIP:
            continue

        if action.decision == HysteresisDecision.DELETE:
            _handle_delete(action, config, docs_adapter, doc_writer, merge_handler, now, docs_to_commit, repo_config)
            continue

        if action.decision in (HysteresisDecision.CREATE, HysteresisDecision.UPDATE):
            _handle_generate(
                action, config, source_adapter, docs_adapter, file_filter,
                file_mapper, folder_reducer, cross_ref, doc_writer,
                now, commit_sha, docs_to_commit, repo_config,
            )

    if docs_to_commit:
        from src.vcs.base import DocFile
        sha = docs_adapter.commit_files(
            [DocFile(path=path, content=content) for path, content in docs_to_commit],
            f"docs: auto-update design docs from {repo_config.name}@{commit_sha or 'scan'}",
        )
        logger.info("Committed %d docs: %s", len(docs_to_commit), sha)


def _handle_generate(
    action: FolderAction, config: AppConfig, source_adapter,
    docs_adapter, file_filter: FileFilter, file_mapper: FileMapper,
    folder_reducer: FolderReducer, cross_ref: CrossRefLinker,
    doc_writer: DocWriter, now: datetime, commit_sha: str,
    docs_to_commit: list, repo_config,
) -> None:
    all_folder_files = source_adapter.list_files(action.folder_path)
    valid_files = file_filter.filter_files(all_folder_files)

    files_content: dict[str, str] = {}
    for f in valid_files:
        if not any(f.startswith(child_folder + "/") for child_folder in action.child_folder_paths):
            try:
                files_content[f] = source_adapter.get_file_content(f)
            except Exception as e:
                logger.warning("파일 읽기 실패 %s: %s", f, e)

    summaries = file_mapper.map_files(files_content, folder_context=action.folder_path)

    child_summaries: dict[str, str] = {}
    for child_doc_path, child_folder in zip(action.child_doc_paths, action.child_folder_paths):
        try:
            child_content = docs_adapter.get_file_content(child_doc_path)
            folder_name = child_folder.rsplit("/", 1)[-1]
            child_summaries[folder_name] = cross_ref.extract_child_summary(child_content)
        except Exception as e:
            logger.warning("하위 문서 읽기 실패 %s: %s", child_doc_path, e)

    body = folder_reducer.reduce(action.folder_path, summaries, child_summaries)

    if action.child_doc_paths:
        child_links = {
            p.rsplit("/", 1)[-1].replace("_design.md", ""): p
            for p in action.child_doc_paths
        }
        body = cross_ref.inject_links(body, child_links)

    metadata = DocMetadata(
        last_updated=now,
        trigger_file=commit_sha or "manual-scan",
        total_files=action.file_count,
        status="active",
        source_repo=repo_config.name,
        folder_path=action.folder_path,
    )

    existing_version = 1
    try:
        existing = docs_adapter.get_file_content(action.doc_path)
        existing_meta = doc_writer.parse_metadata(existing)
        if existing_meta:
            existing_version = existing_meta.doc_version + 1
    except FileNotFoundError:
        pass

    metadata.doc_version = existing_version
    content = doc_writer.generate(metadata, body)
    docs_to_commit.append((action.doc_path, content))
    logger.info("%s: %s", action.decision.value, action.doc_path)


def _handle_delete(
    action: FolderAction, config: AppConfig, docs_adapter,
    doc_writer: DocWriter, merge_handler: MergeHandler,
    now: datetime, docs_to_commit: list, repo_config,
) -> None:
    try:
        orphan_content = docs_adapter.get_file_content(action.doc_path)
    except FileNotFoundError:
        return

    if action.parent_doc_path:
        try:
            parent_content = docs_adapter.get_file_content(action.parent_doc_path)
            parent_meta = doc_writer.parse_metadata(parent_content) or DocMetadata(
                last_updated=now,
                trigger_file="merge",
                total_files=0,
                status="active",
                source_repo=repo_config.name,
                folder_path=str(Path(action.folder_path).parent),
            )
            parent_meta.last_updated = now
            parent_meta.status = "active"
            merged = merge_handler.merge_into_parent(
                orphan_doc_content=orphan_content,
                parent_doc_content=parent_content,
                orphan_folder_path=action.folder_path,
                new_metadata=parent_meta,
            )
            docs_to_commit.append((action.parent_doc_path, merged))
        except FileNotFoundError:
            pass

    # 빈 content로 삭제 마킹 (commit_files에서 sha=None 처리)
    docs_to_commit.append((action.doc_path, ""))
    logger.info("DELETE: %s (merged into %s)", action.doc_path, action.parent_doc_path)


def _ancestor_folders(folder: str) -> set[str]:
    folders = {folder}
    parts = folder.split("/")
    for i in range(len(parts)):
        folders.add("/".join(parts[:i]))
    return folders


if __name__ == "__main__":
    main()
