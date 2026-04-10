# Create core/email_utils.py or add to utils.py

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_contact_confirmation_email(inquiry):
    """Send confirmation email to the user"""
    subject = f"Thank you for contacting VehicleInsure - {inquiry.inquiry_number}"
    
    # HTML content
    html_content = render_to_string('core/emails/contact_confirmation.html', {
        'inquiry': inquiry,
        'site_name': 'VehicleInsure Nigeria',
        'support_email': settings.DEFAULT_FROM_EMAIL,
    })
    
    # Plain text content
    text_content = strip_tags(html_content)
    
    # Send email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[inquiry.email],
        reply_to=[settings.DEFAULT_FROM_EMAIL],
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=True)
    
    return True


def send_staff_notification_email(inquiry):
    """Send notification email to staff"""
    subject = f"New Contact Inquiry - {inquiry.get_inquiry_type_display()} - {inquiry.inquiry_number}"
    
    # Determine recipient based on inquiry type
    recipient_map = {
        'claim': 'claims@vehicleinsure.ng',
        'partnership': 'partners@vehicleinsure.ng',
        'quote': 'sales@vehicleinsure.ng',
    }
    
    # Get staff emails from settings or use defaults
    staff_emails = getattr(settings, 'STAFF_NOTIFICATION_EMAILS', [
        'support@vehicleinsure.ng',
        'hello@vehicleinsure.ng',
    ])
    
    # Add specific department email if applicable
    dept_email = recipient_map.get(inquiry.inquiry_type)
    if dept_email and dept_email not in staff_emails:
        staff_emails.append(dept_email)
    
    # HTML content
    html_content = render_to_string('core/emails/staff_notification.html', {
        'inquiry': inquiry,
        'admin_url': f"/staff/inquiries/{inquiry.id}/",
    })
    
    # Plain text content
    text_content = strip_tags(html_content)
    
    # Send email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=staff_emails,
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=True)
    
    return True