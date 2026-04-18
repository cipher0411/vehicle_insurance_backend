"""
Security decorators for views
"""
from functools import wraps
from django.http import HttpResponseForbidden, JsonResponse
from django.core.cache import cache
from django.conf import settings
from ipware import get_client_ip


def secure_file_upload(file_types=None, max_size=None):
    """Decorator for secure file uploads"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Import from the utils package (directory)
            try:
                from apps.core.Utils.file_security import FileSecurityScanner
            except ImportError:
                # Fallback if security module not available
                return view_func(request, *args, **kwargs)
            
            if request.method == 'POST' and request.FILES:
                scanner = FileSecurityScanner()
                
                for field_name, uploaded_file in request.FILES.items():
                    if file_types:
                        file_type = file_types
                    elif field_name in ['profile_picture', 'photo', 'image', 'selfie']:
                        file_type = 'image'
                    else:
                        file_type = 'document'
                    
                    result = scanner.scan_file(uploaded_file, file_type)
                    
                    if not result['safe']:
                        try:
                            from apps.core.models import SecurityEvent
                            client_ip, _ = get_client_ip(request)
                            SecurityEvent.objects.create(
                                event_type='MALWARE_DETECTED',
                                severity='HIGH',
                                user=request.user if request.user.is_authenticated else None,
                                ip_address=client_ip,
                                path=request.path,
                                method=request.method,
                                details={
                                    'threats': result['threats'],
                                    'score': result['score'],
                                    'file_hash': result['hash'],
                                    'file_name': uploaded_file.name
                                }
                            )
                        except Exception:
                            pass
                        
                        return JsonResponse({
                            'error': 'Security scan failed',
                            'message': 'The uploaded file contains suspicious content and was blocked.',
                            'details': result['threats'][:3] if settings.DEBUG else []
                        }, status=400)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_ip_reputation(view_func):
    """Check IP reputation before processing request"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            from apps.core.Utils.file_security import ThreatIntelligenceService
        except ImportError:
            return view_func(request, *args, **kwargs)
        
        client_ip, _ = get_client_ip(request)
        
        if client_ip in ['127.0.0.1', 'localhost', '::1']:
            return view_func(request, *args, **kwargs)
        
        cache_key = f"ip_reputation:{client_ip}"
        reputation = cache.get(cache_key)
        
        if reputation is None:
            service = ThreatIntelligenceService()
            reputation = service.check_ip_reputation(client_ip)
            cache.set(cache_key, reputation, 3600)
        
        if reputation.get('malicious', False):
            return HttpResponseForbidden("Access Denied - Security Policy")
        
        return view_func(request, *args, **kwargs)
    return wrapper


def rate_limit(limit=10, window=60):
    """Rate limiting decorator"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            client_ip, _ = get_client_ip(request)
            user_id = request.user.id if request.user.is_authenticated else 'anon'
            
            ip_key = f"rate_limit:ip:{client_ip}:{request.path}"
            ip_count = cache.get(ip_key, 0)
            
            if ip_count >= limit * 2:
                return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
            
            user_key = f"rate_limit:user:{user_id}:{request.path}"
            user_count = cache.get(user_key, 0)
            
            if user_count >= limit:
                return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
            
            cache.set(ip_key, ip_count + 1, window)
            cache.set(user_key, user_count + 1, window)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Role-based decorators
def role_required(*roles):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            if request.user.role not in roles:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def admin_required(view_func):
    """Decorator to check if user is admin"""
    return role_required('admin')(view_func)


def staff_required(view_func):
    """Decorator to check if user is staff"""
    return role_required('admin', 'agent', 'underwriter', 'claims_adjuster', 'support')(view_func)


def customer_required(view_func):
    """Decorator to check if user is customer"""
    return role_required('customer')(view_func)









# apps/core/decorators.py - Add this

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

def agent_required(view_func):
    """Decorator for views that require agent access"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        if request.user.role != 'agent':
            raise PermissionDenied("You don't have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    """Decorator for views that require admin access"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        if request.user.role != 'admin' and not request.user.is_superuser:
            raise PermissionDenied("You don't have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view









