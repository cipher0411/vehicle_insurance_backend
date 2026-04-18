"""
Celery tasks for async operations
"""
import os
import csv
import tempfile
import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Count, Q, Sum, Max

# Use proper absolute imports
from apps.core.models import (
    User, InsurancePolicy, Notification, Payment, Claim, 
    InsuranceQuote, ScheduledReport, ReportRunHistory, SecurityEvent
)

logger = logging.getLogger(__name__)


# ========== Existing Tasks ==========

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
                    
                    Login to your account to renew.
                    
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


@shared_task
def process_failed_payments():
    """Process and retry failed payments"""
    failed_payments = Payment.objects.filter(
        status='failed',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    )
    
    for payment in failed_payments:
        try:
            # Send notification to user to retry
            Notification.objects.create(
                user=payment.user,
                title='Payment Retry Available',
                message=f'Your payment for policy {payment.policy.policy_number} can be retried. Click to continue.',
                notification_type='payment_confirmation',
                data={'payment_id': str(payment.id)}
            )
        except Exception as e:
            logger.error(f"Failed to process failed payment {payment.id}: {e}")


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


# ========== Security Report Tasks ==========

def generate_csv_report(events):
    """Generate CSV report from events"""
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Timestamp', 'Event Type', 'Severity', 'IP Address', 'Path', 'Method', 'Details'])
    
    # Data
    for event in events.order_by('-created_at')[:1000]:
        writer.writerow([
            event.created_at.isoformat(),
            event.get_event_type_display(),
            event.severity,
            event.ip_address,
            event.path,
            event.method,
            str(event.details)[:200]
        ])
    
    return output.getvalue()


@shared_task(bind=True, max_retries=3)
def generate_security_report(self, report_id):
    """Generate and send scheduled security report"""
    try:
        report = ScheduledReport.objects.get(id=report_id)
        
        # Create run history entry
        history = ReportRunHistory.objects.create(
            scheduled_report=report,
            status='partial',
            started_at=timezone.now()
        )
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=report.date_range_days)
        
        # Get security events
        events = SecurityEvent.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Apply filters
        if report.severity_filter:
            severities = report.severity_filter.split(',')
            events = events.filter(severity__in=severities)
        
        if report.event_type_filter:
            event_types = report.event_type_filter.split(',')
            events = events.filter(event_type__in=event_types)
        
        # Generate report data
        total_events = events.count()
        blocked_attacks = events.filter(
            event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT']
        ).count()
        
        unique_attackers = events.filter(
            event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL']
        ).values('ip_address').distinct().count()
        
        top_attackers = events.filter(
            event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT']
        ).values('ip_address').annotate(
            count=Count('id'),
            last_seen=Max('created_at')
        ).order_by('-count')[:10]
        
        # Severity breakdown
        severity_data = events.values('severity').annotate(count=Count('id'))
        severity_breakdown = {item['severity']: item['count'] for item in severity_data}
        
        # Event type distribution
        event_types_data = events.values('event_type').annotate(count=Count('id')).order_by('-count')
        
        # Prepare context for template
        context = {
            'report': report,
            'total_events': total_events,
            'blocked_attacks': blocked_attacks,
            'unique_attackers': unique_attackers,
            'block_rate': round((blocked_attacks / total_events * 100) if total_events > 0 else 0, 1),
            'top_attackers': top_attackers,
            'severity_breakdown': severity_breakdown,
            'event_types': event_types_data,
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': timezone.now(),
            'include_charts': report.include_charts,
            'include_tables': report.include_tables,
            'include_recommendations': report.include_recommendations,
        }
        
        # Generate report content
        try:
            html_content = render_to_string('core/admin/security/email_report.html', context)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            html_content = f"""
            <h1>Edgway Security Report: {report.name}</h1>
            <p>Period: {start_date.date()} to {end_date.date()}</p>
            <p>Total Events: {total_events}</p>
            <p>Blocked Attacks: {blocked_attacks}</p>
            <p>Unique Attackers: {unique_attackers}</p>
            """
        
        # Create PDF if requested
        attachment_path = None
        if report.format == 'pdf':
            try:
                from weasyprint import HTML
                pdf_file = HTML(string=html_content).write_pdf()
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
                    f.write(pdf_file)
                    attachment_path = f.name
                
                history.report_file.save(
                    f"security_report_{report.name}_{end_date.date()}.pdf",
                    open(attachment_path, 'rb')
                )
                history.file_size = f"{len(pdf_file) / 1024:.1f} KB"
            except ImportError:
                logger.warning("WeasyPrint not installed, skipping PDF generation")
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")
        
        elif report.format == 'csv':
            # Generate CSV
            csv_content = generate_csv_report(events)
            attachment_path = tempfile.NamedTemporaryFile(delete=False, suffix='.csv').name
            with open(attachment_path, 'w') as f:
                f.write(csv_content)
            
            history.report_file.save(
                f"security_report_{report.name}_{end_date.date()}.csv",
                open(attachment_path, 'rb')
            )
        
        # Send email
        subject = f"[Edgway Security] {report.name} - {end_date.strftime('%Y-%m-%d')}"
        
        # Plain text version
        text_content = f"""
        Edgway Security Report: {report.name}
        
        Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
        
        Summary:
        - Total Events: {total_events}
        - Blocked Attacks: {blocked_attacks}
        - Unique Attackers: {unique_attackers}
        - Block Rate: {context['block_rate']}%
        
        This is an automated report from Edgway Security.
        """
        
        email = EmailMessage(
            subject=subject,
            body=html_content if report.format == 'email' else text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=report.get_recipients_list(),
            cc=report.get_cc_list(),
            bcc=report.get_bcc_list(),
        )
        
        if report.format == 'email':
            email.content_subtype = "html"
        
        # Attach file if generated
        if attachment_path and report.format != 'email':
            email.attach_file(attachment_path)
        
        email.send(fail_silently=False)
        
        # Clean up temp file
        if attachment_path and os.path.exists(attachment_path):
            os.unlink(attachment_path)
        
        # Update history
        history.status = 'success'
        history.completed_at = timezone.now()
        history.recipients_count = len(report.get_recipients_list())
        history.save()
        
        # Update report
        report.mark_run(success=True)
        
        return f"Report {report.name} sent successfully to {history.recipients_count} recipients"
        
    except ScheduledReport.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return f"Report {report_id} not found"
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        # Log error and update status
        if 'history' in locals():
            history.status = 'failed'
            history.error_message = str(e)
            history.completed_at = timezone.now()
            history.save()
        
        if 'report' in locals():
            report.mark_run(success=False, error=str(e))
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def run_all_scheduled_reports():
    """Check and run all due scheduled reports"""
    now = timezone.now()
    
    # Find reports that are due
    due_reports = ScheduledReport.objects.filter(
        status='active',
        next_run__lte=now
    )
    
    count = 0
    for report in due_reports:
        generate_security_report.delay(str(report.id))
        count += 1
    
    logger.info(f"Triggered {count} scheduled reports")
    return f"Triggered {count} scheduled reports"