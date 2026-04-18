"""
Audit logging middleware for compliance and tracking
"""
import json
import uuid
import logging
from ipware import get_client_ip

logger = logging.getLogger('audit')


class AuditLogMiddleware:
    """Log all significant actions for compliance"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Generate unique request ID
        request.id = str(uuid.uuid4())
        
        # Process request
        response = self.get_response(request)
        
        # Log after response (only for modifying actions)
        if self.should_log(request):
            self.log_request(request, response)
        
        return response
    
    def should_log(self, request):
        """Determine if request should be logged"""
        # Skip static/media files
        if request.path.startswith(('/static/', '/media/', '/admin/jsi18n/')):
            return False
        
        # Skip GET requests (too many)
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return False
        
        return True
    
    def log_request(self, request, response):
        """Create audit log entry"""
        try:
            from apps.core.models import AuditLog
            
            client_ip, _ = get_client_ip(request)
            
            # Determine resource type from URL path
            resource_type = self.get_resource_type(request.path)
            resource_id = self.get_resource_id(request)
            
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=self.get_action(request.method),
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                session_id=request.session.session_key,
                request_id=request.id,
                metadata={
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'query_params': dict(request.GET.items()) if request.GET else None,
                }
            )
        except Exception as e:
            # Don't break the app if logging fails
            logger.error(f"Audit logging failed: {e}")
    
    def get_action(self, method):
        """Map HTTP method to action"""
        actions = {
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'UPDATE',
            'DELETE': 'DELETE',
        }
        return actions.get(method, 'VIEW')
    
    def get_resource_type(self, path):
        """Extract resource type from URL path"""
        resource_map = {
            'policy': 'InsurancePolicy',
            'claim': 'Claim',
            'payment': 'Payment',
            'vehicle': 'Vehicle',
            'user': 'User',
            'ticket': 'SupportTicket',
            'document': 'Document',
            'promo': 'PromoCode',
            'quote': 'InsuranceQuote',
            'notification': 'Notification',
        }
        
        for key, value in resource_map.items():
            if key in path:
                return value
        
        return 'Unknown'
    
    def get_resource_id(self, request):
        """Extract resource ID from URL kwargs"""
        if hasattr(request, 'resolver_match') and request.resolver_match:
            kwargs = request.resolver_match.kwargs
            return str(kwargs.get('pk', kwargs.get('id', kwargs.get('uuid', ''))))
        return ''