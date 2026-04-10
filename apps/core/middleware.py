# Create core/middleware.py

import logging
import traceback
from django.shortcuts import render
from django.conf import settings

logger = logging.getLogger('django')


class CustomErrorMiddleware:
    """Custom middleware for better error handling"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_exception(self, request, exception):
        """Process exceptions and log them"""
        if not settings.DEBUG:
            # Log the error
            logger.error(
                f"Exception occurred: {str(exception)}\n"
                f"URL: {request.build_absolute_uri()}\n"
                f"Method: {request.method}\n"
                f"User: {request.user if request.user.is_authenticated else 'Anonymous'}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
        
        return None