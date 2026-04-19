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
from django.db.models import Q

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











# apps/core/views.py
# apps/core/views.py

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from django.urls import reverse  # Add this import
import qrcode
import hashlib
import os
from PIL import Image as PILImage

# ========== CERTIFICATE GENERATION FUNCTIONS ==========

def format_ngn(amount):
    """Format amount as Nigerian Naira with commas"""
    if amount is None:
        return "₦0.00"
    return f"₦{amount:,.2f}"


def generate_policy_certificate(policy, generated_by=None, request=None):
    """
    Generate a professional, single-page PDF certificate for an active policy.
    """
    from apps.core.models import PolicyCertificate, PublicDocument, DocumentCategory
    
    try:
        # Create certificate record
        certificate = PolicyCertificate.objects.create(
            policy=policy,
            generated_by=generated_by,
            status='pending'
        )
        
        certificate_number = certificate.certificate_number
        
        # Create PDF with landscape orientation
        page_width, page_height = landscape(A4)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4), 
            topMargin=15*mm,
            bottomMargin=15*mm,
            leftMargin=15*mm,
            rightMargin=15*mm
        )
        
        # Custom Styles
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'MainTitle',
            parent=styles['Heading1'],
            fontSize=32,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_CENTER,
            spaceAfter=5,
            fontName='Helvetica-Bold',
        )
        
        cert_num_style = ParagraphStyle(
            'CertNumber',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER,
            spaceAfter=10,
            fontName='Helvetica'
        )
        
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=colors.white,
            spaceAfter=0,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        label_style = ParagraphStyle(
            'LabelStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=2,
            fontName='Helvetica',
            alignment=TA_LEFT
        )
        
        value_style = ParagraphStyle(
            'ValueStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=4,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#94a3b8'),
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        story = []
        
        # Background function - draws decorative borders and header bar
        def add_background(canvas, doc):
            canvas.saveState()
            
            # Outer border
            canvas.setStrokeColor(colors.HexColor('#1a365d'))
            canvas.setLineWidth(2)
            canvas.rect(12*mm, 12*mm, page_width-24*mm, page_height-24*mm)
            
            # Inner border
            canvas.setStrokeColor(colors.HexColor('#cbd5e1'))
            canvas.setLineWidth(0.5)
            canvas.rect(14*mm, 14*mm, page_width-28*mm, page_height-28*mm)
            
            # Header background bar - positioned at the top behind the content
            canvas.setFillColor(colors.HexColor('#1a365d'))
            canvas.rect(14*mm, page_height-45*mm, page_width-28*mm, 30*mm, fill=1, stroke=0)
            
            # Footer background bar
            canvas.setFillColor(colors.HexColor('#f8fafc'))
            canvas.rect(14*mm, 14*mm, page_width-28*mm, 14*mm, fill=1, stroke=0)
            
            # Watermark
            canvas.setFillColor(colors.HexColor('#f1f5f9'))
            canvas.setFont('Helvetica-Bold', 60)
            canvas.rotate(45)
            canvas.drawString(80*mm, -20*mm, 'CERTIFIED')
            canvas.rotate(-45)
            
            canvas.restoreState()
        
        # ========== CONTENT STARTS HERE ==========
        story.append(Spacer(1, 8*mm))
        
        # Logo - with proper aspect ratio handling
        logo_path = None
        possible_paths = [
            os.path.join(settings.STATIC_ROOT, 'images/logo.png') if settings.STATIC_ROOT else None,
            os.path.join(settings.STATIC_ROOT, 'images/logo.jpeg') if settings.STATIC_ROOT else None,
            os.path.join(settings.BASE_DIR, 'static/images/logo.png'),
            os.path.join(settings.BASE_DIR, 'static/images/logo.jpeg'),
            os.path.join(settings.STATICFILES_DIRS[0], 'images/logo.png') if settings.STATICFILES_DIRS else None,
            os.path.join(settings.STATICFILES_DIRS[0], 'images/logo.jpeg') if settings.STATICFILES_DIRS else None,
        ]
        
        for path in possible_paths:
            if path and os.path.exists(path):
                logo_path = path
                break
        
        if logo_path and os.path.exists(logo_path):
            try:
                pil_img = PILImage.open(logo_path)
                original_width, original_height = pil_img.size
                aspect_ratio = original_width / original_height
                
                desired_width = 45 * mm
                desired_height = desired_width / aspect_ratio
                
                max_height = 18 * mm
                if desired_height > max_height:
                    desired_height = max_height
                    desired_width = desired_height * aspect_ratio
                
                logo = Image(logo_path, width=desired_width, height=desired_height)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 5*mm))
            except Exception as e:
                print(f"Error loading logo: {e}")
                logo = Image(logo_path, width=45*mm, height=15*mm)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 5*mm))
        else:
            story.append(Spacer(1, 8*mm))
        
        # Title
        story.append(Paragraph("CERTIFICATE OF INSURANCE", title_style))
        story.append(Spacer(1, 3*mm))
        
        # Certificate Number
        cert_num_table = Table([[Paragraph(f"Certificate No: {certificate_number}", cert_num_style)]], 
                               colWidths=[page_width-30*mm])
        cert_num_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(cert_num_table)
        story.append(Spacer(1, 8*mm))
        
        # ========== THREE COLUMN LAYOUT ==========
        holder_details = [
            [Paragraph('Full Name', label_style), 
             Paragraph(policy.user.get_full_name() or policy.user.email, value_style)],
            [Paragraph('Email Address', label_style), 
             Paragraph(policy.user.email, value_style)],
            [Paragraph('Phone Number', label_style), 
             Paragraph(str(policy.user.phone_number) if policy.user.phone_number else 'N/A', value_style)],
            [Paragraph('Address', label_style), 
             Paragraph(policy.user.address or 'N/A', value_style)],
        ]
        
        coverage_amount = format_ngn(policy.coverage_amount)
        premium_amount = format_ngn(policy.premium_amount)
        deductible_amount = format_ngn(policy.deductible)
        
        policy_details = [
            [Paragraph('Policy Number', label_style), 
             Paragraph(policy.policy_number, value_style)],
            [Paragraph('Policy Type', label_style), 
             Paragraph(policy.get_policy_type_display(), value_style)],
            [Paragraph('Coverage Amount', label_style), 
             Paragraph(coverage_amount, value_style)],
            [Paragraph('Premium Amount', label_style), 
             Paragraph(premium_amount, value_style)],
        ]
        
        if policy.vehicle:
            vehicle_details = [
                [Paragraph('Vehicle', label_style), 
                 Paragraph(f'{policy.vehicle.make} {policy.vehicle.model} ({policy.vehicle.year})', value_style)],
                [Paragraph('Registration', label_style), 
                 Paragraph(policy.vehicle.registration_number, value_style)],
                [Paragraph('Vehicle Type', label_style), 
                 Paragraph(policy.vehicle.get_vehicle_type_display(), value_style)],
                [Paragraph('Engine No.', label_style), 
                 Paragraph(policy.vehicle.engine_number[:15] + '...' if len(policy.vehicle.engine_number) > 15 else policy.vehicle.engine_number, value_style)],
            ]
        else:
            vehicle_details = [[Paragraph('No vehicle associated', value_style)]]
        
        three_col_table = Table([
            [
                Table(holder_details, colWidths=[22*mm, 55*mm]),
                Table(policy_details, colWidths=[25*mm, 52*mm]),
                Table(vehicle_details, colWidths=[22*mm, 55*mm]),
            ]
        ], colWidths=[82*mm, 82*mm, 82*mm])
        
        three_col_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(three_col_table)
        story.append(Spacer(1, 6*mm))
        
        # ========== COVERAGE PERIOD ==========
        period_details = Table([[
            Paragraph(f'<b>Start Date:</b> {policy.start_date.strftime("%B %d, %Y")}', value_style),
            Paragraph(f'<b>End Date:</b> {policy.end_date.strftime("%B %d, %Y")}', value_style),
            Paragraph(f'<b>Status:</b> <font color="#10b981">● ACTIVE</font>', value_style),
            Paragraph(f'<b>Deductible:</b> {deductible_amount}', value_style),
        ]], colWidths=[65*mm, 65*mm, 55*mm, 55*mm])
        
        period_details.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(period_details)
        story.append(Spacer(1, 6*mm))
        
        # ========== COVERAGE BENEFITS ==========
        benefits = policy.additional_benefits or []
        if not benefits:
            benefits = [
                "Third Party Liability Coverage",
                "Own Damage Coverage",
                "Personal Accident Cover",
                "Roadside Assistance",
                "Fire and Theft Protection",
                "Legal Protection",
                "Windscreen Cover",
                "Courtesy Car"
            ]
        
        mid = (len(benefits) + 1) // 2
        left_benefits = benefits[:mid]
        right_benefits = benefits[mid:]
        
        benefits_table = Table([[
            Paragraph('<br/>'.join([f'<font color="#10b981">✓</font> {b}' for b in left_benefits]), value_style),
            Paragraph('<br/>'.join([f'<font color="#10b981">✓</font> {b}' for b in right_benefits]), value_style),
        ]], colWidths=[123*mm, 123*mm])
        
        benefits_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ]))
        story.append(benefits_table)
        story.append(Spacer(1, 8*mm))
        
        # ========== QR CODE & FOOTER ==========
        verification_data = f"{certificate_number}|{policy.policy_number}|{policy.user.email}"
        verification_hash = hashlib.sha256(verification_data.encode()).hexdigest()[:16]
        certificate.verification_hash = verification_hash
        
        # FIXED: Build the verification URL correctly
        site_url = getattr(settings, 'SITE_URL', 'https://vehicleinsure.ng')
        verify_url = f"{site_url}/verify-certificate/{certificate_number}/?hash={verification_hash}"
        
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#1a365d", back_color="white")
        
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        certificate.qr_code.save(f"qr_{certificate_number}.png", ContentFile(qr_buffer.getvalue()), save=False)
        qr_image = Image(qr_buffer, width=20*mm, height=20*mm)
        
        footer_row = Table([[
            Table([[
                Paragraph(
                    "<font size='7'>This certificate is electronically generated and valid without a physical signature.<br/>"
                    "Scan the QR code to verify authenticity or visit vehicleinsure.ng/verify</font>",
                    footer_style
                )
            ]], colWidths=[195*mm]),
            qr_image
        ]], colWidths=[215*mm, 31*mm])
        
        footer_row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        story.append(footer_row)
        
        # Build PDF
        doc.build(story, onFirstPage=add_background, onLaterPages=add_background)
        buffer.seek(0)
        
        # Save certificate
        filename = f"certificate_{policy.policy_number}_{timezone.now().strftime('%Y%m%d')}.pdf"
        certificate.certificate_file.save(filename, ContentFile(buffer.getvalue()), save=False)
        certificate.status = 'generated'
        certificate.save()
        
        # Create public document
        doc_category, _ = DocumentCategory.objects.get_or_create(
            name='Insurance Certificates',
            defaults={'slug': 'insurance-certificates', 'is_active': True}
        )
        
        public_doc = PublicDocument.objects.create(
            title=f"Insurance Certificate - {policy.policy_number}",
            slug=f"certificate-{policy.policy_number.lower()}",
            user=policy.user,
            policy=policy,
            category=doc_category,
            document_type='certificate',
            document_file=certificate.certificate_file,
            document_number=certificate_number,
            description=f"Insurance certificate for policy #{policy.policy_number}",
            issue_date=timezone.now().date(),
            valid_until=policy.end_date,
            status='published',
            is_public=True,
            is_verified=True,
            verification_hash=verification_hash,
            created_by=generated_by or policy.user,
        )
        
        return {
            'success': True,
            'certificate': certificate,
            'public_document': public_doc,
            'message': 'Certificate generated successfully'
        }
        
    except Exception as e:
        import traceback
        print(f"Certificate Generation Error: {traceback.format_exc()}")
        if 'certificate' in locals():
            certificate.status = 'failed'
            certificate.metadata = {'error': str(e)}
            certificate.save()
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to generate certificate: {str(e)}'
        }


