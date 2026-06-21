# Auto Design-Doc Generator — 설계 문서

> 참조: [plan.md](./plan.md) (아키텍처 설계), [spec.md](./spec.md) (구현 명세)

---

## 1. 프로젝트 개요

GitHub 또는 Perforce 레포지토리의 코드 변경을 감지하여, **구조적 변경이 있을 때만** Claude LLM을 호출해 폴더 단위 디자인 문서(`.md`)를 자동 생성·갱신·삭제하는 오케스트레이터 시스템.

| 항목 | 내용 |
|------|------|
| 언어 | Python 3.11+ |
| 패키지 관리 | uv |
| VCS 지원 | GitHub (구현 완료), Perforce (stub) |
| LLM | Anthropic Claude (Haiku / Sonnet) |
| 실행 환경 | CLI (`uv run autodesign`) 또는 GitHub Actions |
| 문서 저장 위치 | 중앙 오케스트레이터 레포의 `docs/` 폴더 |

---

## 2. 프로젝트 구조

```
AutoDesignDoc/
├── config/
│   └── repos.yaml                  # 등록 레포 목록, 필터/임계값/LLM 설정
├── docs/                           # 생성된 디자인 문서 저장 (gitignore됨)
├── src/
│   ├── main.py                     # CLI 진입점 — 전체 파이프라인 조율
│   ├── config_loader.py            # repos.yaml 파싱 → AppConfig 반환
│   ├── validate.py                 # 설정 파일 유효성 검증 CLI
│   ├── vcs/
│   │   ├── base.py                 # VCSAdapter 추상 인터페이스
│   │   ├── github_adapter.py       # PyGitHub 기반 GitHub 구현체
│   │   └── perforce_adapter.py     # p4 CLI subprocess 래핑 (stub)
│   ├── trigger/
│   │   ├── diff_analyzer.py        # Git diff 파싱 (변경 파일 목록 추출)
│   │   └── ast_analyzer.py         # Python AST / 정규식 구조 변경 감지
│   ├── counter/
│   │   ├── file_filter.py          # exclude_dirs/extensions/files 필터링
│   │   └── hysteresis_evaluator.py # 폴더별 CREATE/UPDATE/DELETE/SKIP 결정
│   ├── llm/
│   │   ├── base.py                 # LLMClient 추상 인터페이스
│   │   └── claude_client.py        # Anthropic SDK 구현체
│   ├── pipeline/
│   │   ├── file_mapper.py          # Map 단계: 파일별 LLM 요약
│   │   ├── folder_reducer.py       # Reduce 단계: 폴더 문서 합성
│   │   └── cross_ref_linker.py     # Cross-Reference 하이퍼링크 주입
│   └── document/
│       ├── doc_writer.py           # YAML Frontmatter + 마크다운 생성
│       ├── doc_namer.py            # 폴더 경로 → 문서 파일명 변환
│       └── merge_handler.py        # 문서 삭제 시 상위 문서로 병합
├── tests/
│   ├── unit/                       # 단위 테스트
│   └── integration/                # 통합 테스트 (Map-Reduce 파이프라인)
├── pyproject.toml                  # 프로젝트 메타데이터 및 의존성
└── uv.lock                         # 고정된 의존성 버전 (40개 패키지)
```

---

## 3. 환경 설정

### 3.1 uv 설치 (최초 1회)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### 3.2 의존성 설치 및 가상환경 생성

```bash
uv sync --all-groups   # 프로덕션 + dev 의존성 모두 설치
```

### 3.3 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:

```bash
# GitHub 소스 레포 접근용
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Claude LLM 호출용
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

---

## 4. VCS 브랜치 설정

### 4.1 GitHub 브랜치 설정

`config/repos.yaml`에 레포를 등록한다:

```yaml
repositories:
  - name: my-backend           # 문서 파일명 prefix로 사용됨
    type: github
    url: https://github.com/org/my-backend
    branch: main               # 감시할 브랜치
    token_env: GITHUB_TOKEN    # 환경 변수명 (직접 값 아님)
