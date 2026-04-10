from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from .models import InsurancePolicy, Notification, User, Payment, Claim, InsuranceQuote
import logging
from core.flutterwave import flutterwave_service
logger = logging.getLogger(__name__)

@shared_task
def send_policy_expiry_reminders():
    """Send reminders for policies expiring soon"""
    today = timezone.now().date()
    reminders_days = [30, 15, 7, 3, 1]
    
    for days in reminders_days:
        expiry_date = today + timezone.timedelta(days=days)
        policies = InsurancePolicy.objects.filter(
            end_date=expiry_date,
            status='active'
        )
        
        for policy in policies:
            try:
                # Send email reminder
                send_mail(
                    f'Policy Expiry Reminder - {policy.policy_number}',
                    f"""
                    Dear {policy.user.get_full_name()},
                    
                    Your insurance policy {policy.policy_number} will expire on {policy.end_date}.
                    
                    Please renew your policy to continue enjoying coverage benefits.
                    
                    Renew now to get:
                    • No Claim Bonus up to 50%
                    • Instant policy issuance
                    • Digital policy document
                    
                    Click here to renew: {settings.SITE_URL}/policies/{policy.id}/renew
                    
                    Best regards,
                    Vehicle Insurance Pro Team
                    """,
                    settings.DEFAULT_FROM_EMAIL,
                    [policy.user.email],
                    fail_silently=True,
                )
                
                # Create notification
                Notification.objects.create(
                    user=policy.user,
                    title='Policy Expiry Reminder',
                    message=f'Your policy {policy.policy_number} expires in {days} days. Renew now!',
                    notification_type='policy_expiry',
                    data={'policy_id': str(policy.id)}
                )
            except Exception as e:
                logger.error(f"Failed to send expiry reminder for policy {policy.policy_number}: {e}")

@shared_task
def send_claim_reminders():
    """Send reminders for pending claims"""
    pending_claims = Claim.objects.filter(
        status='pending',
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    )
    
    for claim in pending_claims:
        days_pending = (timezone.now() - claim.created_at).days
        
        if days_pending in [3, 5, 7]:
            try:
                send_mail(
                    f'Claim Status Update - {claim.claim_number}',
                    f"""
                    Dear {claim.user.get_full_name()},
                    
                    Your claim #{claim.claim_number} is still under review.
                    
                    Current Status: {claim.get_status_display()}
                    Days Pending: {days_pending}
                    
                    Our team is working on your claim and will update you soon.
                    
                    If you have any additional information to provide, please login to your account.
                    
                    Best regards,
                    Vehicle Insurance Pro Team
                    """,
                    settings.DEFAULT_FROM_EMAIL,
                    [claim.user.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send claim reminder for claim {claim.claim_number}: {e}")

@shared_task
def cleanup_expired_quotes():
    """Delete expired quotes"""
    expired_quotes = InsuranceQuote.objects.filter(
        valid_until__lt=timezone.now(),
        status='approved'
    )
    
    count = expired_quotes.update(status='expired')
    logger.info(f"Expired {count} insurance quotes")

@shared_task
def send_daily_digest():
    """Send daily digest emails to users"""
    users = User.objects.filter(is_active=True, role='customer')
    yesterday = timezone.now() - timezone.timedelta(days=1)
    
    for user in users:
        new_policies = InsurancePolicy.objects.filter(
            user=user,
            created_at__gte=yesterday
        ).count()
        
        new_claims = Claim.objects.filter(
            user=user,
            created_at__gte=yesterday
        ).count()
        
        if new_policies > 0 or new_claims > 0:
            try:
                send_mail(
                    'Your Daily Insurance Digest',
                    f"""
                    Dear {user.get_full_name()},
                    
                    Here's your daily activity summary:
                    
                    • New Policies: {new_policies}
                    • New Claims: {new_claims}
                    
                    Login to your account for more details.
                    
                    Best regards,
                    Vehicle Insurance Pro Team
                    """,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send daily digest to {user.email}: {e}")

@shared_task
def update_policy_statuses():
    """Update policy statuses (expire old policies)"""
    today = timezone.now().date()
    expired_policies = InsurancePolicy.objects.filter(
        end_date__lt=today,
        status='active'
    )
    
    count = expired_policies.update(status='expired')
    logger.info(f"Updated {count} policies to expired status")
    
    
    
    
    
    
    
    
    
# Add these tasks to existing tasks.py

@shared_task
def process_failed_payments():
    """Process and retry failed payments"""
    failed_payments = Payment.objects.filter(
        status='failed',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    )
    
    for payment in failed_payments:
        try:
            # Retry payment
            flutterwave_response = flutterwave_service.initialize_payment(
                amount=float(payment.amount),
                email=payment.user.email,
                tx_ref=payment.payment_reference,
                customer_name=payment.user.get_full_name()
            )
            
            if flutterwave_response['success']:
                # Send notification to user
                Notification.objects.create(
                    user=payment.user,
                    title='Payment Retry Available',
                    message=f'Your payment for policy {payment.policy.policy_number} can be retried. Click to continue.',
                    notification_type='payment_confirmation',
                    data={'payment_id': str(payment.id), 'payment_link': flutterwave_response['link']}
                )
        except Exception as e:
            logger.error(f"Failed to retry payment {payment.id}: {e}")

@shared_task
def cleanup_expired_payment_references():
    """Clean up expired payment references"""
    expired_time = timezone.now() - timezone.timedelta(hours=24)
    pending_payments = Payment.objects.filter(
        status='pending',
        created_at__lt=expired_time
    )
    
    count = pending_payments.update(status='failed')
    logger.info(f"Marked {count} pending payments as failed")