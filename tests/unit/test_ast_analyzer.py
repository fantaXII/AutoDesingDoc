import pytest
from src.trigger.ast_analyzer import ASTAnalyzer, RegexStructureAnalyzer


@pytest.fixture
def analyzer():
    return ASTAnalyzer()


class TestASTAnalyzer:
    def test_detects_new_class(self, analyzer):
        old = "def foo(): pass"
        new = "class Bar: pass\ndef foo(): pass"
        assert analyzer.is_structural_change(old, new) is True

    def test_detects_removed_function(self, analyzer):
        old = "def foo(): pass\ndef bar(): pass"
        new = "def foo(): pass"
        assert analyzer.is_structural_change(old, new) is True

    def test_detects_changed_function_signature(self, analyzer):
        old = "def foo(a, b): pass"
        new = "def foo(a, b, c): pass"
        assert analyzer.is_structural_change(old, new) is True

    def test_ignores_comment_change(self, analyzer):
        old = "def foo(a):\n    pass"
        new = "def foo(a):\n    # new comment\n    pass"
        assert analyzer.is_structural_change(old, new) is False

    def test_ignores_variable_value_change(self, analyzer):
        old = "X = 1\ndef foo(): pass"
        new = "X = 2\ndef foo(): pass"
        assert analyzer.is_structural_change(old, new) is False

    def test_detects_enum_value_change(self, analyzer):
        old = "from enum import Enum\nclass Status(Enum):\n    A = 1"
        new = "from enum import Enum\nclass Status(Enum):\n    A = 1\n    B = 2"
        assert analyzer.is_structural_change(old, new) is True

    def test_new_file_is_structural_change(self, analyzer):
        assert analyzer.is_structural_change(None, "def foo(): pass") is True

    def test_deleted_file_is_structural_change(self, analyzer):
        assert analyzer.is_structural_change("def foo(): pass", None) is True

    def test_both_none_is_not_structural(self, analyzer):
        assert analyzer.is_structural_change(None, None) is True

    def test_invalid_syntax_treated_as_structural(self, analyzer):
        old = "def foo(): pass"
        new = "def foo(: invalid syntax"
        assert analyzer.is_structural_change(old, new) is True

    def test_no_change(self, analyzer):
        code = "class Foo:\n    def bar(self, x: int) -> str: ...\n"
        assert analyzer.is_structural_change(code, code) is False

    def test_async_function_detected(self, analyzer):
        old = "async def foo(): pass"
        new = "async def foo(x: int): pass"
        assert analyzer.is_structural_change(old, new) is True

    def test_extract_signature_classes(self, analyzer):
        code = "class A: pass\nclass B: pass"
        sig = analyzer.extract_signature(code)
        assert sorted(sig.classes) == ["A", "B"]

    def test_extract_signature_functions(self, analyzer):
        code = "def foo(a, b): pass\ndef bar(): pass"
        sig = analyzer.extract_signature(code)
        assert "foo" in sig.functions
        assert sig.functions["foo"] == ["a", "b"]

    def test_extract_signature_invalid_syntax_returns_empty(self, analyzer):
        sig = analyzer.extract_signature("def foo(: bad")
        assert sig.classes == []
        assert sig.functions == {}


class TestRegexStructureAnalyzer:
    @pytest.fixture
    def regex_analyzer(self):
        return RegexStructureAnalyzer()

    def test_ts_detects_class_change(self, regex_analyzer):
        old = "export class Foo {}"
        new = "export class Foo {}\nexport class Bar {}"
        assert regex_analyzer.is_structural_change("app.ts", old, new) is True

    def test_ts_no_change(self, regex_analyzer):
        code = "export class Foo {}\nexport function bar() {}"
        assert regex_analyzer.is_structural_change("app.ts", code, code) is False

    def test_go_detects_struct_change(self, regex_analyzer):
        old = "type User struct { Name string }"
        new = "type User struct { Name string }\ntype Admin struct { Role string }"
        assert regex_analyzer.is_structural_change("models.go", old, new) is True

    def test_unknown_extension_compares_full_content(self, regex_analyzer):
        old = "some content"
        new = "different content"
        assert regex_analyzer.is_structural_change("file.xyz", old, new) is True

    def test_unknown_extension_same_content(self, regex_analyzer):
        content = "same content"
        assert regex_analyzer.is_structural_change("file.xyz", content, content) is False
