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
