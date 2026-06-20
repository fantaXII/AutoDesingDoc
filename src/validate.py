from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml


CODE_BLOCK_RE = re.compile(r"```[\w]*\n.*?```", re.DOTALL)
REQUIRED_FIELDS = {"last_updated", "trigger_file", "total_files", "status"}
VALID_STATUSES = {"active", "merging", "archived"}
REQUIRED_SECTIONS = ["## 개요", "## 핵심 컴포넌트"]


def validate_file(file_path: Path) -> list[str]:
    errors: list[str] = []
    content = file_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        errors.append("YAML Frontmatter 없음")
        return errors

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append("YAML Frontmatter 종료 구분자(---) 없음")
        return errors

    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        errors.append(f"YAML 파싱 실패: {e}")
        return errors

    if not isinstance(fm, dict):
        errors.append("Frontmatter가 딕셔너리가 아님")
        return errors

    for field in REQUIRED_FIELDS:
        if field not in fm:
            errors.append(f"필수 필드 누락: {field}")
        elif field == "total_files" and not isinstance(fm[field], int):
            errors.append(f"total_files 타입 오류: {type(fm[field]).__name__} (기대: int)")
        elif field == "status" and fm[field] not in VALID_STATUSES:
            errors.append(f"status 값 오류: {fm[field]} (허용: {VALID_STATUSES})")
        elif field == "last_updated":
            try:
                datetime.fromisoformat(str(fm[field]))
            except (ValueError, TypeError):
                errors.append("last_updated가 ISO 8601 형식이 아님")

    body = parts[2]
    if CODE_BLOCK_RE.search(body):
        errors.append("소스 코드 블록(```) 포함 — 디자인 문서에는 Raw 코드 금지")

    if len(body.strip()) < 200:
        errors.append(f"문서 내용이 너무 짧음 ({len(body.strip())}자, 최소 200자)")

    return errors


@click.command()
@click.argument("docs_dir", default="docs/")
@click.option("--strict", is_flag=True, help="오류 발생 시 exit code 1 반환")
def validate(docs_dir: str, strict: bool) -> None:
    """생성된 디자인 문서의 YAML Frontmatter와 내용 규칙을 검증합니다."""
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        click.echo(f"디렉토리 없음: {docs_dir}", err=True)
        sys.exit(1)

    md_files = list(docs_path.glob("**/*_design.md"))
    if not md_files:
        click.echo(f"검증할 디자인 문서 없음: {docs_dir}")
        return

    has_error = False
    for md_file in sorted(md_files):
        errors = validate_file(md_file)
        if errors:
            has_error = True
            click.echo(f"\n[FAIL] {md_file.relative_to(docs_path)}")
            for err in errors:
                click.echo(f"  - {err}")
        else:
            click.echo(f"[OK]   {md_file.relative_to(docs_path)}")

    if has_error and strict:
        sys.exit(1)


if __name__ == "__main__":
    validate()
