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
