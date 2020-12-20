"""Tests for the legacy ``core.views`` compatibility re-export module."""

import unittest

import django

django.setup()


class ViewsCompatModuleTests(unittest.TestCase):
    def test_legacy_views_module_reexports_view_callables(self):
        from core import views

        # The compatibility module should surface symbols from the split view
        # modules so stale ``core.views`` imports keep working.
        exported = [name for name in dir(views) if not name.startswith("_")]
        self.assertTrue(exported)
        # A representative symbol from one of the split modules.
        from core import auth_view

        auth_exports = [n for n in dir(auth_view) if not n.startswith("_")]
        self.assertTrue(set(auth_exports) & set(exported))


if __name__ == "__main__":
    unittest.main()
