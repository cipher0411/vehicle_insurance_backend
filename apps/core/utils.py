import random
import string
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client

def generate_otp(length=6):
    """Generate a numeric OTP"""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(email, otp):
    """Send OTP via email"""
    send_mail(
        'Password Reset OTP',
        f'Your OTP for password reset is: {otp}. This OTP is valid for 10 minutes.',
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )

def send_otp_sms(phone_number, otp):
    """Send OTP via SMS using Twilio"""
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f'Your OTP for password reset is: {otp}',
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        return message.sid
    return None

def generate_policy_number():
    """Generate unique policy number"""
    return f"POL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

def generate_claim_number():
    """Generate unique claim number"""
    return f"CLM-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

def calculate_vehicle_premium(vehicle, coverage_amount, add_ons=[]):
    """Calculate insurance premium based on vehicle and coverage"""
    base_premium = 5000
    age_factor = vehicle.vehicle_age * 0.05
    coverage_factor = coverage_amount / 5000000
    add_on_cost = len(add_ons) * 5000
    
    total = base_premium * (1 + age_factor) * coverage_factor + add_on_cost
    return round(total, 2)








import csv
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def export_to_excel(queryset, fields, filename="export.csv"):
    """
    Export queryset to CSV (Excel-readable)
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(fields)

    for obj in queryset:
        row = [getattr(obj, field) for field in fields]
        writer.writerow(row)

    return response


def generate_report(title="Report", data=None):
    """
    Generate simple PDF report
    """
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    p.drawString(100, height - 50, title)

    y = height - 100
    if data:
        for item in data:
            p.drawString(100, y, str(item))
            y -= 20

    p.showPage()
    p.save()

    return response








