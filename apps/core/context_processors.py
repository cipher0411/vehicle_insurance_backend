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