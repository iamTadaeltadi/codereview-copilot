"""Unit tests for the agent runtime diff formatting utilities."""

import unittest

try:
    from unittest.mock import MagicMock, patch

    from Utils.DiffFormatter import DiffFormatter, get_repo_default_branch

    _DIFFFORMATTER_AVAILABLE = True
except Exception:  # pragma: no cover - agent runtime deps absent in this env
    _DIFFFORMATTER_AVAILABLE = False

SAMPLE_DIFF = """diff --git a/foo.py b/foo.py
index 1111111..2222222 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 import os
-x = 1
+x = 2
+y = 3
diff --git a/bar.py b/bar.py
new file mode 100644
@@ -0,0 +1,2 @@
+def bar():
+    return 1
"""


@unittest.skipUnless(_DIFFFORMATTER_AVAILABLE, "agent runtime deps not installed")
class DiffFormatterTests(unittest.TestCase):
    def test_parse_and_format_returns_text_summary(self):
        formatter = DiffFormatter(SAMPLE_DIFF)
        output = formatter.parse_and_format()

        self.assertIsInstance(output, str)
        self.assertIn("foo.py", output)
        self.assertIn("bar.py", output)

    def test_parse_and_format_tracks_additions_and_deletions(self):
        formatter = DiffFormatter(SAMPLE_DIFF)
        formatter.parse_and_format()

        foo = formatter.formatted_files[0]
        self.assertEqual(foo["file_path"], "foo.py")
        change_types = {
            change["type"]
            for chunk in foo["chunks"]
            for change in chunk["changes"]
        }
        self.assertIn("addition", change_types)
        self.assertIn("deletion", change_types)
