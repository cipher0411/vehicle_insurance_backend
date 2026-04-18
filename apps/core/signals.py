# apps/core/signals.py - Cleaned up and consolidated

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
import logging

from .models import (
    User, AgentProfile, AgentReferral, Commission, CommissionStructure,
    InsurancePolicy, PolicyRenewal, NoClaimBonus, Claim, Payment, 
    Notification, PolicyCertificate
)
from .Utils.utils import generate_policy_certificate

logger = logging.getLogger(__name__)


# ============================================
# USER SIGNALS
# ============================================

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


@receiver(post_save, sender=User)
def create_agent_profile(sender, instance, created, **kwargs):
    """Create agent profile when a user with agent role is created"""
    if instance.role == 'agent':
        AgentProfile.objects.get_or_create(user=instance)


# ============================================
# POLICY SIGNALS
# ============================================

@receiver(post_save, sender=InsurancePolicy)
def policy_created(sender, instance, created, **kwargs):
    """Handle policy creation - send confirmation email and create renewal record"""
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
                message=f'Your policy {instance.policy_number} has been created.',
                notification_type='system_alert',
                data={'policy_id': str(instance.id)}
            )
        except Exception as e:
            logger.error(f"Failed to send policy confirmation: {e}")
        
        # Create renewal record when policy is created and active
        if instance.status == 'active':
            PolicyRenewal.objects.get_or_create(
                original_policy=instance,
                defaults={
                    'user': instance.user,
                    'original_premium': instance.premium_amount,
                    'renewal_premium': instance.premium_amount,
                    'renewal_date': instance.end_date - timezone.timedelta(days=30),
                    'expiry_date': instance.end_date,
                    'new_start_date': instance.end_date + timezone.timedelta(days=1),
                    'new_end_date': instance.end_date + timezone.timedelta(days=365),
                }
            )


@receiver(post_save, sender=InsurancePolicy)
def auto_generate_certificate_on_activation(sender, instance, **kwargs):
    """Auto-generate certificate when policy becomes active"""
    if instance.status == 'active':
        if not PolicyCertificate.objects.filter(policy=instance, status='generated').exists():
            generate_policy_certificate(instance)


# ============================================
# AGENT COMMISSION SIGNAL (SINGLE VERSION)
# ============================================

@receiver(post_save, sender=InsurancePolicy)
def create_commission_for_agent_policy(sender, instance, created, **kwargs):
    """Create commission when policy is purchased through an agent"""
    if not created:
        return
    
    from .Utils.utils import calculate_agent_commission
    
    # Case 1: Customer was referred by an agent
    if instance.user.referred_by and instance.user.referred_by.role == 'agent':
        agent = instance.user.referred_by
        create_dynamic_commission(agent, instance)
    
    # Case 2: Check AgentReferral table as backup
    elif hasattr(instance.user, 'agent_reference'):
        try:
            agent_referral = instance.user.agent_reference
            agent = agent_referral.agent
            create_dynamic_commission(agent, instance)
        except:
            pass


def create_dynamic_commission(agent, policy):
    """Create commission using dynamic structure"""
    from .Utils.utils import calculate_agent_commission
    
    # Calculate commission using dynamic structure
    calc = calculate_agent_commission(agent, policy, policy.premium_amount)
    
    # Create commission record
    commission = Commission.objects.create(
        agent=agent,
        policy=policy,
        commission_type='new_policy',
        premium_amount=policy.premium_amount,
        commission_rate=calc['commission_rate'],
        bonus_amount=calc['bonus_amount'],
        bonus_reason=calc['bonus_reason'],
        earned_date=policy.start_date,
        status='pending'
    )
    
    # Set agent on policy
    if not policy.agent:
        policy.agent = agent
        policy.save(update_fields=['agent'])
    
    # Create AgentReferral if it doesn't exist
    AgentReferral.objects.get_or_create(
        agent=agent,
        customer=policy.user,
        defaults={'referral_source': 'policy_purchase'}
    )
    
    # Update agent profile metrics
    if hasattr(agent, 'agent_profile'):
        agent.agent_profile.update_performance_metrics()
    
    # Notify agent
    Notification.objects.create(
        user=agent,
        title='New Commission Earned',
        message=f'You earned ₦{commission.total_commission:,.2f} commission from {policy.user.get_full_name() or policy.user.email}',
        notification_type='payment_confirmation',
        data={'commission_id': str(commission.id), 'policy_id': str(policy.id)}
    )



