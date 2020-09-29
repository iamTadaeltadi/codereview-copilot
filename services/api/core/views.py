"""Legacy compatibility module.

The canonical API implementation now lives in the split modules:
`auth_view.py`, `repository_view.py`, `pr_view.py`, `commit_view.py`,
`review_view.py`, `thread_view.py`, `user_view.py`, `admin_view.py`,
`llmusage_view.py`, and `webhook_view.py`.

This module re-exports those symbols so any stale imports of
`core.views` continue to work without carrying a second conflicting
implementation.
"""

from .admin_view import *  # noqa: F401,F403
from .auth_view import *  # noqa: F401,F403
from .commit_view import *  # noqa: F401,F403
from .llmusage_view import *  # noqa: F401,F403
from .pr_view import *  # noqa: F401,F403
from .repository_view import *  # noqa: F401,F403
from .review_view import *  # noqa: F401,F403
from .thread_view import *  # noqa: F401,F403
from .user_view import *  # noqa: F401,F403
from .webhook_view import *  # noqa: F401,F403
