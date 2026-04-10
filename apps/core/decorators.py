from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def role_required(*roles):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator

def admin_required(view_func):
    """Decorator to check if user is admin"""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.role != 'admin':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped

def staff_required(view_func):
    """Decorator to check if user is staff (agent, underwriter, claims_adjuster, support)"""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.role not in ['agent', 'underwriter', 'claims_adjuster', 'support', 'admin']:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped

def customer_required(view_func):
    """Decorator to check if user is customer"""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.role != 'customer':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped