import pytest
from src.trigger.diff_analyzer import DiffAnalyzer


@pytest.fixture
def analyzer():
    return DiffAnalyzer()


SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def foo():
     pass
+def bar():
+    pass
"""

NEW_FILE_DIFF = """\
diff --git a/src/new.py b/src/new.py
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,3 @@
+class NewClass:
+    pass
"""

DELETED_FILE_DIFF = """\
diff --git a/src/old.py b/src/old.py
deleted file mode 100644
index abc123..0000000
--- a/src/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-class OldClass:
-    pass
"""


class TestDiffAnalyzer:
    def test_parse_modified_file(self, analyzer):
        hunks = analyzer.parse_diff(SAMPLE_DIFF)
        assert len(hunks) == 1
        assert hunks[0].file_path == "src/main.py"

    def test_parse_new_file_has_no_old_content(self, analyzer):
        hunks = analyzer.parse_diff(NEW_FILE_DIFF)
        assert len(hunks) == 1
        assert hunks[0].old_content is None

    def test_parse_deleted_file_has_no_new_content(self, analyzer):
        hunks = analyzer.parse_diff(DELETED_FILE_DIFF)
        assert len(hunks) == 1
        assert hunks[0].new_content is None

    def test_parse_empty_diff(self, analyzer):
        assert analyzer.parse_diff("") == []

    def test_get_affected_folders_includes_parent(self, analyzer):
        hunks = analyzer.parse_diff(SAMPLE_DIFF)
        folders = analyzer.get_affected_folders(hunks)
        assert "src" in folders
        assert "" in folders  # 루트

    def test_get_affected_folders_nested(self, analyzer):
        diff = """\
diff --git a/src/api/v1/router.py b/src/api/v1/router.py
index abc..def 100644
--- a/src/api/v1/router.py
+++ b/src/api/v1/router.py
@@ -1 +1 @@
-x = 1
+x = 2
"""
        hunks = analyzer.parse_diff(diff)
        folders = analyzer.get_affected_folders(hunks)
        assert "src" in folders
        assert "src/api" in folders
        assert "src/api/v1" in folders
        assert "" in folders

    def test_multiple_files_in_diff(self, analyzer):
        multi_diff = SAMPLE_DIFF + "\n" + NEW_FILE_DIFF
        hunks = analyzer.parse_diff(multi_diff)
        assert len(hunks) == 2
        paths = {h.file_path for h in hunks}
        assert "src/main.py" in paths
        assert "src/new.py" in paths
