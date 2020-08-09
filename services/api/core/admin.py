from django.contrib import admin
from .models import (
    User, Repository, RepoCollaborator, PullRequest, Commit, 
    Review, Thread, Comment, LLMUsage, ReviewFeedback, WebhookEventLog
)

# Register your models here.

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'github_id', 'is_staff', 'is_admin', 'created_at')
    search_fields = ('username', 'email', 'github_id')
    list_filter = ('is_staff', 'is_admin', 'created_at')

@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('repo_name', 'owner', 'repo_url', 'github_native_id', 'created_at')
    search_fields = ('repo_name', 'owner__username', 'repo_url')
    list_filter = ('created_at', 'owner')
    raw_id_fields = ('owner',)

@admin.register(RepoCollaborator)
class RepoCollaboratorAdmin(admin.ModelAdmin):
    list_display = ('repository', 'user', 'role', 'created_at')
    search_fields = ('repository__repo_name', 'user__username', 'role')
    list_filter = ('role', 'created_at')
    raw_id_fields = ('repository', 'user')

@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'repository', 'pr_number', 'status', 'author_github_id', 'created_at')
    search_fields = ('title', 'repository__repo_name', 'author_github_id')
    list_filter = ('status', 'created_at')
    raw_id_fields = ('repository',)

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ('commit_hash_short', 'repository', 'message_short', 'author_github_id', 'timestamp')
    search_fields = ('commit_hash', 'repository__repo_name', 'author_github_id')
    list_filter = ('timestamp', 'repository')
    raw_id_fields = ('repository',)

    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_short.short_description = 'Message'

    def commit_hash_short(self, obj):
        return obj.commit_hash[:12]
    commit_hash_short.short_description = 'Commit Hash'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'repository', 'pull_request_info', 'commit_info', 'status', 'created_at')
    search_fields = ('repository__repo_name', 'pull_request__title', 'commit__commit_hash')
    list_filter = ('status', 'created_at')
    raw_id_fields = ('repository', 'pull_request', 'commit', 'parent_review')

    def pull_request_info(self, obj):
        if obj.pull_request:
            return f"PR #{obj.pull_request.pr_number} ({obj.pull_request.title[:30]}...)"
        return None
    pull_request_info.short_description = 'Pull Request'

    def commit_info(self, obj):
        if obj.commit:
            return obj.commit.commit_hash[:12]
        return None
    commit_info.short_description = 'Commit'

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'review_info', 'status', 'thread_id_short', 'created_at')
    search_fields = ('review__id', 'thread_id')
    list_filter = ('status', 'created_at')
    raw_id_fields = ('review',)
