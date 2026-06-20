from __future__ import annotations

import json

import anthropic

from src.config_loader import LLMConfig
from .base import FileSummary, LLMClient


class ClaudeClient(LLMClient):
    def __init__(self, config: LLMConfig, api_key: str):
        self._config = config
        self._client = anthropic.Anthropic(api_key=api_key)

    def summarize_file(
        self,
        file_path: str,
        content: str,
        folder_context: str = "",
    ) -> FileSummary:
        context_hint = f"\n이 파일은 다음 폴더의 일부입니다: {folder_context}" if folder_context else ""
        prompt = f"""파일 경로: {file_path}{context_hint}

파일 내용:
{content[:self._config.max_tokens_per_file * 3]}

위 파일을 분석하여 아래 JSON 형식으로만 응답하세요 (소스 코드 블록, Raw 값 포함 금지):
{{
  "purpose": "이 파일의 핵심 역할을 1-2문장으로 설명",
  "key_concepts": ["주요 클래스/Enum/Interface 이름과 그 의미 (최대 5개)"],
  "dependencies": ["주요 외부 의존 관계 (최대 5개)"]
}}"""

        response = self._client.messages.create(
            model=self._config.map_model,
            max_tokens=1000,
            temperature=self._config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {"purpose": text[:200], "key_concepts": [], "dependencies": []}

        return FileSummary(
            file_path=file_path,
            purpose=data.get("purpose", ""),
            key_concepts=data.get("key_concepts", []),
            dependencies=data.get("dependencies", []),
        )

    def synthesize_folder(
        self,
        folder_path: str,
        summaries: list[FileSummary],
        child_doc_summaries: dict[str, str],
    ) -> str:
        summaries_text = "\n\n".join(
            f"### {s.file_path}\n"
            f"- 목적: {s.purpose}\n"
            f"- 핵심 개념: {', '.join(s.key_concepts)}\n"
            f"- 의존성: {', '.join(s.dependencies)}"
            for s in summaries
        )

        child_text = ""
        if child_doc_summaries:
            child_text = "\n\n## 하위 폴더 요약\n" + "\n\n".join(
                f"### {folder}\n{summary}" for folder, summary in child_doc_summaries.items()
            )

        prompt = f"""폴더: {folder_path}

파일 요약 목록:
{summaries_text}
{child_text}

위 정보를 바탕으로 폴더 단위 디자인 문서를 작성하세요.

**규칙 (반드시 준수):**
- 소스 코드 블록(```) 및 Raw 값 포함 금지
- 개념, Enum 의미, 핵심 목적, 디렉토리 구조, 주요 워크플로우 시나리오 위주로 작성
- 하위 폴더가 자체 문서를 가진 경우 "구조와 역할" 수준 요약만 작성 (상세 내용은 링크 처리)
- 마크다운 형식으로 작성

**필수 섹션:**
## 개요
## 디렉토리 구조
## 핵심 컴포넌트
## 주요 워크플로우
"""

        response = self._client.messages.create(
            model=self._config.reduce_model,
            max_tokens=4000,
            temperature=self._config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def merge_into_parent(
        self,
        orphan_doc_content: str,
        parent_doc_content: str,
        folder_path: str,
    ) -> str:
        prompt = f"""다음 두 디자인 문서를 병합하세요.

삭제될 하위 폴더({folder_path}) 문서:
{orphan_doc_content}

현재 상위 폴더 문서:
{parent_doc_content}

**지시사항:**
- 삭제될 문서의 핵심 내용을 상위 문서에 자연스럽게 통합하세요.
- 소스 코드 블록 및 Raw 값 포함 금지
- 기존 상위 문서의 구조를 유지하면서 {folder_path} 섹션을 추가/보강하세요.
- 마크다운 형식으로 완성된 상위 문서 전체를 반환하세요.
"""

        response = self._client.messages.create(
            model=self._config.reduce_model,
            max_tokens=6000,
            temperature=self._config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
