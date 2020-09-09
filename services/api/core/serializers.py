from rest_framework import serializers
from .models import User, Repository as DBRepository, RepoCollaborator, PullRequest, Commit, Review, Thread, Comment, LLMUsage, ReviewFeedback, WebhookEventLog

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_admin', 'github_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'github_id', 'created_at', 'updated_at']

class RepositorySerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    # For request (create/update), owner will be set from the request user, not from input data.
    # For response, owner will be serialized.
    
    # Fields from FastAPI RepositoryCreate/Update/Response
    # repo_name, repo_url, description, github_native_id, coding_standards, code_metrics, llm_preference, webhook_url

    # webhook_url will be generated on creation, can be read_only for updates unless explicitly allowed.
    webhook_url = serializers.CharField(read_only=True, allow_null=True)
    webhook_secret = serializers.CharField(read_only=True)

    class Meta:
        model = DBRepository
        fields = [
            'id', 'owner', 'repo_name', 'repo_url', 'description', 'github_native_id',
            'coding_standards', 'code_metrics', 'llm_preference', 'webhook_url',
            'created_at', 'updated_at', 'webhook_last_event_at', 'webhook_secret'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at', 'webhook_url', 'webhook_secret', 'webhook_last_event_at']

    def create(self, validated_data):
        # The owner is set in the view from request.user
        # Webhook URL is also generated in the view after initial save
        return super().create(validated_data)
    
    def validate_repo_name(self, value):
        if '/' not in value or len(value.split('/')) != 2:
            raise serializers.ValidationError("repo_name must be in the format 'owner/repo'.")
        return value

class RepoCollaboratorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    repo_id = serializers.PrimaryKeyRelatedField(queryset=DBRepository.objects.all(), source='repository')

    class Meta:
        model = RepoCollaborator
        fields = ['id', 'repo_id', 'user', 'role', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

class GitHubRepositorySerializer(serializers.Serializer):
    """Serializer for GitHub repo data that might not directly map to our model fields yet."""
    id = serializers.IntegerField() # GitHub's native ID
    name = serializers.CharField()
    full_name = serializers.CharField()
    private = serializers.BooleanField()
    html_url = serializers.URLField()
    description = serializers.CharField(allow_null=True, required=False)
    owner_login = serializers.CharField(source='owner.login') # Example of accessing nested data
    permissions = serializers.DictField(child=serializers.BooleanField(), required=False) # e.g. {"admin": true, "push": true, "pull": true}
    is_registered_in_system = serializers.BooleanField(default=False)
    system_id = serializers.IntegerField(allow_null=True, required=False)

class GitHubOrganizationSerializer(serializers.Serializer):
    """Serializer for GitHub organization data."""
    login = serializers.CharField()
    id = serializers.IntegerField()
    node_id = serializers.CharField()
    url = serializers.URLField()
    repos_url = serializers.URLField()
    events_url = serializers.URLField()
    hooks_url = serializers.URLField()
    issues_url = serializers.URLField()
    members_url = serializers.URLField()
    public_members_url = serializers.URLField()
    avatar_url = serializers.URLField()
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)

class GitHubCollaboratorSerializer(serializers.Serializer):
