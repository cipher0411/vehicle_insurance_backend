from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admin to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user.is_staff or request.user.role == 'admin':
            return True
        
        # Check if the object has a 'user' attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if the object is the user itself
        if hasattr(obj, 'id') and isinstance(obj, request.user.__class__):
            return obj == request.user
        
        return False

class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Staff users can modify, others can only read.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff

class IsCustomerOnly(permissions.BasePermission):
    """
    Only customers can access.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'customer'

class IsAgentOrAdmin(permissions.BasePermission):
    """
    Only agents or admin can access.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'agent' or 
            request.user.role == 'admin' or 
            request.user.is_staff
        )

class IsUnderwriterOrAdmin(permissions.BasePermission):
    """
    Only underwriters or admin can access.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'underwriter' or 
            request.user.role == 'admin' or 
            request.user.is_staff
        )

class IsClaimsAdjusterOrAdmin(permissions.BasePermission):
    """
    Only claims adjusters or admin can access.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'claims_adjuster' or 
            request.user.role == 'admin' or 
            request.user.is_staff
        )