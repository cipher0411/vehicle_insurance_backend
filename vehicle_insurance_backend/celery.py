import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vehicle_insurance.settings')

app = Celery('vehicle_insurance')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-policy-expiry-reminders': {
        'task': 'apps.core.tasks.send_policy_expiry_reminders',
        'schedule': crontab(hour=9, minute=0),  # Run daily at 9 AM
    },
    'send-claim-reminders': {
        'task': 'apps.core.tasks.send_claim_reminders',
        'schedule': crontab(hour=10, minute=0),  # Run daily at 10 AM
    },
    'cleanup-expired-quotes': {
        'task': 'apps.core.tasks.cleanup_expired_quotes',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
    'send-daily-digest': {
        'task': 'apps.core.tasks.send_daily_digest',
        'schedule': crontab(hour=20, minute=0),  # Run daily at 8 PM
    },
    'update-policy-statuses': {
        'task': 'apps.core.tasks.update_policy_statuses',
        'schedule': crontab(hour=1, minute=0),  # Run daily at 1 AM
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')