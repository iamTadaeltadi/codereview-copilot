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
    """Serializer for GitHub collaborator data from the GitHub API."""
    login = serializers.CharField()
    id = serializers.IntegerField()
    avatar_url = serializers.URLField()
    html_url = serializers.URLField()
    type = serializers.CharField() # User or Organization
    site_admin = serializers.BooleanField()
    permissions = serializers.DictField(child=serializers.BooleanField()) # e.g. {"pull": true, "push": true, "admin": false}

# New Serializers
class PRSerializer(serializers.ModelSerializer):
    repository_id = serializers.PrimaryKeyRelatedField(
        queryset=DBRepository.objects.all(), source='repository', write_only=True
    )
    repository = RepositorySerializer(read_only=True) # For displaying repository details
    source = serializers.CharField(read_only=True, required=False)
    # Fields from GitHub API that are not directly on the model but useful for client
    user_login = serializers.CharField(read_only=True, required=False)
    user_avatar_url = serializers.URLField(read_only=True, required=False)
    created_at_gh = serializers.DateTimeField(read_only=True, required=False)
    updated_at_gh = serializers.DateTimeField(read_only=True, required=False)
    closed_at_gh = serializers.DateTimeField(read_only=True, required=False, allow_null=True)
    merged_at_gh = serializers.DateTimeField(read_only=True, required=False, allow_null=True)

    class Meta:
        model = PullRequest
        fields = [
            'id', 'repository', 'repository_id', # Standard fields
            'pr_github_id', 'pr_number', 'title', 'body', 'author_github_id', 
            'status', 'url', 'head_sha', 'base_sha', # Model fields
            'user_login', 'user_avatar_url', # Additional GitHub data
            'created_at_gh', 'updated_at_gh', 'closed_at_gh', 'merged_at_gh', # Additional GitHub data
            'created_at', 'updated_at', # Timestamps from TimestampMixin
            'source'
        ]
        read_only_fields = [
            'id', 'repository', 'created_at', 'updated_at', 'source',
            'user_login', 'user_avatar_url', 'created_at_gh', 'updated_at_gh', 
            'closed_at_gh', 'merged_at_gh'
        ]
    def to_representation(self, instance):
        """
        Augment the representation with non-model fields from initial_data
        when the serializer was initialized with `data=...`.
        """
        representation = super().to_representation(instance)

        # `self.initial_data` holds the original data passed to `data=`
        # `instance` here would be `validated_data` if initialized with `data=`
        if hasattr(self, 'initial_data') and self.initial_data:
            non_model_fields = [
                'user_login', 'user_avatar_url', 'created_at_gh',
                'updated_at_gh', 'closed_at_gh', 'merged_at_gh'
            ]
            for field_name in non_model_fields:
                if field_name in self.initial_data:
                    representation[field_name] = self.initial_data[field_name]
        
        # Set 'source' from context if provided, otherwise ensure it's present (e.g. as None)
        # if not already set by super() from a model field (which it isn't for 'source').
        if self.context.get('source'):
            representation['source'] = self.context.get('source')
        elif 'source' not in representation: # Default if not set by super and not in context
            representation['source'] = None

        return representation
class CommitSerializer(serializers.ModelSerializer):
    repository_id = serializers.PrimaryKeyRelatedField(
        queryset=DBRepository.objects.all(), source='repository', write_only=True
    )
    repository = RepositorySerializer(read_only=True) # For displaying repository details
    source = serializers.CharField(read_only=True, required=False)
    # Fields from GitHub API that are not directly on the model but useful for client
    author_name = serializers.CharField(read_only=True, required=False)
    author_email = serializers.EmailField(read_only=True, required=False)
    # author_date = serializers.DateTimeField(read_only=True, required=False) # Covered by model's timestamp
    committer_name = serializers.CharField(read_only=True, required=False, allow_null=True)
    committer_email = serializers.EmailField(read_only=True, required=False, allow_null=True)
    committed_date = serializers.DateTimeField(read_only=True, required=False, allow_null=True)


    class Meta:
        model = Commit
        fields = [
            'id', 'repository', 'repository_id', # Standard fields
            'commit_hash', 'message', 'author_github_id', 'committer_github_id', 
            'url', 'timestamp', # Model fields
            'author_name', 'author_email', # Additional GitHub data
            'committer_name', 'committer_email', 'committed_date', # Additional GitHub data
            'created_at', 'updated_at', # Timestamps from TimestampMixin
            'source'
        ]
        read_only_fields = [
            'id', 'repository', 'created_at', 'updated_at', 'source',
            'author_name', 'author_email', 
            'committer_name', 'committer_email', 'committed_date'
        ]
    def to_representation(self, instance):
        """
        Augment the representation with non-model fields from initial_data
        when the serializer was initialized with `data=...`.
        """
        representation = super().to_representation(instance)

        if hasattr(self, 'initial_data') and self.initial_data:
            non_model_fields = [
                'author_name', 'author_email',
                'committer_name', 'committer_email', 'committed_date'
            ]
            for field_name in non_model_fields:
                if field_name in self.initial_data:
                    representation[field_name] = self.initial_data[field_name]
        
        if self.context.get('source'):
            representation['source'] = self.context.get('source')
        elif 'source' not in representation: # Default if not set by super and not in context
            representation['source'] = None
            
        return representation
class ReviewFeedbackSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) # Feedback is always by the logged-in user
    review = serializers.PrimaryKeyRelatedField(queryset=Review.objects.all())

    class Meta:
        model = ReviewFeedback
        fields = ['id', 'review', 'user', 'rating', 'feedback', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def create(self, validated_data):
        # User is set from the request context in the view
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) # Comment is always by the logged-in user
    thread = serializers.PrimaryKeyRelatedField(queryset=Thread.objects.all())
    parent_comment = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.all(), allow_null=True, required=False)
    # replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'thread', 'user', 'comment', 'comment_data', 'type', 
            'parent_comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'thread', 'created_at', 'updated_at']

    def get_replies(self, obj):
        # Avoids excessively deep nesting or circular dependencies if not careful
        if self.context.get('depth', 0) > 10: # Control nesting depth
            return []
        
        # Create a new context with incremented depth
        new_context = self.context.copy()
        new_context['depth'] = self.context.get('depth', 0) + 1