def create_commission_for_agent(agent, policy, commission_type='new_policy'):
    """Helper function to create commission for an agent"""
    try:
        # Get agent's commission rate
        try:
            profile = agent.agent_profile
            commission_rate = profile.commission_rate
            agent_type = profile.agent_type
        except AgentProfile.DoesNotExist:
            commission_rate = Decimal('10.00')
            agent_type = 'individual'
        
        # Check if there's a specific commission structure
        structure = CommissionStructure.objects.filter(
            policy_type=policy.policy_type,
            agent_type=agent_type,
            is_active=True,
            effective_from__lte=policy.start_date
        ).first()
        
        if structure:
            commission_rate = structure.base_commission_rate
        
        # Set agent on policy if not already set
        if not policy.agent:
            policy.agent = agent
            policy.save(update_fields=['agent'])
        
        # Create AgentReferral if it doesn't exist
        AgentReferral.objects.get_or_create(
            agent=agent,
            customer=policy.user,
            defaults={'referral_source': 'policy_purchase'}
        )
        
        # Create commission
        commission = Commission.objects.create(
            agent=agent,
            policy=policy,
            commission_type=commission_type,
            premium_amount=policy.premium_amount,
            commission_rate=commission_rate,
            earned_date=policy.start_date,
            status='pending'
        )
        
        # Check for bonus eligibility (high premium)
        if hasattr(agent, 'agent_profile') and agent.agent_profile.bonus_eligible:
            if policy.premium_amount >= Decimal('500000'):
                bonus = policy.premium_amount * Decimal('0.05')
                Commission.objects.create(
                    agent=agent,
                    policy=policy,
                    commission_type='bonus',
                    premium_amount=policy.premium_amount,
                    commission_rate=0,
                    bonus_amount=bonus,
                    bonus_reason=f'High premium bonus (₦{policy.premium_amount:,.2f})',
                    earned_date=policy.start_date,
                    status='pending'
                )
        
        # Update agent profile metrics
        if hasattr(agent, 'agent_profile'):
            agent.agent_profile.update_performance_metrics()
            
        # Notify agent
        Notification.objects.create(
            user=agent,
            title='New Commission Earned',
            message=f'You earned ₦{commission.total_commission:,.2f} commission from {policy.user.get_full_name() or policy.user.email}',
            notification_type='payment_confirmation',
            data={'commission_id': str(commission.id), 'policy_id': str(policy.id)}
        )
        
    except Exception as e:
        logger.error(f"Failed to create commission for agent {agent.email}: {e}")


# ============================================
# CLAIM SIGNALS
# ============================================

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
        # Check if status changed
        old_status = getattr(instance, '_old_status', None)
        
        if old_status and old_status != instance.status:
            try:
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
                
                Notification.objects.create(
                    user=instance.user,
                    title=f'Claim {instance.get_status_display()}',
                    message=message,
                    notification_type='claim_update',
                    data={'claim_id': str(instance.id)}
                )
            except Exception as e:
                logger.error(f"Failed to send claim update notification: {e}")


@receiver(post_save, sender=Claim)
def update_ncb_after_claim(sender, instance, created, **kwargs):
    """Update No Claim Bonus when a claim is filed"""
    if created and instance.policy and instance.policy.vehicle:
        ncb = NoClaimBonus.objects.filter(
            user=instance.user,
            vehicle=instance.policy.vehicle
        ).first()
        
        if ncb:
            ncb.update_after_claim()
        else:
            NoClaimBonus.objects.create(
                user=instance.user,
                vehicle=instance.policy.vehicle,
                claim_free_years=0,
                current_ncb_percentage=0,
                last_claim_date=timezone.now().date()
            )


@receiver(post_save, sender=Claim)
def claim_post_save_cleanup(sender, instance, **kwargs):
    """Clean up the temporary _old_status attribute"""
    if hasattr(instance, '_old_status'):
        delattr(instance, '_old_status')


# ============================================
# PAYMENT SIGNALS
# ============================================

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
    old_status = getattr(instance, '_old_status', None)
    
    if instance.status == 'completed' and old_status != 'completed':
        try:
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
            
            Notification.objects.create(
                user=instance.user,
                title='Payment Successful',
                message=f'Your payment of ₦{instance.amount:,.2f} was successful. Your policy is now active.',
                notification_type='payment_confirmation',
                data={'payment_id': str(instance.id), 'policy_id': str(instance.policy.id) if instance.policy else None}
            )
        except Exception as e:
            logger.error(f"Failed to send payment confirmation: {e}")


@receiver(post_save, sender=Payment)
def payment_post_save_cleanup(sender, instance, **kwargs):
    """Clean up the temporary _old_status attribute"""
    if hasattr(instance, '_old_status'):
        delattr(instance, '_old_status')
        
        
        
        
        
        
        
# apps/core/signals.py - Add this signal

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import InsurancePolicy, Vehicle


@receiver(post_save, sender=InsurancePolicy)
def update_vehicle_insurance_status(sender, instance, created, **kwargs):
    """Automatically update vehicle insurance status based on policy status"""
    if instance.vehicle:
        vehicle = instance.vehicle
        
        # Check if there's any active policy for this vehicle
        active_policy_exists = InsurancePolicy.objects.filter(
            vehicle=vehicle,
            status='active'
        ).exists()
        
        # Update vehicle insurance status
        if vehicle.is_insured != active_policy_exists:
            vehicle.is_insured = active_policy_exists
            vehicle.save(update_fields=['is_insured'])


@receiver(pre_save, sender=InsurancePolicy)
def check_policy_status_change(sender, instance, **kwargs):
    """Store old status to detect changes"""
    if instance.pk:
        try:
            old_instance = InsurancePolicy.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except InsurancePolicy.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=InsurancePolicy)
def handle_policy_status_change(sender, instance, created, **kwargs):
    """Handle policy status changes to update vehicle insurance"""
    if instance.vehicle:
        old_status = getattr(instance, '_old_status', None)
        
        # If status changed to or from 'active', update vehicle insurance
        if old_status != instance.status:
            if instance.status == 'active' or old_status == 'active':
                update_vehicle_insurance_status(sender, instance, created, **kwargs)

