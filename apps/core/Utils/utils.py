from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client
from decimal import Decimal
import random
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from apps.core.models import UserActivityLog  # Correct import
from decimal import Decimal, InvalidOperation

def log_user_activity(user, action, request, details=None):
    """Log user activity"""
    if details is None:
        details = {}
    
    try:
        UserActivityLog.objects.create(
            user=user,
            action=action,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            details=details
        )
    except Exception as e:
        print(f"Error logging user activity: {e}")

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip





from decimal import Decimal
from django.utils import timezone
from apps.core.models import InsuranceSettings

def calculate_premium(vehicle, coverage_type, coverage_amount, add_ons=None):
    """Calculate insurance premium using dynamic settings"""
    
    # Get settings
    settings = InsuranceSettings.get_settings()
    
    # Convert coverage_amount to Decimal
    try:
        if isinstance(coverage_amount, str):
            coverage_amount = coverage_amount.replace('₦', '').replace(',', '').strip()
            coverage_amount = Decimal(coverage_amount)
        elif not isinstance(coverage_amount, Decimal):
            coverage_amount = Decimal(str(coverage_amount))
    except:
        coverage_amount = settings.base_coverage_reference
    
    # Base premium from settings
    base_premium = settings.base_premium_amount
    
    # Vehicle age multiplier
    vehicle_age = timezone.now().year - vehicle.year
    if vehicle_age <= 1:
        age_multiplier = settings.age_0_1_multiplier
    elif vehicle_age <= 3:
        age_multiplier = settings.age_2_3_multiplier
    elif vehicle_age <= 5:
        age_multiplier = settings.age_4_5_multiplier
    elif vehicle_age <= 10:
        age_multiplier = settings.age_6_10_multiplier
    else:
        age_multiplier = settings.age_10_plus_multiplier
    base_premium *= age_multiplier
    
    # Vehicle type multiplier
    vehicle_type_multipliers = {
        'car': settings.car_multiplier,
        'motorcycle': settings.motorcycle_multiplier,
        'truck': settings.truck_multiplier,
        'bus': settings.bus_multiplier,
        'rickshaw': settings.rickshaw_multiplier,
    }
    base_premium *= vehicle_type_multipliers.get(vehicle.vehicle_type, Decimal('1.0'))
    
    # Engine capacity multiplier
    if vehicle.engine_capacity:
        if vehicle.engine_capacity > 3000:
            base_premium *= settings.engine_above_3000_multiplier
        elif vehicle.engine_capacity > 2000:
            base_premium *= settings.engine_2000_3000_multiplier
        elif vehicle.engine_capacity > 1000:
            base_premium *= settings.engine_1000_2000_multiplier
        else:
            base_premium *= settings.engine_below_1000_multiplier
    
    # Coverage type multiplier
    coverage_multipliers = {
        'comprehensive': settings.comprehensive_multiplier,
        'third_party': settings.third_party_multiplier,
        'standalone': settings.standalone_multiplier,
        'personal_accident': settings.personal_accident_multiplier,
    }
    coverage_multiplier = coverage_multipliers.get(coverage_type, Decimal('1.0'))
    total_premium = base_premium * coverage_multiplier
    
    # Adjust based on coverage amount
    if coverage_amount > settings.base_coverage_reference:
        coverage_factor = coverage_amount / settings.base_coverage_reference
        if coverage_factor > Decimal('10'):
            coverage_factor = Decimal('10') + (coverage_factor - Decimal('10')) * Decimal('0.5')
        total_premium *= coverage_factor
    
    # Apply minimum premium
    min_premiums = {
        'comprehensive': settings.min_premium_comprehensive,
        'third_party': settings.min_premium_third_party,
        'standalone': settings.min_premium_standalone,
        'personal_accident': settings.min_premium_personal_accident,
    }
    min_premium = min_premiums.get(coverage_type, Decimal('25000'))
    total_premium = max(total_premium, min_premium)
    
    # Add-on costs
    add_ons_list = []
    add_ons_cost = Decimal('0')
    add_on_costs = {
        'roadside_assistance': settings.roadside_assistance_cost,
        'zero_depreciation': settings.zero_depreciation_cost,
        'engine_protection': settings.engine_protection_cost,
        'personal_accident_cover': settings.personal_accident_cover_cost,
    }
    
    if add_ons:
        for addon in add_ons:
            if addon in add_on_costs:
                add_ons_list.append(addon.replace('_', ' ').title())
                add_ons_cost += add_on_costs[addon]
    
    total_premium += add_ons_cost
    
    # Default add-ons for comprehensive
    if coverage_type == 'comprehensive' and not add_ons:
        add_ons_list = ['Roadside Assistance', 'Zero Depreciation', 'Engine Protection']
        total_premium += (settings.roadside_assistance_cost + 
                         settings.zero_depreciation_cost + 
                         settings.engine_protection_cost)
    
    # Calculate deductible
    deductible = total_premium * (settings.deductible_percentage / Decimal('100'))
    deductible = max(min(deductible, settings.max_deductible), settings.min_deductible)
    
    # Coverage details
    coverage_details = {
        'Own Damage': coverage_type in ['comprehensive', 'standalone'],
        'Theft Protection': coverage_type == 'comprehensive',
        'Fire Damage': coverage_type == 'comprehensive',
        'Third Party Liability': True,
        'Personal Accident': coverage_type in ['comprehensive', 'personal_accident'],
        'Medical Expenses': coverage_type == 'comprehensive',
        'Roadside Assistance': 'roadside_assistance' in str(add_ons_list).lower() or coverage_type == 'comprehensive',
        'Flood Damage': coverage_type == 'comprehensive',
        'Riot & Strike': coverage_type == 'comprehensive',
    }
    
    return {
        'base_premium': round(base_premium, 2),
        'total_premium': round(total_premium, 2),
        'deductible': round(deductible, 2),
        'coverage_details': coverage_details,
        'add_ons': add_ons_list,
        'add_ons_cost': round(add_ons_cost, 2)
    }

def generate_policy_document(policy):
    """Generate PDF policy document"""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Add content
    p.drawString(100, 750, "VEHICLE INSURANCE POLICY")
    p.drawString(100, 730, f"Policy Number: {policy.policy_number}")
    p.drawString(100, 710, f"Policy Holder: {policy.user.get_full_name()}")
    p.drawString(100, 690, f"Vehicle: {policy.vehicle.make} {policy.vehicle.model}")
    p.drawString(100, 670, f"Registration: {policy.vehicle.registration_number}")
    p.drawString(100, 650, f"Coverage Type: {policy.get_policy_type_display()}")
    p.drawString(100, 630, f"Coverage Amount: ${policy.coverage_amount}")
    p.drawString(100, 610, f"Premium Amount: ${policy.premium_amount}")
    p.drawString(100, 590, f"Start Date: {policy.start_date}")
    p.drawString(100, 570, f"End Date: {policy.end_date}")
    
    p.save()
    
    buffer.seek(0)
    return ContentFile(buffer.getvalue(), f"policy_{policy.policy_number}.pdf")

def send_email_notification(to_email, subject, message):
    """Send email notification"""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def send_sms_notification(phone_number, message):
    """Send SMS notification using Twilio"""
    if not settings.TWILIO_ACCOUNT_SID:
        return False
    
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=str(phone_number)
        )
        return True
    except Exception as e:
        print(f"SMS sending failed: {e}")
        return False

def process_payment(payment, payment_method):
    """Process payment (simplified version)"""
    try:
        # Simulate payment processing
        transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        
        return {
            'success': True,
            'details': {
                'transaction_id': transaction_id,
                'payment_method': payment_method,
                'status': 'completed'
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def generate_otp():
    """Generate 6-digit OTP"""
    return str(random.randint(100000, 999999))

def calculate_claim_settlement(claim):
    """Calculate claim settlement amount"""
    policy = claim.policy
    
    # Apply deductible
    settlement_amount = claim.claimed_amount - policy.deductible
    
    # Apply coverage limit
    if settlement_amount > policy.coverage_amount:
        settlement_amount = policy.coverage_amount
    
    return max(settlement_amount, 0)