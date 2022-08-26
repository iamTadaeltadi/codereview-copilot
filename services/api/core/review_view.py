from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .tasks.review_tasks import process_pr_review
from .models import (
    Review as ReviewModel,
    Thread as ThreadModel,
    LLMUsage as LLMUsageModel,
    ReviewFeedback,
)
from .serializers import (
    ReviewSerializer, ThreadSerializer, ReviewFeedbackSerializer
)
from .services import (
    LangGraphService
)
from django.conf import settings
from django.db.models import Q 
import logging
from .permissions import (CanAccessRepository)
from core.langgraph_client.client import LangGraphClient
import asyncio
logger = logging.getLogger(__name__)

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'],url_path='history', permission_classes=[IsAuthenticated, CanAccessRepository])
    def history(self, request, pk=None):
        """
        Get review history for a PR or commit with thread information.
        """
        context_param = request.query_params.get('context')  # 'pr' or 'commit'
        item_id = request.query_params.get('id')  # PR or Commit ID
        
        if not context_param or not item_id:
            return Response(
                {"detail": "Context and ID parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reviews_qs = ReviewModel.objects.none()
        if context_param == 'pr':
            reviews_qs = ReviewModel.objects.filter(pull_request_id=item_id)
        elif context_param == 'commit':
            reviews_qs = ReviewModel.objects.filter(commit__commit_hash=item_id)
        else:
            return Response(
                {"detail": "Invalid context. Must be 'pr' or 'commit'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reviews_qs = reviews_qs.prefetch_related('threads', 'threads__comments')
        
        # Use default serializer context, ReviewSerializer includes threads by default if present in Meta
        serializer_context = self.get_serializer_context()
        serializer = self.get_serializer(reviews_qs.order_by('-created_at'), many=True, context=serializer_context)
        
        response_data = serializer.data # This is a list of serialized review objects
        
        fields_to_remove_from_each_review = [
            'repository', 
            'pull_request', 
            'review_data', 
            'threads',
            'thread_count' # Also remove thread_count as it's related to threads
        ]
        
        cleaned_response_data = []
        for review_item_data in response_data:
            for key_to_remove in fields_to_remove_from_each_review:
                review_item_data.pop(key_to_remove, None)
            cleaned_response_data.append(review_item_data)
            
        return Response(cleaned_response_data)
    
    def get_queryset(self):
        return ReviewModel.objects.filter(
            Q(repository__owner=self.request.user) |
            Q(repository__collaborators__user=self.request.user)
        ).distinct()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Serialize and add thread information if threads exist
        # It's better to check instance.threads.exists() or instance.threads.all()
        if instance.threads.exists(): 
            # Assuming ThreadSerializer is available and imported correctly
            # Pass the request context to the ThreadSerializer if it needs it (e.g., for HyperlinkedRelatedField)
            serializer_context = self.get_serializer_context()
            threads_data = ThreadSerializer(instance.threads.all(), many=True, context=serializer_context).data
            data['threads'] = threads_data
        else:
            # Optionally, ensure 'threads' key is present even if empty
            data['threads'] = []
        return Response(data)
    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        review = self.get_object()
        serializer = ReviewFeedbackSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        feedback = serializer.save(review=review, user=request.user)
        thread = review.threads.order_by('created_at').first()
        if not thread or not thread.thread_id:
            return Response(
                {"detail": "No LangGraph thread is available for this review yet."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            repo_settings = {
                'llm_preference': review.repository.llm_preference or settings.DEFAULT_LLM_MODEL,
                'coding_standards': review.repository.coding_standards or [],
                'code_metrics': review.repository.code_metrics or [],
            }
            review_data = ReviewSerializer(review, context=self.get_serializer_context()).data
            feedback_result = LangGraphService().handle_feedback(
                thread_id=thread.thread_id,
                feedback=feedback.feedback,
                user_id=str(request.user.github_id),
                is_first_message=thread.comments.count() <= 1,
                review_data=review_data,
                repo_settings=repo_settings,
            )
            return Response(
                {
                    'feedback_id': feedback.id,
                    'feedback_data': feedback_result.get('feedback_data', {}),
                    'token_usage': feedback_result.get('token_usage', {}),
                }
            )
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}", exc_info=True)
            return Response(
                {"detail": "Error processing feedback"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    @action(detail=True, methods=['get'])
    def threads(self, request, pk=None):
        review = self.get_object() # pk is reviewId
        threads_qs = ThreadModel.objects.filter(review=review)
        serializer = ThreadSerializer(threads_qs, many=True) # Assuming ThreadSerializer exists
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_thread(self, request, pk=None):
        review = self.get_object()
        title = request.data.get('title', f'Conversation for Review {review.id}')

        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            langgraph_client = LangGraphClient()
            loop.run_until_complete(langgraph_client.initialize())
            langgraph_thread = loop.run_until_complete(langgraph_client.client.threads.create())
            langgraph_thread_id = langgraph_thread.get('thread_id')
        except Exception as exc:
            logger.error(f'Failed to create LangGraph thread for review {review.id}: {exc}', exc_info=True)
            return Response(
                {'detail': 'Failed to initialize a discussion thread for this review.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        finally:
            try:
                if loop is not None:
                    loop.close()
            except Exception:
                pass

        new_thread = ThreadModel.objects.create(
            review=review,
            title=title,
            thread_id=langgraph_thread_id,
            status='open',
            created_by=request.user,
        )
        serializer = ThreadSerializer(new_thread)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=['post'])
    def re_review(self, request, pk=None):
        review = self.get_object()
        issues = request.data.get('issues', [])
        
        if not issues:
            return Response(
                {"detail": "No issues provided for re-review"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Create new review based on previous one
            new_review = ReviewModel.objects.create(
                repository=review.repository,
                pull_request=review.pull_request,
                commit=review.commit,
                status='pending',
                parent_review=review
            )
            
            # Trigger re-review process
            process_pr_review.delay({
                'pull_request': {
                    'number': review.pull_request.pr_number if review.pull_request else None,
                    'user': {'id': request.user.id},
                    'base': {
                        'repo': {
                            'owner': {'login': review.repository.owner.username},
                            'name': review.repository.repo_name.split('/')[-1]
                        }
                    }
                },
                'repository': {
                    'owner': {'login': review.repository.owner.username},
                    'name': review.repository.repo_name.split('/')[-1]
                }
            })
            
            return Response({
                'review_id': new_review.id,
                'status': 'pending'
            })
        except Exception as e:
            logger.error(f"Error requesting re-review: {str(e)}")
            return Response(
                {"detail": "Error requesting re-review"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def submit_ai_rating(self, request, pk=None):
        """
        Submit a rating and feedback about the AI review quality
        
        Args:
            pk: The ID of the Review model instance
            
        Request body:
            rating: int (1-5)
            feedback: str
            
        Returns:
            Response with success message
        """
        review = self.get_object()
        
        # Validate input
        rating = request.data.get('rating')
        feedback_text = request.data.get('feedback')
        
        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return Response(
                {"detail": "Rating must be an integer between 1 and 5"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not feedback_text:
            return Response(
                {"detail": "Feedback text is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Create or update a ReviewFeedback with a specific feedback_type
        feedback, created = ReviewFeedback.objects.update_or_create(
            review=review,
            user=request.user,
            defaults={
                'rating': rating,
                'feedback': feedback_text
            }
        )
        
        # Track token usage for this feedback
        try:
            # Create a minimal LLMUsage entry for the rating submission
            # This helps track user engagement with the system
            LLMUsageModel.objects.create(
                review=review,
                user=request.user,
                llm_model=review.repository.llm_preference or settings.DEFAULT_LLM_MODEL,
                input_tokens=0,  # No tokens used for ratings
                output_tokens=0,  # No tokens used for ratings
                cost=0.0
            )
        except Exception as e:
            logger.warning(f"Failed to record LLM usage for rating: {str(e)}")
            # Continue even if tracking fails
            
        return Response({
            "detail": "Thank you for your feedback!",
            "review_id": review.id,
            "rating": rating
        })