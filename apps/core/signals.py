from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import User, InsurancePolicy, Claim, Payment, Notification
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_created(sender, instance, created, **kwargs):
    """Send welcome email when a new user is created"""
    if created:
        try:
            send_mail(
                'Welcome to Vehicle Insurance Pro',
                f"""
                Hi {instance.get_full_name() or instance.email},
                
                Welcome to Vehicle Insurance Pro!
                
                We're excited to have you on board. Here's what you can do:
                • Get instant insurance quotes
                • Purchase policies online
                • File claims easily
                • Track your claims status
                • Get 24/7 support
                
                Get started by adding your vehicle details and getting your first quote.
                
                Best regards,
                Vehicle Insurance Pro Team
                """,
                settings.DEFAULT_FROM_EMAIL,
                [instance.email],
                fail_silently=True,
            )
            
            # Create welcome notification
            Notification.objects.create(
                user=instance,
                title='Welcome to Vehicle Insurance Pro!',
                message='Get started with your first insurance quote today.',
                notification_type='system_alert'
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email to {instance.email}: {e}")


@receiver(post_save, sender=InsurancePolicy)
def policy_created(sender, instance, created, **kwargs):
    """Handle policy creation and expiry notifications"""
    if created:
        # Send policy confirmation email
        try:
            send_mail(
                f'Policy Confirmation - {instance.policy_number}',
                f"""
                Dear {instance.user.get_full_name() or instance.user.email},
                
                Your insurance policy has been successfully purchased!
                
                Policy Details:
                • Policy Number: {instance.policy_number}
                • Type: {instance.get_policy_type_display()}
                • Coverage Amount: ₦{instance.coverage_amount:,.2f}
                • Premium: ₦{instance.premium_amount:,.2f}
                • Start Date: {instance.start_date}
                • End Date: {instance.end_date}
                
                Your policy document is available in your account.
                
                For any assistance, please contact our support team.
                
                Best regards,
                Vehicle Insurance Pro Team
                """,
                settings.DEFAULT_FROM_EMAIL,
                [instance.user.email],
                fail_silently=True,
            )
            
            # Create notification
            Notification.objects.create(
                user=instance.user,
                title='Policy Purchased Successfully',
                message=f'Your policy {instance.policy_number} has been activated.',
                notification_type='system_alert',
                data={'policy_id': str(instance.id)}
            )
        except Exception as e:
            logger.error(f"Failed to send policy confirmation: {e}")


# Store original status before save
@receiver(pre_save, sender=Claim)
def claim_pre_save(sender, instance, **kwargs):
    """Store the original status before the claim is saved"""
    if instance.pk:
        try:
            old_instance = Claim.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Claim.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Claim)
