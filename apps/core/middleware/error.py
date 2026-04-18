"""
Custom error handling middleware
"""
import logging
import traceback
from django.conf import settings
from django.shortcuts import render

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
            # Log the error with full details
            logger.error(
                f"Exception occurred: {str(exception)}\n"
                f"URL: {request.build_absolute_uri()}\n"
                f"Method: {request.method}\n"
                f"User: {request.user if request.user.is_authenticated else 'Anonymous'}\n"
                f"IP: {self.get_client_ip(request)}\n"
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            
            # Try to log to SecurityEvent if model exists
            try:
                from apps.core.models import SecurityEvent
                SecurityEvent.objects.create(
                    event_type='EXCEPTION',
                    severity='HIGH',
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=self.get_client_ip(request),
                    path=request.path,
                    method=request.method,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    details={
                        'exception': str(exception),
                        'exception_type': type(exception).__name__,
                    }
                )
            except Exception:
                pass
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip