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
        self.assertIn("context", change_types)

    def test_extract_file_path_strips_prefixes(self):
        formatter = DiffFormatter("")
        self.assertEqual(
            formatter._extract_file_path("diff --git a/src/app.py b/src/app.py"),
            "src/app.py",
        )

    def test_parse_chunk_header_extracts_line_numbers(self):
        formatter = DiffFormatter("")
        chunk = formatter._parse_chunk_header("@@ -10,5 +12,6 @@")
        self.assertEqual(chunk["old_start"], 10)
        self.assertEqual(chunk["new_start"], 12)
        self.assertEqual(chunk["changes"], [])


@unittest.skipUnless(_DIFFFORMATTER_AVAILABLE, "agent runtime deps not installed")
class GetRepoDefaultBranchTests(unittest.TestCase):
    @patch("Utils.DiffFormatter.requests.get")
    def test_returns_default_branch(self, mock_get):
        response = MagicMock()
        response.json.return_value = {"default_branch": "main"}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        self.assertEqual(get_repo_default_branch("octo", "repo"), "main")

    @patch("Utils.DiffFormatter.requests.get")
    def test_includes_authorization_header_when_token_present(self, mock_get):
        response = MagicMock()
        response.json.return_value = {"default_branch": "develop"}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        get_repo_default_branch("octo", "repo", user_github_token="tok")

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")

    @patch("Utils.DiffFormatter.requests.get")
    def test_raises_when_default_branch_missing(self, mock_get):
        response = MagicMock()
        response.json.return_value = {}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        with self.assertRaises(ValueError):
            get_repo_default_branch("octo", "repo")


if __name__ == "__main__":
    unittest.main()