def regenerate_certificate(policy, generated_by=None, request=None):
    """Regenerate certificate for an existing policy"""
    from apps.core.models import PublicDocument
    import os
    
    try:
        # Delete existing certificate
        if hasattr(policy, 'certificate'):
            certificate = policy.certificate
            
            if certificate.certificate_file:
                try:
                    if os.path.isfile(certificate.certificate_file.path):
                        os.remove(certificate.certificate_file.path)
                except Exception as e:
                    print(f"Error deleting certificate file: {e}")
            
            if certificate.qr_code:
                try:
                    if os.path.isfile(certificate.qr_code.path):
                        os.remove(certificate.qr_code.path)
                except Exception as e:
                    print(f"Error deleting QR code file: {e}")
            
            certificate.delete()
        
        # Delete associated public document
        PublicDocument.objects.filter(policy=policy, document_type='certificate').delete()
        
        # Generate new certificate
        return generate_policy_certificate(policy, generated_by, request)
        
    except Exception as e:
        import traceback
        print(f"Error in regenerate_certificate: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to regenerate certificate: {str(e)}'
        }


def generate_policy_document(policy):
    """Generate PDF policy document"""
    from io import BytesIO
    from django.core.files.base import ContentFile
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    def ngn(amount):
        return f"₦{amount:,.2f}" if amount else "₦0.00"
    
    p.drawString(100, 750, "VEHICLE INSURANCE POLICY")
    p.drawString(100, 730, f"Policy Number: {policy.policy_number}")
    p.drawString(100, 710, f"Policy Holder: {policy.user.get_full_name()}")
    if policy.vehicle:
        p.drawString(100, 690, f"Vehicle: {policy.vehicle.make} {policy.vehicle.model}")
        p.drawString(100, 670, f"Registration: {policy.vehicle.registration_number}")
    p.drawString(100, 650, f"Coverage Type: {policy.get_policy_type_display()}")
    p.drawString(100, 630, f"Coverage Amount: {ngn(policy.coverage_amount)}")
    p.drawString(100, 610, f"Premium Amount: {ngn(policy.premium_amount)}")
    p.drawString(100, 590, f"Start Date: {policy.start_date}")
    p.drawString(100, 570, f"End Date: {policy.end_date}")
    
    p.save()
    
    buffer.seek(0)
    return ContentFile(buffer.getvalue(), f"policy_{policy.policy_number}.pdf")






