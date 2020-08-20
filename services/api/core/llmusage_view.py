from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .models import (
    LLMUsage as LLMUsageModel,
)
from .serializers import (
    LLMUsageSerializer
)

from django.db.models import Q, Sum, Count
import logging
logger = logging.getLogger(__name__)

class LLMUsageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LLMUsageSerializer
    permission_classes = [IsAuthenticated]

    def _get_base_llm_usage_queryset(self):
        """
        Helper method to get the base QuerySet of LLMUsageModel instances
        based on user permissions.
        """
        if self.request.user.is_staff:
            return LLMUsageModel.objects.all()
        else:
            return LLMUsageModel.objects.filter(
                Q(review__repository__owner=self.request.user) |
                Q(review__repository__collaborators__user=self.request.user)
            ).distinct()

    def get_queryset(self):
        """
        This method is intended to return a summary dictionary.
        It's called by the overridden 'list' and 'summary' actions.
        Standard DRF ModelViewSet 'retrieve' action will break if it relies on this
        method returning a QuerySet of model instances.
        """
        base_queryset = self._get_base_llm_usage_queryset()
