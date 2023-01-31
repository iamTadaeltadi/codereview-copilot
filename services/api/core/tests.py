from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from core.auth_view import GitHubCallbackView, GitHubLoginView
from core.models import Comment, PullRequest, RepoCollaborator, Repository, Review, Thread
from core.permissions import CanAccessRepository, IsAssignedReviewerForThread, IsRepositoryOwner
from core.serializers import RepositorySerializer, ThreadSerializer
from core.user_view import CurrentUserView, UserRepositoriesView


class UserManagerTests(TestCase):
    def test_create_user_requires_github_id(self):
        with self.assertRaisesMessage(ValueError, "Users must have a GitHub ID"):
            get_user_model().objects.create_user(github_id="", username="missing-id")

    def test_create_user_requires_username(self):
        with self.assertRaisesMessage(ValueError, "Users must have a username"):
            get_user_model().objects.create_user(github_id="1001", username="")


class RepositorySerializerTests(TestCase):
    def test_validate_repo_name_rejects_invalid_format(self):
        serializer = RepositorySerializer()
        with self.assertRaisesMessage(Exception, "repo_name must be in the format 'owner/repo'."):
            serializer.validate_repo_name("invalid-name")

    def test_validate_repo_name_accepts_owner_repo_format(self):
        serializer = RepositorySerializer()
        self.assertEqual(serializer.validate_repo_name("owner/repo"), "owner/repo")


class RepositoryApiTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(github_id="2001", username="owner-user", password="pw")
        self.collaborator = self.user_model.objects.create_user(github_id="2002", username="collab-user", password="pw")
        self.outsider = self.user_model.objects.create_user(github_id="2003", username="outsider-user", password="pw")
        self.client = APIClient()

    def test_create_repository_generates_webhook_fields_and_owner_collaborator(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/v1/repositories/",
            {
                "repo_name": "owner-user/sample-repo",
                "repo_url": "https://github.com/owner-user/sample-repo",
                "description": "Repository used for API coverage",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        repository = Repository.objects.get(repo_name="owner-user/sample-repo")
        self.assertEqual(repository.owner, self.owner)
        self.assertTrue(repository.webhook_secret)
        self.assertIn("/api/v1/webhook/github/", repository.webhook_url)
        self.assertTrue(
            RepoCollaborator.objects.filter(repository=repository, user=self.owner, role="owner").exists()
        )

    def test_list_repositories_only_returns_owned_or_collaborating_repositories(self):
        owned_repo = Repository.objects.create(
            owner=self.owner,
            repo_name="owner-user/owned-repo",
            repo_url="https://github.com/owner-user/owned-repo",
        )
        shared_repo = Repository.objects.create(
            owner=self.owner,
            repo_name="owner-user/shared-repo",
            repo_url="https://github.com/owner-user/shared-repo",
        )
        hidden_repo = Repository.objects.create(
            owner=self.outsider,
            repo_name="outsider-user/private-repo",
            repo_url="https://github.com/outsider-user/private-repo",
        )
        RepoCollaborator.objects.create(repository=shared_repo, user=self.collaborator, role="member")

        self.client.force_authenticate(user=self.collaborator)
        response = self.client.get("/api/v1/repositories/")

        self.assertEqual(response.status_code, 200)
        names = {item["repo_name"] for item in response.json()}
        self.assertIn(shared_repo.repo_name, names)
        self.assertNotIn(owned_repo.repo_name, names)
        self.assertNotIn(hidden_repo.repo_name, names)

    def test_regenerate_webhook_secret_rotates_secret(self):
        repository = Repository.objects.create(
            owner=self.owner,
            repo_name="owner-user/rotating-repo",
            repo_url="https://github.com/owner-user/rotating-repo",
            webhook_secret="old-secret",
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(f"/api/v1/repositories/{repository.id}/webhook/regenerate-secret/")

        repository.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(repository.webhook_secret, "old-secret")

    def test_by_github_id_returns_repository_for_authorized_collaborator(self):
        repository = Repository.objects.create(
            owner=self.owner,
            github_native_id=999,
            repo_name="owner-user/by-id-repo",
            repo_url="https://github.com/owner-user/by-id-repo",
        )
        RepoCollaborator.objects.create(repository=repository, user=self.collaborator, role="member")
        self.client.force_authenticate(user=self.collaborator)

        response = self.client.get("/api/v1/repositories/by-github-id/999/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["repo_name"], repository.repo_name)


class PermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(github_id="4001", username="perm-owner", password="pw")
        self.member = self.user_model.objects.create_user(
            github_id="4002", username="perm-member", password="pw", github_access_token="token"
        )
        self.other = self.user_model.objects.create_user(github_id="4003", username="perm-other", password="pw")
        self.repository = Repository.objects.create(
            owner=self.owner,
            repo_name="perm-owner/perm-repo",
            repo_url="https://github.com/perm-owner/perm-repo",
        )
        self.pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="pr-perm-1",
            pr_number=8,
            title="Permission coverage",
            author_github_id=self.owner.github_id,
            status="open",
            url="https://github.com/perm-owner/perm-repo/pull/8",
        )
        self.review = Review.objects.create(repository=self.repository, pull_request=self.pull_request)
        self.thread = Thread.objects.create(review=self.review, thread_id="thread-1")

    def test_is_repository_owner_allows_owner(self):
        request = self.factory.get("/")
        request.user = self.owner
        self.assertTrue(IsRepositoryOwner().has_object_permission(request, None, self.repository))

    def test_can_access_repository_allows_db_collaborator(self):
        RepoCollaborator.objects.create(repository=self.repository, user=self.member, role="member")
        request = self.factory.get("/")
        request.user = self.member
        self.assertTrue(CanAccessRepository().has_object_permission(request, None, self.repository))

    @patch("core.permissions.get_repo_collaborators_from_github")
    def test_can_access_repository_syncs_github_collaborator(self, mock_get_collabs):
        mock_get_collabs.return_value = [
            {"id": int(self.member.github_id), "permissions": {"push": True}}
        ]
        request = self.factory.get("/")
        request.user = self.member

        allowed = CanAccessRepository().has_object_permission(request, None, self.repository)

        self.assertTrue(allowed)
        self.assertTrue(RepoCollaborator.objects.filter(repository=self.repository, user=self.member).exists())

    @patch("core.permissions.get_single_pull_request_from_github")
    def test_is_assigned_reviewer_for_thread_uses_requested_reviewers(self, mock_get_pr):
        mock_get_pr.return_value = {
            "requested_reviewers": [{"id": int(self.member.github_id), "login": self.member.username}]
        }
        request = self.factory.get("/")
        request.user = self.member

        allowed = IsAssignedReviewerForThread().has_object_permission(request, None, self.thread)

        self.assertTrue(allowed)


class UserViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            github_id="5001",
            username="view-user",
            password="pw",
            github_access_token="token-123",
            email="view@example.com",
        )

    def test_current_user_view_returns_authenticated_user(self):
        request = self.factory.get("/api/v1/user/")
        force_authenticate(request, user=self.user)

        response = CurrentUserView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], self.user.username)

    @patch("core.user_view.get_user_repos_from_github")
    def test_user_repositories_view_marks_registered_repositories(self, mock_get_repos):
        repository = Repository.objects.create(
            owner=self.user,
            github_native_id=321,
            repo_name="view-user/registered-repo",
            repo_url="https://github.com/view-user/registered-repo",
        )
        mock_get_repos.return_value = [
            {
                "id": 321,
                "name": "registered-repo",
                "full_name": repository.repo_name,
                "private": False,
                "html_url": repository.repo_url,
                "description": "registered",
                "owner": {"login": self.user.username},
            },
            {
                "id": 322,
                "name": "other-repo",
                "full_name": f"{self.user.username}/other-repo",
                "private": True,
                "html_url": "https://github.com/view-user/other-repo",
                "description": "other",
                "owner": {"login": self.user.username},
            },
        ]
        request = self.factory.get("/api/v1/user/repos/?page=1&per_page=30")
        force_authenticate(request, user=self.user)

        response = UserRepositoriesView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        registered = {item["id"]: item for item in response.data}
        self.assertTrue(registered[321]["is_registered_in_system"])
        self.assertEqual(registered[321]["system_id"], repository.id)
        self.assertFalse(registered[322]["is_registered_in_system"])

    def test_user_repositories_view_requires_github_token(self):
        self.user.github_access_token = None
        self.user.save(update_fields=["github_access_token"])
        request = self.factory.get("/api/v1/user/repos/")
        force_authenticate(request, user=self.user)

        response = UserRepositoriesView.as_view()(request)

        self.assertEqual(response.status_code, 400)


class AuthViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.auth_view.generate_oauth_state", return_value="oauth-state")
    @patch("core.auth_view.get_github_oauth_redirect_url", return_value="https://github.com/login/oauth/authorize?state=oauth-state")
    def test_github_login_view_redirects_to_github(self, mock_redirect_url, mock_generate_state):
        request = self.factory.get("/api/v1/auth/github/login/")

        response = GitHubLoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("github.com/login/oauth/authorize", response.url)
        mock_generate_state.assert_called_once()
        mock_redirect_url.assert_called_once_with("oauth-state")

    @patch("core.auth_view.validate_oauth_state", return_value=True)
    @patch("core.auth_view.exchange_code_for_github_token", return_value="gh-token")
    @patch("core.auth_view.get_github_user_info")
    def test_github_callback_creates_user_and_redirects_with_token(self, mock_get_user, mock_exchange, mock_validate):
        mock_get_user.return_value = {"id": 7001, "login": "gh-user", "email": "gh@example.com"}
        request = self.factory.get("/api/v1/auth/github/callback/?code=abc&state=valid")
        request.session = {}

        response = GitHubCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/callback?token=", response.url)
        self.assertTrue(get_user_model().objects.filter(github_id="7001", username="gh-user").exists())

    @patch("core.auth_view.validate_oauth_state", return_value=False)
    def test_github_callback_rejects_invalid_state(self, mock_validate):
        request = self.factory.get("/api/v1/auth/github/callback/?code=abc&state=invalid")
        request.session = {}

        response = GitHubCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("Invalid%20OAuth%20state.", response.url)


class ThreadSerializerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(github_id="8001", username="thread-user", password="pw")
        self.repository = Repository.objects.create(
            owner=self.user,
            repo_name="thread-user/thread-repo",
            repo_url="https://github.com/thread-user/thread-repo",
        )
        self.pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="thread-pr-1",
            pr_number=15,
            title="Thread review",
            author_github_id=self.user.github_id,
            status="open",
            url="https://github.com/thread-user/thread-repo/pull/15",
        )
        self.review = Review.objects.create(repository=self.repository, pull_request=self.pull_request)
        self.thread = Thread.objects.create(review=self.review, thread_id="thread-serializer")

    def test_thread_serializer_reports_comment_count(self):
        Comment.objects.create(thread=self.thread, user=self.user, comment="one", type="note")
        Comment.objects.create(thread=self.thread, user=self.user, comment="two", type="request")

        serializer = ThreadSerializer(self.thread)

        self.assertEqual(serializer.data["comment_count"], 2)

    def test_thread_serializer_filters_comment_data_for_non_last_comment(self):
        Comment.objects.create(
            thread=self.thread,
            user=self.user,
            comment="first",
            type="note",
            comment_data={
                "repo": "thread-repo",
                "feedback": "keep",
                "messages": ["hidden"],
                "original_review": {"a": 1},
            },
        )
        Comment.objects.create(
            thread=self.thread,
            user=self.user,
            comment="second",
            type="response",
            comment_data={
                "repo": "thread-repo",
                "feedback": "keep",
                "messages": ["shown"],
                "original_review": {"a": 1},
                "updated_review": {"b": 2},
            },
        )

        serializer = ThreadSerializer(self.thread)
        comments = serializer.data["comments"]

        self.assertEqual(comments[0]["comment_data"], {"repo": "thread-repo", "feedback": "keep"})
        self.assertIn("messages", comments[1]["comment_data"])
        self.assertIn("updated_review", comments[1]["comment_data"])


class ReviewModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(github_id="3001", username="review-user", password="pw")
        self.repository = Repository.objects.create(
            owner=self.user,
            repo_name="review-user/review-repo",
            repo_url="https://github.com/review-user/review-repo",
        )

    def test_review_can_be_created_for_pull_request_context(self):
        pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="9001",
            pr_number=12,
            title="Add review flow",
            author_github_id=self.user.github_id,
            status="open",
            url="https://github.com/review-user/review-repo/pull/12",
        )

        review = Review.objects.create(
            repository=self.repository,
            pull_request=pull_request,
            status="pending",
            review_data={"summary": "pending analysis"},
        )

        self.assertEqual(review.pull_request, pull_request)
        self.assertEqual(str(review), "Review for PR #12")


class PermissionNegativeTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(github_id="4101", username="negative-owner", password="pw")
        self.other = self.user_model.objects.create_user(github_id="4102", username="negative-other", password="pw")
        self.repository = Repository.objects.create(
            owner=self.owner,
            repo_name="negative-owner/negative-repo",
            repo_url="https://github.com/negative-owner/negative-repo",
        )
        self.pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="neg-pr-1",
            pr_number=21,
            title="Negative permissions",
            author_github_id=self.owner.github_id,
            status="open",
            url="https://github.com/negative-owner/negative-repo/pull/21",
        )
        self.review = Review.objects.create(repository=self.repository, pull_request=self.pull_request)
        self.thread = Thread.objects.create(review=self.review, thread_id="negative-thread")

    def test_is_repository_owner_rejects_non_owner(self):
        request = self.factory.get("/")
        request.user = self.other
        self.assertFalse(IsRepositoryOwner().has_object_permission(request, None, self.repository))

    def test_can_access_repository_rejects_user_without_token_or_membership(self):
        request = self.factory.get("/")
        request.user = self.other
        self.assertFalse(CanAccessRepository().has_object_permission(request, None, self.repository))

    @patch("core.permissions.get_repo_collaborators_from_github", side_effect=Exception("github down"))
    def test_can_access_repository_returns_false_when_github_lookup_fails(self, _mock_get_collabs):
        self.other.github_access_token = "token"
        self.other.save(update_fields=["github_access_token"])
        request = self.factory.get("/")
        request.user = self.other
        self.assertFalse(CanAccessRepository().has_object_permission(request, None, self.repository))

    def test_is_assigned_reviewer_for_thread_rejects_non_thread_objects(self):
        request = self.factory.get("/")
        request.user = self.other
        self.assertFalse(IsAssignedReviewerForThread().has_object_permission(request, None, self.repository))

    def test_is_assigned_reviewer_for_thread_rejects_user_without_token(self):
        request = self.factory.get("/")
        request.user = self.other
        self.assertFalse(IsAssignedReviewerForThread().has_object_permission(request, None, self.thread))

    @patch("core.permissions.get_single_pull_request_from_github", return_value={"requested_reviewers": []})
    def test_is_assigned_reviewer_for_thread_rejects_unassigned_user(self, _mock_get_pr):
        self.other.github_access_token = "token"
        self.other.save(update_fields=["github_access_token"])
        request = self.factory.get("/")
        request.user = self.other
        self.assertFalse(IsAssignedReviewerForThread().has_object_permission(request, None, self.thread))


class UserOrganizationViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            github_id="5101",
            username="org-view-user",
            password="pw",
            github_access_token="token-xyz",
        )

    @patch("core.user_view.get_user_orgs_from_github")
    def test_user_organizations_view_returns_serialized_orgs(self, mock_get_orgs):
        from core.user_view import UserOrganizationsView

        mock_get_orgs.return_value = [
            {
                "login": "afterquery",
                "id": 11,
                "node_id": "abc",
                "url": "https://api.github.com/orgs/afterquery",
                "repos_url": "https://api.github.com/orgs/afterquery/repos",
                "events_url": "https://api.github.com/orgs/afterquery/events",
                "hooks_url": "https://api.github.com/orgs/afterquery/hooks",
                "issues_url": "https://api.github.com/orgs/afterquery/issues{/number}",
                "members_url": "https://api.github.com/orgs/afterquery/members{/member}",
                "public_members_url": "https://api.github.com/orgs/afterquery/public_members{/member}",
                "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
                "description": "AI review",
            }
        ]
        request = self.factory.get("/api/v1/user/orgs/?page=2&per_page=10")
        force_authenticate(request, user=self.user)

        response = UserOrganizationsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["login"], "afterquery")
        mock_get_orgs.assert_called_once_with("token-xyz", page=2, per_page=10)

    def test_user_organizations_view_requires_token(self):
        from core.user_view import UserOrganizationsView

        self.user.github_access_token = None
        self.user.save(update_fields=["github_access_token"])
        request = self.factory.get("/api/v1/user/orgs/")
        force_authenticate(request, user=self.user)

        response = UserOrganizationsView.as_view()(request)

        self.assertEqual(response.status_code, 400)

    @patch("core.user_view.get_user_orgs_from_github", side_effect=Exception("boom"))
    def test_user_organizations_view_handles_unexpected_errors(self, _mock_get_orgs):
        from core.user_view import UserOrganizationsView

        request = self.factory.get("/api/v1/user/orgs/")
        force_authenticate(request, user=self.user)

        response = UserOrganizationsView.as_view()(request)

        self.assertEqual(response.status_code, 500)


class AuthViewExtraTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_github_callback_rejects_missing_code(self):
        request = self.factory.get("/api/v1/auth/github/callback/?state=only-state")
        request.session = {}

        response = GitHubCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("Missing%20code%20or%20state", response.url)

    @patch("core.auth_view.validate_oauth_state", return_value=True)
    @patch("core.auth_view.exchange_code_for_github_token", side_effect=Exception("token exchange failed"))
    def test_github_callback_redirects_to_error_when_exchange_fails(self, _mock_exchange, _mock_validate):
        request = self.factory.get("/api/v1/auth/github/callback/?code=abc&state=valid")
        request.session = {}

        response = GitHubCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("An%20unexpected%20error%20occurred", response.url)

    @patch("core.auth_view.validate_oauth_state", return_value=True)
    @patch("core.auth_view.exchange_code_for_github_token", return_value=None)
    def test_github_callback_redirects_to_error_when_token_missing(self, _mock_exchange, _mock_validate):
        request = self.factory.get("/api/v1/auth/github/callback/?code=abc&state=valid")
        request.session = {}

        response = GitHubCallbackView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("Failed%20to%20retrieve%20GitHub%20access%20token", response.url)


class SerializerRepresentationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(github_id="9101", username="serializer-user", password="pw")
        self.repository = Repository.objects.create(
            owner=self.user,
            repo_name="serializer-user/serializer-repo",
            repo_url="https://github.com/serializer-user/serializer-repo",
        )

    def test_github_repository_serializer_sets_registration_defaults(self):
        from core.serializers import GitHubRepositorySerializer

        serializer = GitHubRepositorySerializer(
            {
                "id": 1,
                "name": "serializer-repo",
                "full_name": "serializer-user/serializer-repo",
                "private": False,
                "html_url": "https://github.com/serializer-user/serializer-repo",
                "owner": {"login": "serializer-user"},
            }
        )

        self.assertFalse(serializer.data["is_registered_in_system"])

    def test_github_organization_serializer_allows_blank_description(self):
        from core.serializers import GitHubOrganizationSerializer

        serializer = GitHubOrganizationSerializer(
            {
                "login": "afterquery",
                "id": 5,
                "node_id": "node-5",
                "url": "https://api.github.com/orgs/afterquery",
                "repos_url": "https://api.github.com/orgs/afterquery/repos",
                "events_url": "https://api.github.com/orgs/afterquery/events",
                "hooks_url": "https://api.github.com/orgs/afterquery/hooks",
                "issues_url": "https://api.github.com/orgs/afterquery/issues{/number}",
                "members_url": "https://api.github.com/orgs/afterquery/members{/member}",
                "public_members_url": "https://api.github.com/orgs/afterquery/public_members{/member}",
                "avatar_url": "https://avatars.githubusercontent.com/u/5?v=4",
                "description": "",
            }
        )

        self.assertEqual(serializer.data["description"], "")

    def test_pr_serializer_representation_includes_initial_data_fields(self):
        from core.serializers import PRSerializer

        serializer = PRSerializer(
            data={
                "repository_id": self.repository.id,
                "pr_github_id": "1",
                "pr_number": 44,
                "title": "Serializer PR",
                "body": "Details",
                "author_github_id": self.user.github_id,
                "status": "open",
                "url": "https://github.com/serializer-user/serializer-repo/pull/44",
                "head_sha": "abc",
                "base_sha": "def",
                "user_login": "serializer-user",
                "user_avatar_url": "https://avatars.githubusercontent.com/u/9101?v=4",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.data["user_login"], "serializer-user")
        self.assertEqual(serializer.data["source"], None)

    def test_pr_serializer_representation_uses_context_source(self):
        from core.serializers import PRSerializer

        pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="5",
            pr_number=45,
            title="Context PR",
            author_github_id=self.user.github_id,
            status="open",
            url="https://github.com/serializer-user/serializer-repo/pull/45",
        )
        serializer = PRSerializer(pull_request, context={"source": "github"})

        self.assertEqual(serializer.data["source"], "github")

    def test_commit_serializer_representation_includes_initial_data_fields(self):
        from core.serializers import CommitSerializer

        serializer = CommitSerializer(
            data={
                "repository_id": self.repository.id,
                "commit_hash": "abc1234",
                "message": "Commit serializer",
                "url": "https://github.com/serializer-user/serializer-repo/commit/abc1234",
                "timestamp": "2026-05-19T00:00:00Z",
                "author_name": "Serializer User",
                "author_email": "serializer@example.com",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.data["author_name"], "Serializer User")
        self.assertEqual(serializer.data["source"], None)

    def test_commit_serializer_representation_uses_context_source(self):
        from core.serializers import CommitSerializer
        from core.models import Commit

        commit = Commit.objects.create(
            repository=self.repository,
            commit_hash="def5678",
            message="Context commit",
            url="https://github.com/serializer-user/serializer-repo/commit/def5678",
            timestamp="2026-05-19T00:00:00Z",
        )
        serializer = CommitSerializer(commit, context={"source": "db"})

        self.assertEqual(serializer.data["source"], "db")

    def test_review_feedback_serializer_create_uses_request_user(self):
        from core.serializers import ReviewFeedbackSerializer

        pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="77",
            pr_number=77,
            title="Feedback PR",
            author_github_id=self.user.github_id,
            status="open",
            url="https://github.com/serializer-user/serializer-repo/pull/77",
        )
        review = Review.objects.create(repository=self.repository, pull_request=pull_request)
        request = RequestFactory().post("/")
        request.user = self.user
        serializer = ReviewFeedbackSerializer(
            data={"review": review.id, "rating": 5, "feedback": "Useful"},
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        feedback = serializer.save()

        self.assertEqual(feedback.user, self.user)

    def test_comment_serializer_create_uses_request_user(self):
        from core.serializers import CommentSerializer

        pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="88",
            pr_number=88,
            title="Comment PR",
            author_github_id=self.user.github_id,
            status="open",
            url="https://github.com/serializer-user/serializer-repo/pull/88",
        )
        review = Review.objects.create(repository=self.repository, pull_request=pull_request)
        thread = Thread.objects.create(review=review, thread_id="comment-thread")
        request = RequestFactory().post("/")
        request.user = self.user
        serializer = CommentSerializer(
            data={"thread": thread.id, "comment": "Looks good", "type": "note"},
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        comment = serializer.save()

        self.assertEqual(comment.user, self.user)


class RepositoryRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            github_id="9201",
            username="route-owner",
            password="pw",
            github_access_token="token-route",
        )
        self.other = get_user_model().objects.create_user(github_id="9202", username="route-other", password="pw")
        self.repository = Repository.objects.create(
            owner=self.user,
            repo_name="route-owner/route-repo",
            repo_url="https://github.com/route-owner/route-repo",
            github_native_id=4040,
            webhook_secret="secret-123",
            webhook_url="https://api.example.com/api/v1/webhook/github/",
        )
        self.client = APIClient()

    def test_repository_list_requires_authentication(self):
        response = self.client.get("/api/v1/repositories/")
        self.assertEqual(response.status_code, 401)

    def test_repository_create_requires_authentication(self):
        response = self.client.post("/api/v1/repositories/", {"repo_name": "a/b", "repo_url": "https://github.com/a/b"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_registered_collaborators_returns_system_collaborators(self):
        RepoCollaborator.objects.create(repository=self.repository, user=self.user, role="owner")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/registered-collaborators/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["role"], "owner")

    def test_collaborators_requires_github_token(self):
        self.user.github_access_token = None
        self.user.save(update_fields=["github_access_token"])
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/collaborators/")

        self.assertEqual(response.status_code, 400)

    @patch("core.repository_view.get_repo_collaborators_from_github")
    def test_collaborators_returns_github_collaborators(self, mock_get_collabs):
        mock_get_collabs.return_value = [
            {
                "login": self.user.username,
                "id": int(self.user.github_id),
                "avatar_url": "https://avatars.githubusercontent.com/u/9201?v=4",
                "html_url": "https://github.com/route-owner",
                "type": "User",
                "site_admin": False,
                "permissions": {"pull": True, "push": True, "admin": False},
            }
        ]
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/collaborators/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["login"], self.user.username)
        self.assertTrue(RepoCollaborator.objects.filter(repository=self.repository, user=self.user).exists())

    def test_webhook_status_reports_recent_event_count(self):
        from core.models import WebhookEventLog

        WebhookEventLog.objects.create(repository=self.repository, event_id="evt-1", event_type="push", status="processed", payload={}, processed_at="2026-05-19T00:00:00Z")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/webhook/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recent_event_count"], 1)

    def test_by_github_id_rejects_unauthorized_user(self):
        self.client.force_authenticate(user=self.other)

        response = self.client.get(f"/api/v1/repositories/by-github-id/{self.repository.github_native_id}/")

        self.assertEqual(response.status_code, 403)

    def test_retrieve_pull_request_returns_database_record(self):
        pull_request = PullRequest.objects.create(
            repository=self.repository,
            pr_github_id="db-1",
            pr_number=66,
            title="DB PR",
            author_github_id=self.user.github_id,
            status="open",
            url="https://github.com/route-owner/route-repo/pull/66",
        )
        RepoCollaborator.objects.create(repository=self.repository, user=self.user, role="owner")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/pulls/{pull_request.pr_number}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "db")

    @patch("core.repository_view.get_single_pull_request_from_github")
    def test_retrieve_pull_request_falls_back_to_github(self, mock_get_pr):
        mock_get_pr.return_value = {
            "id": 501,
            "number": 67,
            "title": "GitHub PR",
            "body": "Body",
            "state": "open",
            "html_url": "https://github.com/route-owner/route-repo/pull/67",
            "user": {"id": int(self.user.github_id), "login": self.user.username, "avatar_url": "https://avatars.githubusercontent.com/u/9201?v=4"},
            "head": {"sha": "abc"},
            "base": {"sha": "def"},
            "created_at": "2026-05-19T00:00:00Z",
            "updated_at": "2026-05-19T00:00:00Z",
            "closed_at": None,
            "merged_at": None,
        }
        RepoCollaborator.objects.create(repository=self.repository, user=self.user, role="owner")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/pulls/67/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "github")
        self.assertEqual(response.json()["title"], "GitHub PR")

    def test_retrieve_commit_returns_database_record(self):
        from core.models import Commit

        Commit.objects.create(
            repository=self.repository,
            commit_hash="abc1234",
            message="DB commit",
            url="https://github.com/route-owner/route-repo/commit/abc1234",
            timestamp="2026-05-19T00:00:00Z",
        )
        RepoCollaborator.objects.create(repository=self.repository, user=self.user, role="owner")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/commits/sha/abc1234/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "db")

    @patch("core.repository_view.get_single_commit_from_github")
    def test_retrieve_commit_falls_back_to_github(self, mock_get_commit):
        mock_get_commit.return_value = {
            "sha": "def5678",
            "html_url": "https://github.com/route-owner/route-repo/commit/def5678",
            "commit": {
                "message": "GitHub commit",
                "author": {"name": "Route Owner", "email": "route-owner@example.com", "date": "2026-05-19T00:00:00Z"},
                "committer": {"name": "Route Owner", "email": "route-owner@example.com", "date": "2026-05-19T00:00:00Z"},
            },
            "author": {"id": int(self.user.github_id)},
            "committer": {"id": int(self.user.github_id)},
        }
        RepoCollaborator.objects.create(repository=self.repository, user=self.user, role="owner")
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/repositories/{self.repository.id}/commits/sha/def5678/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["commit_hash"], "def5678")
        self.assertEqual(response.json()["author_name"], "Route Owner")