```

**필요 권한**: `GITHUB_TOKEN`에 `repo` (private) 또는 `public_repo` (public) 스코프.

여러 레포를 동시에 등록할 수 있으며, 토큰 환경 변수명을 레포별로 다르게 지정할 수 있다:

```yaml
repositories:
  - name: frontend
    type: github
    url: https://github.com/org/frontend
    branch: develop
    token_env: GITHUB_TOKEN_FRONTEND

  - name: backend
    type: github
    url: https://github.com/org/backend
    branch: main
    token_env: GITHUB_TOKEN_BACKEND
```

### 4.2 Perforce 브랜치 설정

```yaml
repositories:
  - name: game-engine
    type: perforce
    server: perforce.company.com:1666
    depot: //depot/game-engine/main
    client_env: P4CLIENT       # p4 클라이언트 워크스페이스 이름
    password_env: P4PASSWD     # p4 패스워드
```

> **주의**: `commit_files`는 아직 구현되지 않아 Perforce 레포에서는 문서 생성이 불가능하다. (`NotImplementedError`)

### 4.3 필터 설정

```yaml
filters:
  exclude_dirs:
    - node_modules
    - .venv
    - __pycache__
    - .git
    - dist
    - build
    - .pytest_cache
  exclude_extensions:
    - .pyc
    - .jpg
    - .png
    - .lock
    - .exe
    - .dll
  exclude_files:
    - package-lock.json
    - yarn.lock
    - "*.min.js"
```

### 4.4 Hysteresis 임계값 설정

```yaml
thresholds:
  create: 25    # 유효 파일 수 >= 25 이면 문서 생성
  delete: 10    # 유효 파일 수 <= 10 이면 문서 삭제 (상위 문서로 병합)
```

---

## 5. 실행 방법

### 5.1 특정 레포 + 커밋 처리

```bash
uv run autodesign \
  --config config/repos.yaml \
  --repo my-backend \
  --commit abc1234
```

### 5.2 전체 레포 전체 스캔

```bash
uv run autodesign --config config/repos.yaml
```

### 5.3 Dry-run (실제 커밋 없이 예상 동작 확인)

```bash
uv run autodesign \
  --config config/repos.yaml \
  --repo my-backend \
  --dry-run
```

출력 예시:
```
[DRY RUN] CREATE   docs/my-backend_src_api_design.md (files=34)
[DRY RUN] UPDATE   docs/my-backend_src_design.md (files=82)
[DRY RUN] SKIP     docs/my-backend_tests_design.md (files=18)
[DRY RUN] DELETE   docs/my-backend_src_legacy_design.md (files=7)
```

### 5.4 설정 파일 유효성 검증

```bash
uv run autodesign-validate --config config/repos.yaml
```

### 5.5 테스트 실행

```bash
uv run pytest                          # 전체 테스트
uv run pytest tests/unit/              # 단위 테스트만
uv run pytest -m "not github_api and not llm"  # 외부 API 없이 실행
uv run pytest --cov=src --cov-report=term-missing  # 커버리지 포함
```

---

## 6. 처리 흐름

```
커밋 Push
    ↓
main.py: config 로드, VCSAdapter 초기화
    ↓
get_changed_files(commit_sha)
    ↓
is_structural_change(file, old_content, new_content)
    ↓ 구조적 변경 있음          ↓ 없음 (주석·변수값만 변경)
영향 폴더 목록 도출            SKIP → 종료
    ↓
count_folder_files(folder) → 유효 파일 수 계산
    ↓
HysteresisEvaluator.decide(file_count, doc_exists, has_change)
    ↓
  CREATE / UPDATE          DELETE               SKIP
      ↓                      ↓                   ↓
  FileMapper.map()       MergeHandler         종료
  (파일별 Haiku 요약)    (상위 문서 병합)
      ↓
  FolderReducer.reduce()
  (Sonnet으로 폴더 문서 합성)
      ↓
  CrossRefLinker.inject_links()
  (하위 문서 링크 주입)
      ↓
  DocWriter.generate()
  (YAML Frontmatter + 마크다운)
      ↓
  docs 레포에 단일 커밋으로 저장
