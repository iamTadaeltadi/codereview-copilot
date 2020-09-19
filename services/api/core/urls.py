from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_view import AdminStatsView, AdminUserListView, AdminUserUpdateView
from .auth_view import GitHubLoginView, GitHubCallbackView, GitHubExchangeAuthTokenView
from .commit_view import CommitViewSet
from .llmusage_view import LLMUsageViewSet
from .pr_view import PullRequestViewSet
from .repository_view import RepositoryViewSet
from .review_view import ReviewViewSet
from .thread_view import ThreadViewSet
from .user_view import CurrentUserView, UserOrganizationsView, UserRepositoriesView
from .webhook_view import github_webhook

router = DefaultRouter()
router.register(r'repositories', RepositoryViewSet, basename='repository')
router.register(r'pull-requests', PullRequestViewSet, basename='pullrequest')
router.register(r'commits', CommitViewSet, basename='commit')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'llm-usage', LLMUsageViewSet, basename='llmusage')
router.register(r'threads', ThreadViewSet, basename='thread')

urlpatterns = [
    path('auth/github/login/', GitHubLoginView.as_view(), name='github_login'),
    path('auth/github/callback/', GitHubCallbackView.as_view(), name='github_callback'),
    path('auth/github/exchange/', GitHubExchangeAuthTokenView.as_view(), name='github_exchange_token'),
    path('user/', CurrentUserView.as_view(), name='current_user'),
    path('user/repos/', UserRepositoriesView.as_view(), name='user_repositories'),
    path('user/organizations/', UserOrganizationsView.as_view(), name='user_organizations'),
    path('', include(router.urls)),
    path('webhook/github/', github_webhook, name='github-webhook'),
    path('admin/stats/', AdminStatsView.as_view(), name='admin_stats'),
    path('admin/users/', AdminUserListView.as_view(), name='admin_list_users'),
    path('admin/users/<int:user_id>/', AdminUserUpdateView.as_view(), name='admin_update_user'),
]