def claim_updated(sender, instance, created, **kwargs):
    """Send notifications when claim is created or status changes"""
    if created:
        # New claim created
        try:
            # Send email to user
            send_mail(
                f'Claim Filed - {instance.claim_number}',
                f"""
                Dear {instance.user.get_full_name() or instance.user.email},
                
                Your claim has been successfully filed!
                
                Claim Details:
                • Claim Number: {instance.claim_number}
                • Type: {instance.get_claim_type_display()}
                • Claimed Amount: ₦{instance.claimed_amount:,.2f}
                • Incident Date: {instance.incident_date}
                • Status: Pending Review
                
                We will review your claim and get back to you within 24-48 hours.
                
                You can track your claim status in your account.
                
                Best regards,
                Vehicle Insurance Pro Team
                """,
                settings.DEFAULT_FROM_EMAIL,
                [instance.user.email],
                fail_silently=True,
            )
            
            # Create notification for user
            Notification.objects.create(
                user=instance.user,
                title='Claim Filed Successfully',
                message=f'Your claim #{instance.claim_number} has been filed and is pending review.',
                notification_type='claim_update',
                data={'claim_id': str(instance.id)}
            )
            
            # Notify admin users
            from .models import User
            admin_users = User.objects.filter(role='admin', is_active=True)
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='New Claim Filed',
                    message=f'New claim #{instance.claim_number} filed by {instance.user.get_full_name() or instance.user.email} for ₦{instance.claimed_amount:,.2f}',
                    notification_type='claim_update',
                    data={'claim_id': str(instance.id)}
                )
        except Exception as e:
            logger.error(f"Failed to send claim creation notification: {e}")
    else:
        # Check if status changed (using the stored old status)
        old_status = getattr(instance, '_old_status', None)
        
        if old_status and old_status != instance.status:
            try:
                # Prepare status-specific message
                status_messages = {
                    'under_review': 'Your claim is now under review by our claims team.',
                    'approved': f'Your claim has been approved for ₦{instance.approved_amount:,.2f}.',
                    'rejected': f'Your claim has been rejected. Reason: {instance.rejection_reason}',
                    'settled': f'Your claim has been settled for ₦{instance.approved_amount or instance.claimed_amount:,.2f}.'
                }
                
                message = status_messages.get(
                    instance.status, 
                    f'Your claim status has been updated to {instance.get_status_display()}.'
                )
                
                # Send email notification
                email_body = f"""
                Dear {instance.user.get_full_name() or instance.user.email},
                
                Your claim #{instance.claim_number} status has been updated to: {instance.get_status_display()}
                
                Claim Details:
                • Claim Number: {instance.claim_number}
                • Type: {instance.get_claim_type_display()}
                • Status: {instance.get_status_display()}
                • Claimed Amount: ₦{instance.claimed_amount:,.2f}
                """
                
                if instance.approved_amount:
                    email_body += f"\n• Approved Amount: ₦{instance.approved_amount:,.2f}"
                
                if instance.rejection_reason:
                    email_body += f"\n• Rejection Reason: {instance.rejection_reason}"
                
                email_body += """
                
                For more details, please login to your account.
                
                Best regards,
                Vehicle Insurance Pro Team
                """
                
                send_mail(
                    f'Claim Update - {instance.claim_number}',
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.user.email],
                    fail_silently=True,
                )
                
                # Create notification
                Notification.objects.create(
                    user=instance.user,
                    title=f'Claim {instance.get_status_display()}',
                    message=message,
                    notification_type='claim_update',
                    data={'claim_id': str(instance.id)}
                )
            except Exception as e:
                logger.error(f"Failed to send claim update notification: {e}")


# Store original status before save for Payment
@receiver(pre_save, sender=Payment)
def payment_pre_save(sender, instance, **kwargs):
    """Store the original status before the payment is saved"""
    if instance.pk:
        try:
            old_instance = Payment.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Payment.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Payment)
def payment_completed(sender, instance, created, **kwargs):
    """Handle payment completion"""
    # Check if status changed to completed
    old_status = getattr(instance, '_old_status', None)
    
    if instance.status == 'completed' and old_status != 'completed':
        try:
            # Send payment confirmation
            send_mail(
                f'Payment Confirmation - {instance.transaction_id}',
                f"""
                Dear {instance.user.get_full_name() or instance.user.email},
                
                Your payment has been successfully processed!
                
                Payment Details:
                • Transaction ID: {instance.transaction_id}
                • Amount: ₦{instance.amount:,.2f}
                • Payment Method: {instance.get_payment_method_display()}
                • Date: {instance.paid_at or instance.updated_at}
                
                Your policy is now active.
                
                Thank you for choosing Vehicle Insurance Pro.
                
                Best regards,
                Vehicle Insurance Pro Team
                """,
                settings.DEFAULT_FROM_EMAIL,
                [instance.user.email],
                fail_silently=True,
            )
            
            # Create notification
            Notification.objects.create(
                user=instance.user,
                title='Payment Successful',
                message=f'Your payment of ₦{instance.amount:,.2f} was successful. Your policy is now active.',
                notification_type='payment_confirmation',
                data={'payment_id': str(instance.id), 'policy_id': str(instance.policy.id) if instance.policy else None}
            )
        except Exception as e:
            logger.error(f"Failed to send payment confirmation: {e}")


# Clean up the _old_status attribute after save
@receiver(post_save, sender=Claim)
def claim_post_save_cleanup(sender, instance, **kwargs):
    """Clean up the temporary _old_status attribute"""
    if hasattr(instance, '_old_status'):
        delattr(instance, '_old_status')


@receiver(post_save, sender=Payment)
def payment_post_save_cleanup(sender, instance, **kwargs):
    """Clean up the temporary _old_status attribute"""
    if hasattr(instance, '_old_status'):
        delattr(instance, '_old_status')