```

---

## 7. 산출물

### 7.1 생성되는 파일

| 파일 | 위치 | 설명 |
|------|------|------|
| `{repo}_{folder_path}_design.md` | `docs/` | 폴더 단위 디자인 문서 |
| `CLAUDE.md` | `docs/` | 전체 레포 글로벌 컨텍스트 인덱스 |
| `uv.lock` | 프로젝트 루트 | 고정된 의존성 버전 목록 |

**문서 파일명 규칙:**
```
repo_name + "_" + folder_path (슬래시 → 언더스코어) + "_design.md"

예)
  repo="my-backend", folder="src/api/users"
  → my-backend_src_api_users_design.md

  repo="my-backend", folder="" (루트)
  → my-backend_root_design.md
```

### 7.2 문서 구조 (YAML Frontmatter + Markdown)

```markdown
---
last_updated: "2026-06-21T00:00:00+00:00"
trigger_file: "abc1234"
total_files: 34
status: active
source_repo: my-backend
folder_path: src/api/users
doc_version: 3
---

## 개요
...

## 디렉토리 구조
...

## 핵심 컴포넌트
...

## 주요 워크플로우
...
```

**status 값:**
| 값 | 의미 |
|----|------|
| `active` | 정상 운영 중 |
| `merging` | 파일 수 ≤ 10, 상위 문서로 병합 중 |
| `archived` | 삭제 완료 (내용은 상위 문서로 이전됨) |

### 7.3 LLM 모델 분리

| 단계 | 모델 | 용도 |
|------|------|------|
| Map (파일별 요약) | `claude-haiku-4-5` | 비용 절감, 빠른 처리 |
| Reduce (폴더 합성) | `claude-sonnet-4-6` | 높은 품질의 문서 생성 |

---

## 8. GitHub Actions 연동

### 8.1 소스 레포에 설치할 dispatch workflow

```yaml
# .github/workflows/notify-design-doc.yml
name: Notify Design Doc Orchestrator
on:
  push:
    branches: [main]

jobs:
  dispatch:
    runs-on: ubuntu-latest
    steps:
      - uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.ORCHESTRATOR_DISPATCH_TOKEN }}
          repository: org/auto-design-doc-orchestrator
          event-type: source-repo-updated
          client-payload: |
            {
              "repo_name": "${{ github.event.repository.name }}",
              "commit_sha": "${{ github.sha }}"
            }
```

### 8.2 오케스트레이터 메인 workflow

```yaml
# .github/workflows/orchestrate.yml
name: Generate Design Docs
on:
  repository_dispatch:
    types: [source-repo-updated]
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.11"
      - run: uv sync
      - name: Run generator
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          uv run autodesign \
            --config config/repos.yaml \
            --repo "${{ github.event.client_payload.repo_name }}" \
            --commit "${{ github.event.client_payload.commit_sha }}"
```

---

## 9. 의존성

```toml
# 프로덕션 (pyproject.toml [project.dependencies])
anthropic>=0.40.0       # Claude LLM SDK
PyGithub>=2.3.0         # GitHub API 클라이언트
pathspec>=0.12.0        # .gitignore 패턴 매칭
pyyaml>=6.0.2           # repos.yaml 파싱
python-dotenv>=1.0.0    # 환경 변수 관리
httpx>=0.27.0           # HTTP 클라이언트 (확장용)
click>=8.1.0            # CLI 인터페이스

# 개발 (pyproject.toml [dependency-groups.dev])
pytest>=8.0.0
pytest-cov>=5.0.0
pytest-mock>=3.14.0
```

---

## 10. 확장 포인트

### 새 VCS 추가

1. `src/vcs/base.py`의 `VCSAdapter` 추상 클래스 상속
2. `get_changed_files`, `get_file_content`, `list_files`, `commit_files`, `file_exists` 5개 메서드 구현
3. `config/repos.yaml`에 `type: new_vcs` 추가
4. `src/main.py`의 `build_vcs_adapter()`에 분기 추가

### 새 LLM 추가

1. `src/llm/base.py`의 `LLMClient` 추상 클래스 상속
2. `summarize_file`, `synthesize_folder`, `merge_into_parent` 3개 메서드 구현
3. `config/repos.yaml`의 `llm.provider` 값 변경
