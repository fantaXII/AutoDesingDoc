from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class StructuralSignature:
    classes: list[str] = field(default_factory=list)
    functions: dict[str, list[str]] = field(default_factory=dict)
    enums: dict[str, list[str]] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructuralSignature):
            return False
        return (
            sorted(self.classes) == sorted(other.classes)
            and self.functions == other.functions
            and self.enums == other.enums
        )


class ASTAnalyzer:
    def extract_signature(self, source_code: str) -> StructuralSignature:
        """Python 소스 코드에서 구조 시그니처 추출. 파싱 실패 시 빈 서명 반환."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return StructuralSignature()

        sig = StructuralSignature()
        enum_bases = self._find_enum_bases(tree)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                sig.classes.append(node.name)
                if node.name in enum_bases:
                    sig.enums[node.name] = [
                        t.targets[0].id
                        for t in node.body
                        if isinstance(t, ast.Assign)
                        and isinstance(t.targets[0], ast.Name)
                    ]
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        key = f"{node.name}.{child.name}"
                        sig.functions[key] = [arg.arg for arg in child.args.args]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [arg.arg for arg in node.args.args]
                sig.functions[node.name] = params

        return sig

    def _find_enum_bases(self, tree: ast.AST) -> set[str]:
        enum_classes: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name in ("Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"):
                        enum_classes.add(node.name)
        return enum_classes

    def is_structural_change(self, old_content: str | None, new_content: str | None) -> bool:
        """두 버전의 소스 코드를 비교해 구조적 변경 여부 반환."""
        if old_content is None or new_content is None:
            return True
        old_sig = self.extract_signature(old_content)
        new_sig = self.extract_signature(new_content)
        # 빈 서명(파싱 실패)이 포함된 경우 보수적으로 변경으로 판단
        old_failed = not old_sig.classes and not old_sig.functions
        new_failed = not new_sig.classes and not new_sig.functions
        if old_failed != new_failed:
            return True
        # 파싱 실패한 파일인데 내용이 동일하지 않으면 변경으로 간주
        try:
            ast.parse(old_content)
            ast.parse(new_content)
        except SyntaxError:
            return old_content != new_content
        return old_sig != new_sig


class RegexStructureAnalyzer:
    """비-Python 파일용 정규식 기반 구조 변경 감지."""

    PATTERNS: dict[str, list[str]] = {
        ".ts": [
            r"^(export\s+)?(abstract\s+)?(class|interface|type|enum)\s+\w+",
            r"^(export\s+)?(async\s+)?function\s+\w+",
        ],
        ".tsx": [
            r"^(export\s+)?(abstract\s+)?(class|interface|type|enum)\s+\w+",
            r"^(export\s+)?(async\s+)?function\s+\w+",
        ],
        ".go": [
            r"^type\s+\w+\s+(struct|interface)",
            r"^func\s+(\(\w+\s+\*?\w+\)\s+)?\w+\(",
        ],
        ".java": [
            r"^(public|private|protected)?\s*(abstract\s+)?(class|interface|enum)\s+\w+",
            r"^(public|private|protected)\s+\w+\s+\w+\(",
        ],
        ".kt": [
            r"^(data\s+|sealed\s+|abstract\s+)?(class|interface|object|enum class)\s+\w+",
            r"^(fun)\s+\w+\(",
        ],
    }

    def _extract_structural_lines(self, content: str, ext: str) -> set[str]:
        patterns = self.PATTERNS.get(ext, [])
        lines: set[str] = set()
        for line in content.splitlines():
            stripped = line.strip()
            for pattern in patterns:
                if re.match(pattern, stripped):
                    lines.add(stripped)
                    break
        return lines

    def is_structural_change(self, file_path: str, old_content: str, new_content: str) -> bool:
        """확장자에 맞는 패턴으로 구조 변경 여부 반환."""
        ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        if ext not in self.PATTERNS:
            return old_content != new_content
        old_lines = self._extract_structural_lines(old_content, ext)
        new_lines = self._extract_structural_lines(new_content, ext)
        return old_lines != new_lines