# apps/core/utils.py - Add this helper function

from decimal import Decimal
from django.utils import timezone
from apps.core.models import CommissionStructure, AgentCommissionOverride

def calculate_agent_commission(agent, policy, premium_amount):
    """
    Calculate commission for an agent based on policy and premium.
    Returns dict with commission details.
    """
    today = timezone.now().date()
    
    # Check for agent-specific override first
    override = AgentCommissionOverride.objects.filter(
        agent=agent,
        policy_type=policy.policy_type,
        is_active=True,
        effective_from__lte=today
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    ).first()
    
    if override:
        commission_rate = override.commission_rate
        bonus_amount = Decimal('0')
        bonus_reason = ''
        structure_used = None
    else:
        # Get agent's profile for agent type
        try:
            agent_profile = agent.agent_profile
            agent_type = agent_profile.agent_type
        except:
            agent_type = 'individual'
        
        # Get applicable commission structure
        structure = CommissionStructure.get_applicable_structure(
            policy.policy_type,
            agent_type,
            today
        )
        
        if structure:
            commission_rate = structure.calculate_commission_rate(premium_amount)
            bonus_amount = structure.calculate_bonus(premium_amount)
            bonus_reason = f"Bonus from {structure.name}" if bonus_amount > 0 else ''
            structure_used = structure
        else:
            # Default fallback
            commission_rate = Decimal('10.00')
            bonus_amount = Decimal('0')
            bonus_reason = ''
            structure_used = None
    
    commission_amount = premium_amount * (commission_rate / Decimal('100'))
    total_commission = commission_amount + bonus_amount
    
    return {
        'commission_rate': commission_rate,
        'commission_amount': commission_amount,
        'bonus_amount': bonus_amount,
        'bonus_reason': bonus_reason,
        'total_commission': total_commission,
        'structure_used': structure_used,
        'override_used': override,
    }