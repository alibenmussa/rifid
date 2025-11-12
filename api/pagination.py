# api/pagination.py - Professional pagination configuration
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Professional pagination class with default page size of 30.
    Provides consistent pagination across all API endpoints.
    """
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """
        Return a paginated style Response object with additional metadata.
        """
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.get_page_size(self.request),
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })

