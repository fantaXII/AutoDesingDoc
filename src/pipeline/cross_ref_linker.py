from __future__ import annotations

import re


class CrossRefLinker:
    _OVERVIEW_RE = re.compile(r"## 개요\s*\n(.*?)(?=\n##|\Z)", re.DOTALL)

    def inject_links(
        self,
        doc_content: str,
        child_docs: dict[str, str],
        link_base: str = "",
    ) -> str:
        """
        문서 끝에 Cross-Reference 섹션을 추가.
        child_docs: {하위 폴더명 → 문서 상대 경로}
        """
        if not child_docs:
            return doc_content

        lines = ["\n## Cross-Reference\n"]
        for folder_name, doc_path in child_docs.items():
            link_path = f"{link_base}{doc_path}" if link_base else doc_path
            lines.append(f"- [{folder_name} 상세 설계]({link_path})")

        return doc_content.rstrip() + "\n" + "\n".join(lines) + "\n"

    def extract_child_summary(
        self,
        child_doc_content: str,
        max_chars: int = 500,
    ) -> str:
        """하위 문서에서 Cross-Reference용 요약 발췌 (## 개요 섹션 또는 앞 N글자)."""
        match = self._OVERVIEW_RE.search(child_doc_content)
        if match:
            summary = match.group(1).strip()
            return summary[:max_chars] if len(summary) > max_chars else summary

        # Frontmatter 이후 본문 시작
        parts = child_doc_content.split("---\n", 2)
        body = parts[-1].strip() if len(parts) >= 3 else child_doc_content.strip()
        return body[:max_chars]
