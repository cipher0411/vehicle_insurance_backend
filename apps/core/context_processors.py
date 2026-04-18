# apps/core/context_processors.py

from apps.core.models import Notification

def notification_count(request):
    """Add unread notification count to context"""
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {
            'unread_notifications_count': count
        }
    return {
        'unread_notifications_count': 0
    }
    
    
    
    
    
from .models import AgentReferral, Claim

def agent_pending_claims_count(request):
    """Add pending claims count for agents"""
    if request.user.is_authenticated and request.user.role == 'agent':
        customer_ids = AgentReferral.objects.filter(agent=request.user).values_list('customer_id', flat=True)
        count = Claim.objects.filter(user_id__in=customer_ids, status='pending').count()
        return {'pending_claims_count': count}
    return {'pending_claims_count': 0}