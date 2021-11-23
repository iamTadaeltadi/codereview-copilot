from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Create your models here.
class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class UserManager(BaseUserManager):
    def create_user(self, github_id, username, email=None, password=None, **extra_fields):
        if not github_id:
            raise ValueError('Users must have a GitHub ID')
        if not username:
            raise ValueError('Users must have a username')
        
        email = self.normalize_email(email) if email else None
        user = self.model(github_id=github_id, username=username, email=email, **extra_fields)
        user.set_password(password) # Handles hashing
        user.save(using=self._db)
        return user

    def create_superuser(self, github_id, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True) # Ensure is_admin is also set for superuser

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(github_id, username, email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin, TimestampMixin):
    github_id = models.CharField(max_length=255, unique=True, db_index=True)
    username = models.CharField(max_length=255, unique=True) # Assuming username from GitHub is unique
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True) # Email can be null from GitHub
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False) # Required by Django admin
    is_active = models.BooleanField(default=True) # Required by Django auth
    github_access_token = models.TextField(null=True, blank=True)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    is_ai_user = models.BooleanField(default=False) # New field

    objects = UserManager()

    USERNAME_FIELD = 'username' # Or 'github_id' if preferred for login
    REQUIRED_FIELDS = ['github_id'] # Fields prompted for when creating superuser, besides USERNAME_FIELD and password

    def __str__(self):
        return self.username

class Repository(TimestampMixin):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='repositories', on_delete=models.CASCADE)
    github_native_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True) # From Alembic: github_native_id
    repo_name = models.CharField(max_length=255) # FastAPI: repo_name
    repo_url = models.CharField(max_length=255) # FastAPI: repo_url, ensure this is the HTML URL
    description = models.TextField(null=True, blank=True) # FastAPI: description
    coding_standards = models.JSONField(null=True, blank=True) # FastAPI: coding_standards (List[str])
    code_metrics = models.JSONField(null=True, blank=True) # FastAPI: code_metrics (List[str])
    llm_preference = models.CharField(max_length=255, null=True, blank=True) # FastAPI: llm_preference
    webhook_url = models.CharField(max_length=255, null=True, blank=True) # FastAPI: webhook_url
    webhook_secret = models.CharField(max_length=255, null=True, blank=True) # For verifying incoming webhooks
    webhook_last_event_at = models.DateTimeField(null=True, blank=True) # FastAPI: webhook_last_event_at

    class Meta:
        unique_together = ('owner', 'repo_name') # Alembic: UniqueConstraint('owner_id', 'repo_name')
        verbose_name_plural = "Repositories"

    def __str__(self):
        return self.repo_name

class RepoCollaborator(TimestampMixin):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('contributor', 'Contributor'),
        ('member', 'Member'), # Added based on webhook handling
        ('admin', 'Admin'),   # Added based on webhook handling (GitHub permission)
        ('pull', 'Pull'),     # GitHub permission
        ('push', 'Push'),     # GitHub permission
    ]
    repository = models.ForeignKey(Repository, related_name='collaborators', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='repo_collaborations', on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES) # Alembic: role_enum

    class Meta:
        unique_together = ('repository', 'user') # Alembic: UniqueConstraint('repo_id', 'user_id')

    def __str__(self):
        return f"{self.user.username} - {self.repository.repo_name} ({self.role})"

class PullRequest(TimestampMixin):
    PR_STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('merged', 'Merged'),
    ]
    repository = models.ForeignKey(Repository, related_name='pull_requests', on_delete=models.CASCADE)
    pr_github_id = models.CharField(max_length=255,unique=True) # GitHub's own ID for the PR, not our DB ID.
    pr_number = models.IntegerField() # Alembic: pr_number
    title = models.CharField(max_length=255) # Alembic: pr_title
    author_github_id = models.CharField(max_length=255) # Alembic: pr_author (assuming this is github id)
    status = models.CharField(max_length=50, choices=PR_STATUS_CHOICES) # Alembic: pr_status_enum
    url = models.CharField(max_length=255) # Alembic: pr_url
    body = models.TextField(null=True, blank=True)
    head_sha = models.CharField(max_length=255, null=True, blank=True)
    base_sha = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"PR #{self.pr_number}: {self.title}"

class Commit(TimestampMixin):
    repository = models.ForeignKey(Repository, related_name='commits', on_delete=models.CASCADE)
    commit_hash = models.CharField(max_length=255) # Alembic: commit_sha
    author_github_id = models.CharField(max_length=255, null=True, blank=True) # Alembic: commit_author_id
    committer_github_id = models.CharField(max_length=255, null=True, blank=True) # Added from webhook logic
    message = models.TextField() # Alembic: commit_message (was String(255))
    url = models.CharField(max_length=255, null=True, blank=True) # Added from webhook logic
    timestamp = models.DateTimeField(null=True, blank=True) # Added from webhook logic

    class Meta:
        unique_together = ('repository', 'commit_hash')

    def __str__(self):
        return self.commit_hash[:12]

class Review(TimestampMixin):
    REVIEW_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('processing', 'Processing'), # Added from webhook logic
        ('pending_analysis', 'Pending Analysis') # Added from webhook logic
    ]
    repository = models.ForeignKey(Repository, related_name='reviews', on_delete=models.CASCADE)
    pull_request = models.ForeignKey(PullRequest, related_name='reviews', on_delete=models.CASCADE, null=True, blank=True)
    commit = models.ForeignKey(Commit, related_name='reviews', on_delete=models.CASCADE, null=True, blank=True)
    parent_review = models.ForeignKey('self', related_name='re_reviews', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    review_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True) # New field for storing error messages
    # user = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE) # Consider who owns/requested the review

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pull_request__isnull=False) | models.Q(commit__isnull=False),
                name='check_review_context' # Alembic: check_review_context
            )
        ]

    def __str__(self):
