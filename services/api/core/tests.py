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
