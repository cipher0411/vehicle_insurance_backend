from django.shortcuts import render
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from django.db.models import Sum
import json
import uuid
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone

from apps.core.models import (
    User, Vehicle, InsurancePolicy, Claim, Payment, 
    InsuranceQuote, Notification, Document, SupportTicket, 
    TicketReply, PromoCode, UserActivityLog, InsuranceSettings, 
    PolicyCertificate, PolicyEndorsement, PolicyRenewal, NoClaimBonus, 
    CommissionStructure, Commission, DebitCreditNote, InstallmentPlan, Installment, ReinsuranceTreaty,
    AgentProfile, AgentReferral, 
)

from apps.core.forms import (
    UserRegistrationForm, UserLoginForm, VehicleForm, 
    PolicyPurchaseForm, ClaimForm, ProfileUpdateForm,
    SupportTicketForm, TicketReplyForm, PasswordChangeForm
)
from apps.core.decorators import role_required
from .Utils.utils import (
    calculate_premium, generate_policy_document, 
    send_email_notification, send_sms_notification,
    log_user_activity, process_payment
)





def get_started(request):
    """Get Started page with login and registration options"""
    
    # If user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    context = {
        'page_title': 'Get Started with VehicleInsure',
        'features': [
            {
                'icon': 'fa-shield-alt',
                'title': 'Comprehensive Coverage',
                'description': 'Full protection for your vehicle against accidents, theft, and third-party liability.'
            },
            {
                'icon': 'fa-bolt',
                'title': 'Instant Quotes',
                'description': 'Get personalized insurance quotes in minutes with our easy-to-use calculator.'
            },
            {
                'icon': 'fa-file-invoice',
                'title': 'Digital Certificates',
                'description': 'Receive your insurance certificate instantly via email and access it anytime.'
            },
            {
                'icon': 'fa-headset',
                'title': '24/7 Support',
                'description': 'Our dedicated support team is always available to assist you.'
            },
        ],
        'benefits': [
            'No hidden fees or charges',
            'Flexible payment options',
            'Quick claims processing',
            'Multi-vehicle discounts',
            'Free roadside assistance',
            'Easy policy renewal',
        ],
        'stats': [
            {'value': '50K+', 'label': 'Happy Customers'},
            {'value': '₦2B+', 'label': 'Claims Paid'},
            {'value': '98%', 'label': 'Satisfaction Rate'},
            {'value': '24/7', 'label': 'Support Available'},
        ]
    }
    
    return render(request, 'core/public/get_started.html', context)



def register(request):
    """User registration view with agent referral support"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    # Get referral code from URL
    ref_code = request.GET.get('ref', '')
    referred_by = None
    
    if ref_code:
        try:
            agent_profile = AgentProfile.objects.select_related('user').get(agent_code=ref_code, is_active=True)
            referred_by = agent_profile.user
        except AgentProfile.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                
                # Set referred_by from URL parameter (stored in session or hidden field)
                ref_code_post = request.POST.get('referral_code', '')
                if ref_code_post:
                    try:
                        agent_profile = AgentProfile.objects.select_related('user').get(
                            agent_code=ref_code_post, 
                            is_active=True
                        )
                        user.referred_by = agent_profile.user
                        user.referral_code = ref_code_post
                    except AgentProfile.DoesNotExist:
                        pass
                elif referred_by:
                    user.referred_by = referred_by
                    user.referral_code = ref_code
                
                user.save()
                
                # Create AgentReferral record if user was referred by an agent
                if user.referred_by and user.referred_by.role == 'agent':
                    AgentReferral.objects.get_or_create(
                        agent=user.referred_by,
                        customer=user,
                        defaults={
                            'referral_code': user.referral_code,
                            'referral_source': 'registration'
                        }
                    )
                    
                    # Notify the agent
                    Notification.objects.create(
                        user=user.referred_by,
                        title='New Customer Registered',
                        message=f'{user.get_full_name() or user.email} registered using your referral link!',
                        notification_type='system_alert',
                        data={'customer_id': str(user.id)}
                    )
                
                # Log registration
                log_user_activity(user, 'register', request)
                
                # Send welcome email
                try:
                    send_email_notification(
                        user.email,
                        'Welcome to Vehicle Insurance',
                        f'Welcome {user.get_full_name() or user.email}, thank you for registering!'
                    )
                except Exception as e:
                    print(f"Welcome email failed: {e}")
                
                messages.success(request, 'Registration successful! Please login.')
                return redirect('core:login')
                
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
                print(f"Registration error: {e}")
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()
    
    context = {
        'form': form,
        'referred_by': referred_by,
        'ref_code': ref_code,
    }
    
    return render(request, 'core/register.html', context)


def user_login(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                
                # Update last login IP
                user.last_login_ip = get_client_ip(request)
                user.save(update_fields=['last_login_ip'])
                
                # Log login activity
                log_user_activity(user, 'login', request)
                
                messages.success(request, f'Welcome back, {user.get_full_name() or user.email}!')
                
                # Redirect based on role
                if user.role == 'admin':
                    return redirect('core:admin_dashboard')
                elif user.role == 'agent':
                    return redirect('core:agent_dashboard')
                elif user.role in ['underwriter', 'claims_adjuster', 'support']:
                    return redirect('core:staff_dashboard')
                else:
                    return redirect('core:dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = UserLoginForm()
    
    return render(request, 'core/login.html', {'form': form})

def user_logout(request):
    """User logout view"""
    if request.user.is_authenticated:
        log_user_activity(request.user, 'logout', request)
        logout(request)
        messages.info(request, 'You have been logged out.')
    return redirect('core:login')



# Add to views.py

from django.contrib.auth import views as auth_views
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.urls import reverse_lazy, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from .forms import CustomPasswordResetForm, CustomSetPasswordForm

User = get_user_model()


class CustomPasswordResetView(auth_views.PasswordResetView):
    """Custom password reset view"""
    form_class = CustomPasswordResetForm
    template_name = 'core/auth/password_reset.html'
    email_template_name = 'core/emails/password_reset_email.html'
    subject_template_name = 'core/emails/password_reset_subject.txt'
    success_url = reverse_lazy('core:password_reset_done')
    
    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        """Send email with both plain text and HTML"""
        print(f"📧 Attempting to send email to: {to_email}")
        print(f"📝 From email: {from_email}")
        print(f"🔧 Context keys: {context.keys()}")
        
        subject = render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())
        print(f"📋 Subject: {subject}")
        
        html_content = render_to_string(email_template_name, context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email],
        )
        email.attach_alternative(html_content, "text/html")
        
        try:
            result = email.send(fail_silently=False)
            print(f"✅ Email sent! Result: {result}")
            return result
        except Exception as e:
            print(f"❌ Email failed: {e}")
            raise


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """Password reset done view"""
    template_name = 'core/auth/password_reset_done.html'


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """Password reset confirm view"""
    form_class = CustomSetPasswordForm
    template_name = 'core/auth/password_reset_confirm.html'
    success_url = reverse_lazy('core:password_reset_complete')
    
    def form_valid(self, form):
        """Send confirmation email after password change"""
        response = super().form_valid(form)
        
        # Send confirmation email
        user = form.user
        current_site = get_current_site(self.request)
        
        context = {
            'user': user,
            'user_email': user.email,
            'site_name': current_site.name,
            'protocol': 'https' if self.request.is_secure() else 'http',
            'domain': current_site.domain,
            'site_url': f"{'https' if self.request.is_secure() else 'http'}://{current_site.domain}",
        }
        
        subject = 'VehicleInsure - Password Changed Successfully'
        
        try:
            html_content = render_to_string('core/emails/password_reset_confirmation.html', context)
            text_content = strip_tags(html_content)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,  # Fixed from_email
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)  # Changed to False for debugging
            print(f"Confirmation email sent to {user.email}")
        except Exception as e:
            print(f"Failed to send confirmation email: {e}")
            # Don't fail the password reset if email fails
            pass
        
        messages.success(self.request, 'Your password has been successfully changed! You can now log in with your new password.')
        
        return response


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """Password reset complete view"""
    template_name = 'core/auth/password_reset_complete.html'
    
    
    
    
    

@login_required
def dashboard(request):
    """Customer dashboard view"""
    user = request.user
    
    # Get user data
    vehicles = user.vehicles.all()
    
    # Get policies
    all_policies = user.policies.all().order_by('-created_at')
    policies = all_policies[:5]
    active_policies_count = all_policies.filter(status='active').count()
    
    # Get claims
    all_claims = user.claims.all().order_by('-created_at')
    claims = all_claims[:5]
    
    # Get notifications
    notifications = user.notifications.filter(is_read=False)[:10]
    
    # Calculate statistics
    total_premium_paid = user.payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    pending_claims = user.claims.filter(status__in=['pending', 'under_review']).count()
    insured_vehicles_count = vehicles.filter(is_insured=True).count()
    
    context = {
        'vehicles': vehicles,
        'policies': policies,
        'claims': claims,
        'notifications': notifications,
        'active_policies_count': active_policies_count,
        'total_premium_paid': total_premium_paid,
        'pending_claims': pending_claims,
        'insured_vehicles_count': insured_vehicles_count,
        'recent_activities': user.activities.all()[:10],
    }
    return render(request, 'core/customer/dashboard.html', context)

@login_required
def vehicles(request):
    """Manage vehicles view"""
    user = request.user
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.user = user
            vehicle.save()
            messages.success(request, 'Vehicle added successfully!')
            return redirect('core:vehicles')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = VehicleForm()
    
    vehicles_list = user.vehicles.all().order_by('-created_at')
    
    # Calculate statistics
    insured_count = vehicles_list.filter(is_insured=True).count()
    uninsured_count = vehicles_list.filter(is_insured=False).count()
    total_mileage = vehicles_list.aggregate(Sum('current_mileage'))['current_mileage__sum'] or 0
    
    paginator = Paginator(vehicles_list, 9)
    page = request.GET.get('page')
    vehicles = paginator.get_page(page)
    
    return render(request, 'core/customer/vehicles.html', {
        'vehicles': vehicles,
        'form': form,
        'insured_count': insured_count,
        'uninsured_count': uninsured_count,
        'total_mileage': total_mileage,
    })
    
    

@login_required
def edit_vehicle(request, vehicle_id):
    """Edit vehicle details"""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, user=request.user)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle updated successfully!')
            return redirect('core:vehicles')
    else:
        form = VehicleForm(instance=vehicle)
    
    return render(request, 'core/customer/edit_vehicle.html', {
        'form': form,
        'vehicle': vehicle
    })

@login_required
def delete_vehicle(request, vehicle_id):
    """Delete vehicle"""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, user=request.user)
    
    if request.method == 'POST':
        vehicle.delete()
        messages.success(request, 'Vehicle deleted successfully!')
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}, status=400)

@login_required
def get_quote(request):
    """Get insurance quote for vehicle"""
    if request.method == 'POST':
        try:
            vehicle_id = request.POST.get('vehicle_id')
            coverage_type = request.POST.get('coverage_type')
            coverage_amount = request.POST.get('coverage_amount')
            
            # Validate inputs
            if not all([vehicle_id, coverage_type, coverage_amount]):
                return JsonResponse({'error': 'Missing required fields'}, status=400)
            
            vehicle = get_object_or_404(Vehicle, id=vehicle_id, user=request.user)
            
            # Clean coverage amount
            if isinstance(coverage_amount, str):
                coverage_amount = coverage_amount.replace('₦', '').replace(',', '').strip()
            
            # Calculate premium
            premium_data = calculate_premium(vehicle, coverage_type, coverage_amount)
            
            # Get add-ons
            add_ons = request.POST.get('add_ons', '[]')
            try:
                import json
                add_ons_list = json.loads(add_ons)
                premium_data['add_ons'].extend(add_ons_list)
            except:
                pass
            
            # Check promo code
            promo_code = request.POST.get('promo_code')
            discount_amount = Decimal('0')
            
            if promo_code:
                try:
                    promo = PromoCode.objects.get(
                        code=promo_code.upper(), 
                        is_active=True,
                        valid_from__lte=timezone.now(),
                        valid_to__gte=timezone.now()
                    )
                    if promo.used_count < promo.max_uses:
                        if promo.discount_type == 'percentage':
                            discount_amount = premium_data['total_premium'] * (promo.discount_value / Decimal('100'))
                        else:
                            discount_amount = promo.discount_value
                except PromoCode.DoesNotExist:
                    pass
            
            final_premium = premium_data['total_premium'] - discount_amount
            final_premium = max(final_premium, Decimal('0'))
            
            # Save quote
            quote = InsuranceQuote.objects.create(
                user=request.user,
                vehicle=vehicle,
                coverage_type=coverage_type,
                base_premium=premium_data['base_premium'],
                total_premium=final_premium,
                coverage_amount=Decimal(coverage_amount),
                deductible=premium_data['deductible'],
                coverage_details=premium_data['coverage_details'],
                add_ons=premium_data['add_ons'],
                valid_until=timezone.now() + timezone.timedelta(days=30),
                status='approved'
            )
            
            log_user_activity(request.user, 'get_quote', request, {
                'quote_id': str(quote.id),
                'premium': str(final_premium)
            })
            
            return JsonResponse({
                'quote_id': str(quote.id),
                'base_premium': str(premium_data['base_premium']),
                'total_premium': str(final_premium),
                'deductible': str(premium_data['deductible']),
                'coverage_details': premium_data['coverage_details'],
                'add_ons': premium_data['add_ons'],
                'discount_applied': discount_amount > 0,
                'discount_amount': str(discount_amount) if discount_amount > 0 else '0'
            })
            
        except Vehicle.DoesNotExist:
            return JsonResponse({'error': 'Vehicle not found'}, status=404)
        except Exception as e:
            import traceback
            print(f"Quote Error: {traceback.format_exc()}")
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - load page with settings
    vehicles = request.user.vehicles.all().order_by('-created_at')
    settings = InsuranceSettings.get_settings()
    
    context = {
        'vehicles': vehicles,
        'settings': settings,
        'roadside_assistance_cost': int(settings.roadside_assistance_cost),
        'zero_depreciation_cost': int(settings.zero_depreciation_cost),
        'engine_protection_cost': int(settings.engine_protection_cost),
        'personal_accident_cover_cost': int(settings.personal_accident_cover_cost),
    }
    
    return render(request, 'core/customer/get_quote.html', context)


@login_required
@require_http_methods(["POST"])
def validate_promo_code(request):
    """Validate promo code"""
    try:
        data = json.loads(request.body)
        promo_code = data.get('promo_code', '').strip().upper()
        
        if not promo_code:
            return JsonResponse({'valid': False, 'message': 'Please enter a promo code'})
        
        try:
            promo = PromoCode.objects.get(code=promo_code, is_active=True)
            
            if not promo.is_valid:
                if promo.valid_from > timezone.now():
                    return JsonResponse({'valid': False, 'message': 'Promo code is not yet valid'})
                elif promo.valid_to < timezone.now():
                    return JsonResponse({'valid': False, 'message': 'Promo code has expired'})
                elif promo.used_count >= promo.max_uses:
                    return JsonResponse({'valid': False, 'message': 'Promo code usage limit reached'})
                else:
                    return JsonResponse({'valid': False, 'message': 'Invalid promo code'})
            
            discount_text = f"{promo.discount_value}%" if promo.discount_type == 'percentage' else f"₦{promo.discount_value:,.2f}"
            return JsonResponse({
                'valid': True,
                'message': f'Promo code applied! {discount_text} discount.',
                'code': promo.code,
                'discount_type': promo.discount_type,
                'discount_value': float(promo.discount_value)
            })
            
        except PromoCode.DoesNotExist:
            return JsonResponse({'valid': False, 'message': 'Invalid promo code'})
            
    except Exception as e:
        return JsonResponse({'valid': False, 'message': 'Error validating promo code'})
    
    
@login_required
def promotions(request):
    """Display available promotions for users"""
    now = timezone.now()
    available_promos = PromoCode.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(used_count__gte=models.F('max_uses'))
    
    # Filter by user eligibility
    eligible_promos = []
    for promo in available_promos:
        if promo.is_valid_for_user(request.user):  # Pass the user argument
            eligible_promos.append(promo)
    
    return render(request, 'core/customer/promotions.html', {
        'promotions': eligible_promos
    })
    
    
    
# apps/core/views.py - Complete payment-related views

from datetime import timedelta
from decimal import Decimal
import uuid
import json
import hashlib
import hmac
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings as django_settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
import requests
import logging

from .models import (
    User, Vehicle, InsurancePolicy, Payment, InsuranceQuote, 
    PromoCode, Notification, InsuranceSettings, InstallmentPlan, Installment,
    PolicyCertificate, 
)
from .forms import PolicyPurchaseForm
from .Utils.utils import generate_policy_document, log_user_activity, generate_policy_certificate
from .decorators import admin_required

logger = logging.getLogger(__name__)


# ============================================
# POLICY PURCHASE VIEW
# ============================================
@login_required
def purchase_policy(request, quote_id=None):
    """Purchase insurance policy - Creates draft policy, redirects to payment"""
    from decimal import Decimal
    
    quote = None
    if quote_id:
        quote = get_object_or_404(InsuranceQuote, id=quote_id, user=request.user)
    
    settings = InsuranceSettings.get_settings()
    
    if request.method == 'POST':
        # Initialize form
        if quote:            form = PolicyPurchaseForm(request.POST)
        else:
            form = PolicyPurchaseForm(request.POST)
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                return redirect(request.path)
        
        try:
            # Get policy data from quote or form
            if quote:
                vehicle = quote.vehicle
                coverage_type = quote.coverage_type
                coverage_amount = quote.coverage_amount
                base_premium = quote.base_premium
                total_premium = quote.total_premium
                deductible = quote.deductible
                add_ons = quote.add_ons
                coverage_details = quote.coverage_details
            else:
                vehicle_id = request.POST.get('vehicle_id')
                coverage_type = request.POST.get('coverage_type')
                coverage_amount = request.POST.get('coverage_amount')
                
                if not all([vehicle_id, coverage_type, coverage_amount]):
                    messages.error(request, 'Please fill in all required fields')
                    return redirect(request.path)
                
                vehicle = get_object_or_404(Vehicle, id=vehicle_id, user=request.user)
                
                from .Utils.utils import calculate_premium
                premium_data = calculate_premium(vehicle, coverage_type, coverage_amount)
                base_premium = premium_data['base_premium']
                total_premium = premium_data['total_premium']
                deductible = premium_data['deductible']
                add_ons = premium_data['add_ons']
                coverage_details = premium_data['coverage_details']
            
            # Process promo code
            promo_code = request.POST.get('promo_code', '').strip()
            discount = Decimal('0')
            promo_applied = None
            
            if promo_code:
                try:
                    promo = PromoCode.objects.get(
                        code=promo_code.upper(), 
                        is_active=True,
                        valid_from__lte=timezone.now(),
                        valid_to__gte=timezone.now()
                    )
                    if promo.used_count < promo.max_uses and promo.is_valid_for_user(request.user):
                        if promo.discount_type == 'percentage':
                            discount = total_premium * (promo.discount_value / Decimal('100'))
                            if promo.max_discount_amount:
                                discount = min(discount, promo.max_discount_amount)
                        else:
                            discount = promo.discount_value
                        promo_applied = promo
                        request.session['pending_promo'] = promo.code
                        messages.success(request, f'Promo code applied! Discount: ₦{discount:,.2f}')
                except PromoCode.DoesNotExist:
                    messages.warning(request, 'Invalid or expired promo code')
            
            final_premium = total_premium - discount
            final_premium = max(final_premium, Decimal('0'))
            
            # Get payment details
            payment_method = request.POST.get('payment_method', 'card')
            payment_plan = request.POST.get('payment_plan', 'full')
            
            # Check terms accepted
            terms_accepted = request.POST.get('terms_accepted') == 'on'
            if not terms_accepted:
                messages.error(request, 'You must accept the terms and conditions')
                return redirect(request.path)
            
            # Create policy with DRAFT status - NOT ACTIVE YET
            policy = InsurancePolicy.objects.create(
                user=request.user,
                vehicle=vehicle,
                policy_type=coverage_type,
                coverage_amount=Decimal(str(coverage_amount)),
                premium_amount=final_premium,
                deductible=deductible,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timezone.timedelta(days=365),
                additional_benefits=add_ons,
                custom_coverage=coverage_details,
                terms_accepted=True,
                status='draft'  # IMPORTANT: Start as draft, not pending
            )
            
            # Generate policy document
            try:
                policy_doc = generate_policy_document(policy)
                policy.policy_document = policy_doc
                policy.save()
            except Exception as e:
                print(f"Error generating policy document: {e}")
            
            # Store promo applied flag for after payment
            if promo_applied:
                request.session['pending_promo_id'] = str(promo_applied.id)
            
            # Handle installment payment
            if payment_plan == 'installment':
                result = setup_installment_payment(request, policy, final_premium, payment_method)
                if result['success']:
                    # Increment promo usage
                    if promo_applied:
                        promo_applied.used_count += 1
                        promo_applied.save()
                        if 'pending_promo' in request.session:
                            del request.session['pending_promo']
                        if 'pending_promo_id' in request.session:
                            del request.session['pending_promo_id']
                    
                    messages.success(request, 'Installment plan created! Please complete your down payment to activate your policy.')
                    return redirect('core:pay_installment', installment_id=result['installment_id'])
                else:
                    # Rollback policy creation
                    policy.delete()
                    messages.error(request, result['message'])
                    return redirect(request.path)
            
            # Handle full payment
            else:
                # Use the model's class method to generate unique references
                transaction_id = Payment.generate_unique_transaction_id('TXN')
                payment_reference = Payment.generate_unique_reference('PAY')
                
                payment = Payment.objects.create(
                    policy=policy,
                    user=request.user,
                    amount=final_premium,
                    payment_method=payment_method,
                    transaction_id=transaction_id,
                    payment_reference=payment_reference,
                    status='pending'
                )
                
                # Increment promo usage
                if promo_applied:
                    promo_applied.used_count += 1
                    promo_applied.save()
                    if 'pending_promo' in request.session:
                        del request.session['pending_promo']
                    if 'pending_promo_id' in request.session:
                        del request.session['pending_promo_id']
                
                # Log activity
                log_user_activity(request.user, 'initiate_policy_purchase', request, {
                    'policy_id': str(policy.id),
                    'premium': str(final_premium),
                    'payment_method': payment_method,
                    'payment_plan': 'full'
                })
                
                # NO NOTIFICATION HERE - Only after successful payment
                # NO POLICY ACTIVATION HERE - Only after successful payment
                
                messages.info(request, 'Please complete your payment to activate your policy.')
                
                # Redirect based on payment method
                if payment_method == 'card':
                    return redirect('core:process_card_payment', payment_id=payment.id)
                elif payment_method == 'bank_transfer':
                    return redirect('core:bank_transfer_instructions', payment_id=payment.id)
                else:
                    return redirect('core:payment_page', payment_id=payment.id)
                
        except Exception as e:
            import traceback
            print(f"Purchase Error: {traceback.format_exc()}")
            messages.error(request, f'Error creating policy: {str(e)}')
            return redirect(request.path)
    else:
        initial_data = {}
        if quote:
            initial_data = {
                'vehicle_id': str(quote.vehicle.id),
                'coverage_type': quote.coverage_type,
                'coverage_amount': str(quote.coverage_amount)
            }
        form = PolicyPurchaseForm(initial=initial_data)
    
    vehicles = request.user.vehicles.all()
    
    # Get installment settings
    installment_settings = {
        'min_down_payment_percentage': Decimal('30'),
        'interest_rate': Decimal('5'),
        'max_installments': 12,
        'allowed_frequencies': ['monthly', 'quarterly'],
    }
    
    context = {
        'form': form,
        'vehicles': vehicles,
        'quote': quote,
        'settings': settings,
        'installment_settings': installment_settings,
    }
    
    if quote:
        context.update({
            'addons_cost': float(quote.total_premium - quote.base_premium),
            'final_premium': float(quote.total_premium),
        })
    
    return render(request, 'core/customer/purchase_policy.html', context)


# ============================================
# PAYMENT PAGE VIEWS
# ============================================

@login_required
def payment_page(request, payment_id):
    """Main payment page - shows payment options (Card or Bank Transfer)"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    if payment.status == 'completed':
        return redirect('core:payment_success', payment_id=payment.id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'card':
            return redirect('core:process_card_payment', payment_id=payment.id)
        elif payment_method == 'bank_transfer':
            return redirect('core:bank_transfer_instructions', payment_id=payment.id)
        else:
            messages.error(request, 'Please select a valid payment method')
            return redirect('core:payment_page', payment_id=payment.id)
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'core/customer/payment_page.html', context)


@login_required
def process_card_payment(request, payment_id):
    """Process card payment via Flutterwave"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    settings = InsuranceSettings.get_settings()
    
    if payment.status == 'completed':
        messages.info(request, 'This payment has already been completed.')
        return redirect('core:payment_success', payment_id=payment.id)
    
    if payment.status == 'failed':
        messages.warning(request, 'This payment previously failed. Please try again.')
    
    tx_ref = f"VI-{payment.transaction_id}-{uuid.uuid4().hex[:6].upper()}"
    
    if not payment.payment_details:
        payment.payment_details = {}
    payment.payment_details['tx_ref'] = tx_ref
    payment.status = 'pending'
    payment.save()
    
    user = request.user
    customer_email = user.email
    customer_name = user.get_full_name() or user.email
    customer_phone = str(user.phone_number) if user.phone_number else ""
    
    context = {
        'payment': payment,
        'settings': settings,
        'public_key': settings.flutterwave_public_key,
        'tx_ref': tx_ref,
        'customer_email': customer_email,
        'customer_name': customer_name,
        'customer_phone': customer_phone,
        'amount': float(payment.amount),
        'currency': 'NGN',
        'redirect_url': request.build_absolute_uri(reverse('core:payment_callback')),
        'payment_id': payment_id,
    }
    
    return render(request, 'core/customer/process_payment.html', context)


# apps/core/views.py - Updated views

import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)


@login_required
def bank_transfer_instructions(request, payment_id):
    """Display bank transfer instructions"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    settings = InsuranceSettings.get_settings()
    
    # Check if payment is already completed or pending verification
    if payment.status == 'completed':
        messages.info(request, 'This payment has already been completed.')
        return redirect('core:payment_success', payment_id=payment.id)
    
    if payment.status == 'pending_verification':
        messages.info(request, 'Your bank transfer is currently under verification.')
        return redirect('core:payment_status', payment_id=payment.id)
    
    # Update payment method to bank transfer if not already set
    if payment.payment_method != 'bank_transfer':
        payment.payment_method = 'bank_transfer'
        payment.save()
    
    # Use settings from database or fallback to django settings
    bank_details = {
        'bank_name': settings.bank_name or getattr(django_settings, 'BANK_TRANSFER_SETTINGS', {}).get('bank_name', 'Access Bank'),
        'account_name': settings.bank_account_name or getattr(django_settings, 'BANK_TRANSFER_SETTINGS', {}).get('account_name', 'VehicleInsure Ltd'),
        'account_number': settings.bank_account_number or getattr(django_settings, 'BANK_TRANSFER_SETTINGS', {}).get('account_number', '0592787269'),
        'sort_code': settings.bank_sort_code or getattr(django_settings, 'BANK_TRANSFER_SETTINGS', {}).get('sort_code', '044152567'),
        'swift_code': settings.bank_swift_code or getattr(django_settings, 'BANK_TRANSFER_SETTINGS', {}).get('swift_code', ''),
    }
    
    context = {
        'payment': payment,
        'settings': settings,
        'bank_details': bank_details,
    }
    
    return render(request, 'core/customer/bank_transfer.html', context)


@login_required
def confirm_bank_transfer(request, payment_id):
    """Confirm bank transfer made - Submit for admin verification"""
    if request.method != 'POST':
        return redirect('core:bank_transfer_instructions', payment_id=payment_id)
    
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    # Check if payment can be processed
    if payment.status == 'completed':
        messages.info(request, 'This payment has already been completed.')
        return redirect('core:payment_success', payment_id=payment.id)
    
    if payment.status == 'pending_verification':
        messages.info(request, 'Your payment is already under verification.')
        return redirect('core:payment_status', payment_id=payment.id)
    
    if payment.status != 'pending':
        messages.warning(request, 'This payment cannot be processed.')
        return redirect('core:payment_page', payment_id=payment.id)
    
    bank_name = request.POST.get('bank_name', '').strip()
    transfer_reference = request.POST.get('transfer_reference', '').strip()
    transfer_date = request.POST.get('transfer_date', '').strip()
    account_number = request.POST.get('account_number', '').strip()
    account_name = request.POST.get('account_name', '').strip()
    notes = request.POST.get('notes', '').strip()
    
    if not all([bank_name, transfer_reference, transfer_date, account_number, account_name]):
        messages.error(request, 'Please fill in all required fields.')
        return redirect('core:bank_transfer_instructions', payment_id=payment.id)
    
    # Update payment to pending_verification - NOT COMPLETED
    payment.status = 'pending_verification'
    payment.payment_details = {
        'type': 'bank_transfer',
        'bank_name': bank_name,
        'transfer_reference': transfer_reference,
        'transfer_date': transfer_date,
        'account_number': account_number,
        'account_name': account_name,
        'notes': notes,
        'submitted_at': timezone.now().isoformat(),
    }
    payment.save()
    
    # Log activity
    log_user_activity(request.user, 'bank_transfer_submitted', request, {
        'payment_id': str(payment.id),
        'amount': str(payment.amount),
        'transfer_reference': transfer_reference,
    })
    
    # Create notification for user
    Notification.objects.create(
        user=request.user,
        title='Bank Transfer Submitted for Verification',
        message=f'Your bank transfer payment of ₦{payment.amount:,.2f} has been submitted and is awaiting verification. This usually takes 1-24 hours.',
        notification_type='payment_confirmation',
        data={'payment_id': str(payment.id)}
    )
    
    # Notify admins
    admin_users = User.objects.filter(role='admin', is_active=True)
    for admin in admin_users:
        Notification.objects.create(
            user=admin,
            title='Bank Transfer Payment Submitted',
            message=f'{request.user.get_full_name() or request.user.email} has submitted bank transfer payment of ₦{payment.amount:,.2f} for verification.',
            notification_type='payment_confirmation',
            data={'payment_id': str(payment.id), 'user_id': str(request.user.id)}
        )
    
    # Send email to admins
    send_bank_transfer_notification_email(payment, request.user)
    
    # Send confirmation email to customer
    send_bank_transfer_confirmation_email(payment, request.user)
    
    messages.success(request, 'Your payment has been submitted for verification. We will confirm within 24 hours.')
    return redirect('core:payment_status', payment_id=payment.id)


def send_bank_transfer_notification_email(payment, user):
    """Send email notification to admins about bank transfer"""
    try:
        admin_emails = User.objects.filter(role='admin', is_active=True).values_list('email', flat=True)
        
        if not admin_emails:
            logger.warning("No admin emails found for bank transfer notification")
            return
        
        subject = f'[BANK TRANSFER] Payment Verification Needed - {payment.payment_reference}'
        
        context = {
            'payment': payment,
            'user': user,
            'amount': payment.amount,
            'reference': payment.payment_reference,
            'policy_number': payment.policy.policy_number,
            'bank_name': payment.payment_details.get('bank_name', 'N/A'),
            'account_name': payment.payment_details.get('account_name', 'N/A'),
            'account_number': payment.payment_details.get('account_number', 'N/A'),
            'transfer_reference': payment.payment_details.get('transfer_reference', 'N/A'),
            'transfer_date': payment.payment_details.get('transfer_date', 'N/A'),
            'notes': payment.payment_details.get('notes', ''),
            'submitted_at': payment.payment_details.get('submitted_at', 'N/A'),
            'site_name': 'Vehicle Insurance Pro',
            'admin_url': f"/custom_admin/payments/{payment.id}/verify-transfer/",
        }
        
        html_content = render_to_string('core/emails/bank_transfer_notification.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            to=list(admin_emails),
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"Bank transfer notification email sent to {len(admin_emails)} admins")
        
    except Exception as e:
        logger.error(f"Failed to send bank transfer notification email: {str(e)}")


def send_bank_transfer_confirmation_email(payment, user):
    """Send confirmation email to customer after bank transfer submission"""
    try:
        subject = f'Bank Transfer Submitted - {payment.payment_reference}'
        
        context = {
            'user': user,
            'payment': payment,
            'policy': payment.policy,
            'amount': payment.amount,
            'reference': payment.payment_reference,
            'transfer_reference': payment.payment_details.get('transfer_reference', 'N/A'),
            'submitted_at': timezone.now(),
            'site_name': 'Vehicle Insurance Pro',
        }
        
        html_content = render_to_string('core/emails/bank_transfer_confirmation.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"Bank transfer confirmation email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send bank transfer confirmation email: {str(e)}")


# ============================================
# PAYMENT CALLBACK AND VERIFICATION
# ============================================

@csrf_exempt
def payment_callback(request):
    """Handle Flutterwave payment callback"""
    logger.info(f"Payment Callback Received: {request.GET}")
    
    if request.method == 'GET':
        tx_ref = request.GET.get('tx_ref')
        transaction_id = request.GET.get('transaction_id')
        status = request.GET.get('status')
        
        if not tx_ref:
            logger.error("No tx_ref in callback")
            messages.error(request, 'Invalid payment callback.')
            return redirect('core:dashboard')
        
        try:
            parts = tx_ref.split('-')
            if len(parts) >= 2:
                payment_transaction_id = parts[1]
                payment = Payment.objects.get(transaction_id=payment_transaction_id)
            else:
                logger.error(f"Invalid tx_ref format: {tx_ref}")
                messages.error(request, 'Invalid transaction reference.')
                return redirect('core:dashboard')
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for tx_ref: {tx_ref}")
            messages.error(request, 'Payment record not found.')
            return redirect('core:dashboard')
        
        if payment.status == 'completed':
            logger.info(f"Payment {payment.id} already completed")
            messages.info(request, 'This payment has already been completed.')
            return redirect('core:payment_success', payment_id=payment.id)
        
        if status == 'successful' and transaction_id:
            logger.info(f"Verifying transaction: {transaction_id}")
            
            verification_result = verify_flutterwave_transaction(transaction_id, payment)
            
            if verification_result['success']:
                logger.info(f"Payment {payment.id} verified successfully")
                
                # THIS IS WHERE THE MAGIC HAPPENS
                handle_successful_payment(payment, verification_result['data'])
                
                # Increment promo code usage if applicable
                if 'pending_promo' in request.session:
                    try:
                        promo = PromoCode.objects.get(code=request.session['pending_promo'])
                        promo.used_count += 1
                        promo.save()
                    except PromoCode.DoesNotExist:
                        pass
                    del request.session['pending_promo']
                
                messages.success(request, 'Payment successful! Your policy is now active.')
                
                # Redirect based on payment type
                payment_type = payment.payment_details.get('type') if payment.payment_details else None
                if payment_type in ['installment', 'down_payment']:
                    return redirect('core:my_installments')
                else:
                    return redirect('core:payment_success', payment_id=payment.id)
            else:
                logger.warning(f"Payment verification failed: {verification_result.get('message')}")
                payment.status = 'failed'
                payment.failure_reason = verification_result.get('message', 'Payment verification failed')
                payment.save()
                
                messages.error(request, f'Payment verification failed: {payment.failure_reason}')
                return redirect('core:payment_failed', payment_id=payment.id)
        else:
            logger.info(f"Payment not successful. Status: {status}")
            payment.status = 'failed'
            payment.failure_reason = 'Payment was cancelled or failed'
            payment.save()
            
            messages.error(request, 'Payment was not successful. Please try again.')
            return redirect('core:payment_failed', payment_id=payment.id)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)


def verify_flutterwave_transaction(transaction_id, payment):
    """Verify a transaction with Flutterwave API"""
    settings = InsuranceSettings.get_settings()
    
    verify_url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
    
    headers = {
        'Authorization': f'Bearer {settings.flutterwave_secret_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(verify_url, headers=headers, timeout=30)
        data = response.json()
        
        logger.info(f"Flutterwave Verification Response: {data}")
        
        if data.get('status') == 'success':
            tx_data = data.get('data', {})
            
            expected_amount = float(payment.amount)
            actual_amount = tx_data.get('amount', 0)
            
            if abs(actual_amount - expected_amount) > 1:
                logger.warning(f"Amount mismatch: Expected {expected_amount}, got {actual_amount}")
                return {
                    'success': False,
                    'message': f"Amount mismatch. Expected ₦{expected_amount:,.2f}, got ₦{actual_amount:,.2f}"
                }
            
            if tx_data.get('currency') != 'NGN':
                logger.warning(f"Currency mismatch: Expected NGN, got {tx_data.get('currency')}")
                return {
                    'success': False,
                    'message': f"Currency mismatch. Expected NGN, got {tx_data.get('currency')}"
                }
            
            if tx_data.get('status') != 'successful':
                logger.warning(f"Transaction not successful: {tx_data.get('status')}")
                return {
                    'success': False,
                    'message': f"Transaction not successful. Status: {tx_data.get('status')}"
                }
            
            return {
                'success': True,
                'data': tx_data,
                'message': 'Transaction verified successfully'
            }
        else:
            return {
                'success': False,
                'message': data.get('message', 'Transaction verification failed')
            }
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Flutterwave API Error: {str(e)}")
        return {
            'success': False,
            'message': 'Unable to verify payment at this time. Please contact support.'
        }
    except Exception as e:
        logger.error(f"Verification Error: {str(e)}")
        return {
            'success': False,
            'message': 'An error occurred during verification.'
        }


def handle_successful_payment(payment, transaction_data):
    """Handle successful payment - activates policy and sends notifications"""
    logger.info(f"Handling successful payment for payment {payment.id}")
    
    payment.status = 'completed'
    payment.paid_at = timezone.now()
    payment.payment_details = transaction_data
    payment.save()
    
    if payment.payment_details.get('type') == 'installment':
        installment_id = payment.payment_details.get('installment_id')
        if installment_id:
            try:
                installment = Installment.objects.get(id=installment_id)
                installment.status = 'paid'
                installment.paid_date = timezone.now()
                installment.amount_paid = payment.amount
                installment.payment = payment
                installment.save()
                
                plan = installment.installment_plan
                
                if not plan.installments.filter(status='pending').exists():
                    plan.status = 'completed'
                    plan.save()
                    
                    plan.policy.status = 'active'
                    plan.policy.save()
                    
                    try:
                        generate_policy_certificate(plan.policy)
                    except Exception as e:
                        logger.error(f"Certificate generation error: {e}")
                
                next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
                if next_installment:
                    plan.next_due_date = next_installment.due_date
                    plan.save()
                    
            except Installment.DoesNotExist:
                logger.error(f"Installment not found: {installment_id}")
    
    elif payment.payment_details.get('type') == 'down_payment':
        plan_id = payment.payment_details.get('installment_plan_id')
        if plan_id:
            try:
                plan = InstallmentPlan.objects.get(id=plan_id)
                
                first_installment = plan.installments.filter(installment_number=1).first()
                if first_installment:
                    first_installment.status = 'paid'
                    first_installment.paid_date = timezone.now()
                    first_installment.amount_paid = payment.amount
                    first_installment.payment = payment
                    first_installment.save()
                
                plan.policy.status = 'active'
                plan.policy.save()
                
                try:
                    generate_policy_certificate(plan.policy)
                except Exception as e:
                    logger.error(f"Certificate generation error: {e}")
                
                next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
                if next_installment:
                    plan.next_due_date = next_installment.due_date
                    plan.save()
                    
            except InstallmentPlan.DoesNotExist:
                logger.error(f"Installment plan not found: {plan_id}")
    
    else:
        payment.policy.status = 'active'
        payment.policy.save()
        
        try:
            generate_policy_certificate(payment.policy)
        except Exception as e:
            logger.error(f"Certificate generation error: {e}")
    
    send_payment_success_notifications(payment)
    
    log_user_activity(
        payment.user, 
        'payment_completed', 
        None,
        {
            'payment_id': str(payment.id),
            'amount': str(payment.amount),
            'transaction_id': transaction_data.get('id', '')
        }
    )
    
    logger.info(f"Payment {payment.id} successfully processed")


def send_payment_success_notifications(payment):
    """Send payment success notifications to user and staff"""
    try:
        Notification.objects.create(
            user=payment.user,
            title='Payment Successful',
            message=f'Your payment of ₦{payment.amount:,.2f} for policy #{payment.policy.policy_number} was successful.',
            notification_type='payment_confirmation',
            data={
                'payment_id': str(payment.id),
                'policy_id': str(payment.policy.id),
                'amount': str(payment.amount)
            }
        )
        
        send_customer_payment_email(payment)
        send_staff_payment_email(payment)
        
        logger.info(f"Payment notifications sent for payment {payment.id}")
        
    except Exception as e:
        logger.error(f"Error sending payment notifications: {str(e)}")


def send_customer_payment_email(payment):
    """Send payment confirmation email to customer"""
    try:
        subject = f'Payment Confirmation - {payment.policy.policy_number}'
        
        context = {
            'user': payment.user,
            'payment': payment,
            'policy': payment.policy,
            'amount': payment.amount,
            'transaction_id': payment.payment_details.get('id', payment.transaction_id),
            'payment_date': payment.paid_at,
            'site_name': 'Vehicle Insurance Pro',
        }
        
        html_content = render_to_string('core/emails/payment_success_customer.html', context)
        text_content = strip_tags(html_content)
        
        send_mail(
            subject=subject,
            message=text_content,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[payment.user.email],
            html_message=html_content,
            fail_silently=False,
        )
        
        logger.info(f"Customer payment email sent to {payment.user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send customer payment email: {str(e)}")


def send_staff_payment_email(payment):
    """Send payment notification email to staff"""
    try:
        staff_emails = User.objects.filter(
            role__in=['admin', 'support'],
            is_active=True
        ).values_list('email', flat=True)
        
        if not staff_emails:
            return
        
        subject = f'[Payment Received] {payment.user.get_full_name() or payment.user.email} - ₦{payment.amount:,.2f}'
        
        context = {
            'payment': payment,
            'policy': payment.policy,
            'customer': payment.user,
            'amount': payment.amount,
            'transaction_id': payment.payment_details.get('id', payment.transaction_id),
            'payment_date': payment.paid_at,
            'payment_method': payment.get_payment_method_display(),
            'site_name': 'Vehicle Insurance Pro',
        }
        
        html_content = render_to_string('core/emails/payment_success_staff.html', context)
        text_content = strip_tags(html_content)
        
        send_mail(
            subject=subject,
            message=text_content,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(staff_emails),
            html_message=html_content,
            fail_silently=False,
        )
        
        logger.info(f"Staff payment email sent to {len(staff_emails)} recipients")
        
    except Exception as e:
        logger.error(f"Failed to send staff payment email: {str(e)}")


# ============================================
# PAYMENT STATUS PAGES
# ============================================

@login_required
def payment_status(request, payment_id):
    """View payment status page"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'core/customer/payment_status.html', context)


@login_required
def payment_success(request, payment_id):
    """Display payment success page"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    certificate = None
    try:
        certificate = PolicyCertificate.objects.filter(policy=payment.policy).first()
    except:
        pass
    
    context = {
        'payment': payment,
        'policy': payment.policy,
        'certificate': certificate,
    }
    
    return render(request, 'core/customer/payment_success.html', context)


@login_required
def payment_failed(request, payment_id):
    """Display payment failed page"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    context = {
        'payment': payment,
        'policy': payment.policy,
        'failure_reason': payment.failure_reason or 'Payment was not completed',
    }
    
    return render(request, 'core/customer/payment_failed.html', context)


@login_required
def verify_payment(request, payment_id):
    """Manual payment verification endpoint (for AJAX polling)"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    if payment.status == 'completed':
        return JsonResponse({'success': True, 'status': 'completed'})
    elif payment.status == 'failed':
        return JsonResponse({'success': False, 'status': 'failed', 'message': payment.failure_reason})
    elif payment.status == 'pending_verification':
        return JsonResponse({'success': True, 'status': 'pending_verification', 'message': 'Payment under verification'})
    else:
        return JsonResponse({'success': True, 'status': 'pending', 'message': 'Payment pending'})


# ============================================
# INSTALLMENT VIEWS
# ============================================


def setup_installment_payment(request, policy, total_premium, payment_method='card'):
    """
    Setup installment payment plan for a policy
    Supports both manual and automatic recurring payments
    """
    from decimal import Decimal
    
    try:
        frequency = request.POST.get('installment_frequency', 'monthly')
        num_installments = int(request.POST.get('num_installments', 3))
        down_payment_percentage = Decimal(request.POST.get('down_payment_percentage', '30'))
        payment_mode = request.POST.get('payment_mode', 'manual')
        auto_debit = request.POST.get('auto_debit') == 'on'
        
        # Validate inputs
        if num_installments < 2 or num_installments > 12:
            return {'success': False, 'message': 'Number of installments must be between 2 and 12'}
        
        if down_payment_percentage < 20 or down_payment_percentage > 50:
            return {'success': False, 'message': 'Down payment must be between 20% and 50%'}
        
        # Calculate amounts
        down_payment = total_premium * (down_payment_percentage / Decimal('100'))
        financed_amount = total_premium - down_payment
        
        # Apply interest (5% per annum)
        interest_rate = Decimal('5')
        months = 12 if frequency == 'monthly' else 4 if frequency == 'quarterly' else 2
        total_interest = financed_amount * (interest_rate / Decimal('100')) * (Decimal(num_installments) / Decimal(months))
        
        total_payable = financed_amount + total_interest
        installment_amount = total_payable / Decimal(num_installments)
        
        # Create installment plan
        plan = InstallmentPlan.objects.create(
            policy=policy,
            user=request.user,
            total_premium=total_premium,
            down_payment=down_payment,
            financed_amount=financed_amount,
            interest_rate=interest_rate,
            total_interest=total_interest,
            total_payable=total_payable,
            frequency=frequency,
            number_of_installments=num_installments,
            installment_amount=installment_amount,
            payment_mode=payment_mode,
            auto_debit_enabled=auto_debit,
            start_date=timezone.now().date(),
            next_due_date=timezone.now().date() + timezone.timedelta(days=30),
            next_auto_debit_date=timezone.now().date() + timezone.timedelta(days=30) if auto_debit else None,
            status='active'
        )
        
        # Create Flutterwave payment plan if auto-debit is enabled
        if auto_debit:
            plan_result = plan.create_flutterwave_payment_plan()
            if not plan_result['success']:
                # Fallback to manual if plan creation fails
                plan.payment_mode = 'manual'
                plan.auto_debit_enabled = False
                plan.save()
        
        # Create individual installments
        for i in range(num_installments):
            due_date = timezone.now().date() + timezone.timedelta(days=30 * (i + 1))
            
            principal = financed_amount / Decimal(num_installments)
            interest = total_interest / Decimal(num_installments)
            
            Installment.objects.create(
                installment_plan=plan,
                installment_number=i + 1,
                principal_amount=principal,
                interest_amount=interest,
                total_amount=installment_amount,
                due_date=due_date,
                status='pending'
            )
        
        # Create payment for down payment
        if down_payment > 0:
            transaction_id = Payment.generate_unique_transaction_id('TXN-DP')
            payment_reference = Payment.generate_unique_reference('PAY-DP')
            
            down_payment_record = Payment.objects.create(
                policy=policy,
                user=request.user,
                amount=down_payment,
                payment_method=payment_method,
                transaction_id=transaction_id,
                payment_reference=payment_reference,
                status='pending',
                payment_details={
                    'type': 'down_payment', 
                    'installment_plan_id': str(plan.id),
                    'total_installments': num_installments,
                    'installment_frequency': frequency,
                    'payment_mode': payment_mode,
                    'auto_debit': auto_debit
                }
            )
            
            # Get first installment
            first_installment = plan.installments.filter(installment_number=1).first()
            
            # Link payment to first installment
            if first_installment:
                first_installment.payment = down_payment_record
                first_installment.save()
            
            return {
                'success': True,
                'installment_id': first_installment.id,
                'down_payment_id': down_payment_record.id,
                'plan': plan,
                'payment_mode': payment_mode,
                'auto_debit': auto_debit
            }
        
        return {'success': True, 'installment_id': plan.installments.first().id}
        
    except Exception as e:
        import traceback
        logger.error(f"Installment Setup Error: {traceback.format_exc()}")
        return {'success': False, 'message': f'Error setting up installment plan: {str(e)}'}
    
    

# apps/core/views.py - Auto-debit processing

def process_auto_debit(installment):
    """Process automatic debit for an installment using saved card"""
    import requests
    
    plan = installment.installment_plan
    
    if not plan.auto_debit_enabled or not plan.card_token:
        return {'success': False, 'message': 'Auto-debit not configured'}
    
    settings = InsuranceSettings.get_settings()
    
    # Update installment status
    installment.status = 'processing'
    installment.auto_debit_attempted = True
    installment.auto_debit_attempts += 1
    installment.last_auto_debit_attempt = timezone.now()
    installment.save()
    
    # Prepare charge payload
    url = "https://api.flutterwave.com/v3/charges?type=card"
    
    payload = {
        "token": plan.card_token,
        "currency": "NGN",
        "amount": float(installment.total_amount),
        "email": plan.user.email,
        "tx_ref": f"AUTO-INST-{installment.id}-{timezone.now().timestamp()}",
        "fullname": plan.user.get_full_name() or plan.user.email,
        "redirect_url": django_settings.SITE_URL + "/payment/callback/",
        "meta": {
            "installment_id": str(installment.id),
            "plan_id": str(plan.id),
            "installment_number": installment.installment_number
        }
    }
    
    headers = {
        'Authorization': f'Bearer {settings.flutterwave_secret_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
        
        if data.get('status') == 'success' and data.get('data', {}).get('status') == 'successful':
            # Payment successful
            transaction_id = Payment.generate_unique_transaction_id('TXN-AUTO')
            payment_reference = Payment.generate_unique_reference('PAY-AUTO')
            
            payment = Payment.objects.create(
                policy=plan.policy,
                user=plan.user,
                amount=installment.total_amount,
                payment_method='card',
                transaction_id=transaction_id,
                payment_reference=payment_reference,
                status='completed',
                paid_at=timezone.now(),
                payment_details={
                    'type': 'installment',
                    'installment_id': str(installment.id),
                    'installment_number': installment.installment_number,
                    'installment_plan_id': str(plan.id),
                    'auto_debit': True,
                    'flutterwave_response': data.get('data')
                }
            )
            
            # Update installment
            installment.status = 'paid'
            installment.paid_date = timezone.now()
            installment.amount_paid = installment.total_amount
            installment.payment = payment
            installment.save()
            
            # Update plan
            plan.last_auto_debit_date = timezone.now()
            plan.auto_debit_attempts = 0
            plan.save()
            
            # Update next due date
            next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
            if next_installment:
                plan.next_due_date = next_installment.due_date
                plan.next_auto_debit_date = next_installment.due_date
                plan.save()
            
            # Check if all installments paid
            if not plan.installments.filter(status='pending').exists():
                plan.status = 'completed'
                plan.save()
                
                if plan.policy.status != 'active':
                    plan.policy.status = 'active'
                    plan.policy.save()
                    generate_policy_certificate(plan.policy)
            
            # Send notification
            Notification.objects.create(
                user=plan.user,
                title='Auto-Debit Successful',
                message=f'Your auto-debit payment of ₦{installment.total_amount:,.2f} for installment #{installment.installment_number} was successful.',
                notification_type='payment_confirmation',
                data={'installment_id': str(installment.id)}
            )
            
            return {'success': True, 'message': 'Auto-debit successful'}
            
        else:
            # Payment failed
            installment.status = 'failed' if installment.auto_debit_attempts >= plan.max_auto_debit_attempts else 'pending'
            installment.auto_debit_error = data.get('message', 'Payment failed')
            installment.save()
            
            plan.auto_debit_attempts += 1
            
            # Notify user of failure
            Notification.objects.create(
                user=plan.user,
                title='Auto-Debit Failed',
                message=f'Your auto-debit payment of ₦{installment.total_amount:,.2f} for installment #{installment.installment_number} failed. Please update your payment method or pay manually.',
                notification_type='payment_confirmation',
                data={'installment_id': str(installment.id)}
            )
            
            return {'success': False, 'message': data.get('message', 'Payment failed')}
            
    except Exception as e:
        logger.error(f"Auto-debit error: {str(e)}")
        installment.status = 'pending'
        installment.auto_debit_error = str(e)
        installment.save()
        return {'success': False, 'message': str(e)}


def run_auto_debit_job():
    """Run auto-debit for all due installments - Call this via cron/scheduler"""
    today = timezone.now().date()
    
    # Get pending installments due today or earlier
    due_installments = Installment.objects.filter(
        status='pending',
        due_date__lte=today,
        installment_plan__auto_debit_enabled=True,
        installment_plan__status='active'
    ).select_related('installment_plan', 'installment_plan__user')
    
    results = []
    for installment in due_installments:
        # Skip if max attempts reached
        if installment.auto_debit_attempts >= installment.installment_plan.max_auto_debit_attempts:
            continue
        
        result = process_auto_debit(installment)
        results.append({
            'installment_id': str(installment.id),
            'success': result.get('success', False),
            'message': result.get('message', '')
        })
    
    return results



@login_required
def pay_installment(request, installment_id):
    """Pay an individual installment"""
    installment = get_object_or_404(
        Installment.objects.select_related('installment_plan', 'installment_plan__policy'), 
        id=installment_id, 
        installment_plan__user=request.user
    )
    
    plan = installment.installment_plan
    policy = plan.policy
    
    # Check if already paid
    if installment.status == 'paid':
        messages.info(request, 'This installment has already been paid.')
        return redirect('core:my_installments')
    
    # Check if policy is still active
    if policy.status not in ['active', 'draft']:
        messages.warning(request, 'This policy is no longer active.')
        return redirect('core:my_installments')
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'card')
        
        try:
            # Use model method for unique references
            transaction_id = Payment.generate_unique_transaction_id('TXN-INST')
            payment_reference = Payment.generate_unique_reference('PAY-INST')
            
            payment = Payment.objects.create(
                policy=policy,
                user=request.user,
                amount=installment.total_amount,
                payment_method=payment_method,
                transaction_id=transaction_id,
                payment_reference=payment_reference,
                status='pending',
                payment_details={
                    'type': 'installment',
                    'installment_id': str(installment.id),
                    'installment_number': installment.installment_number,
                    'installment_plan_id': str(plan.id),
                    'total_installments': plan.number_of_installments
                }
            )
            
            # Link payment to installment
            installment.payment = payment
            installment.save()
            
            # Log activity
            log_user_activity(request.user, 'initiate_installment_payment', request, {
                'installment_id': str(installment.id),
                'payment_id': str(payment.id),
                'amount': str(installment.total_amount),
                'installment_number': installment.installment_number
            })
            
            messages.info(request, f'Please complete your payment of ₦{installment.total_amount:,.2f} to continue.')
            
            # Redirect to payment processing
            if payment_method == 'card':
                return redirect('core:process_card_payment', payment_id=payment.id)
            elif payment_method == 'bank_transfer':
                return redirect('core:bank_transfer_instructions', payment_id=payment.id)
            else:
                return redirect('core:payment_page', payment_id=payment.id)
                
        except Exception as e:
            logger.error(f"Error creating installment payment: {str(e)}")
            messages.error(request, 'An error occurred. Please try again.')
            return redirect('core:pay_installment', installment_id=installment.id)
    
    context = {
        'installment': installment,
        'plan': plan,
        'policy': policy,
        'next_due_date': plan.next_due_date,
        'remaining_installments': plan.installments.filter(status='pending').count(),
        'total_remaining': plan.get_remaining_amount(),
    }
    
    return render(request, 'core/customer/pay_installment.html', context)



def handle_successful_payment(payment, transaction_data):
    """
    Handle successful payment - activates policy and sends notifications
    THIS IS ONLY CALLED AFTER SUCCESSFUL VERIFICATION
    """
    logger.info(f"Handling successful payment for payment {payment.id}")
    
    # Update payment record
    payment.status = 'completed'
    payment.paid_at = timezone.now()
    if not payment.payment_details:
        payment.payment_details = {}
    payment.payment_details.update(transaction_data)
    payment.save()
    
    policy = payment.policy
    
    # Check payment type from payment_details
    payment_type = payment.payment_details.get('type') if payment.payment_details else None
    
    if payment_type == 'installment':
        # Handle regular installment payment
        installment_id = payment.payment_details.get('installment_id')
        if installment_id:
            try:
                installment = Installment.objects.get(id=installment_id)
                installment.status = 'paid'
                installment.paid_date = timezone.now()
                installment.amount_paid = payment.amount
                installment.payment = payment
                installment.save()
                
                plan = installment.installment_plan
                
                logger.info(f"Installment {installment.installment_number} paid for plan {plan.plan_number}")
                
                # Check if all installments are paid
                pending_count = plan.installments.filter(status='pending').count()
                if pending_count == 0:
                    plan.status = 'completed'
                    plan.save()
                    
                    # Activate policy if all installments paid
                    if policy.status != 'active':
                        policy.status = 'active'
                        policy.save()
                        logger.info(f"Policy {policy.policy_number} activated after all installments paid")
                    
                    # Generate certificate
                    try:
                        generate_policy_certificate(policy)
                    except Exception as e:
                        logger.error(f"Certificate generation error: {e}")
                
                # Update next due date
                next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
                if next_installment:
                    plan.next_due_date = next_installment.due_date
                    plan.save()
                    
            except Installment.DoesNotExist:
                logger.error(f"Installment not found: {installment_id}")
    
    elif payment_type == 'down_payment':
        # Handle down payment for installment plan
        plan_id = payment.payment_details.get('installment_plan_id')
        if plan_id:
            try:
                plan = InstallmentPlan.objects.get(id=plan_id)
                
                # Mark first installment as paid
                first_installment = plan.installments.filter(installment_number=1).first()
                if first_installment:
                    first_installment.status = 'paid'
                    first_installment.paid_date = timezone.now()
                    first_installment.amount_paid = payment.amount
                    first_installment.payment = payment
                    first_installment.save()
                    logger.info(f"First installment marked as paid for down payment")
                
                # Activate policy after down payment
                if policy.status != 'active':
                    policy.status = 'active'
                    policy.save()
                    logger.info(f"Policy {policy.policy_number} activated after down payment")
                
                # Generate certificate after down payment
                try:
                    generate_policy_certificate(policy)
                except Exception as e:
                    logger.error(f"Certificate generation error: {e}")
                
                # Update next due date for remaining installments
                next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
                if next_installment:
                    plan.next_due_date = next_installment.due_date
                    plan.save()
                    
            except InstallmentPlan.DoesNotExist:
                logger.error(f"Installment plan not found: {plan_id}")
    
    else:
        # Full payment - activate policy immediately
        if policy.status != 'active':
            policy.status = 'active'
            policy.save()
            logger.info(f"Policy {policy.policy_number} activated after full payment")
        
        # Generate certificate
        try:
            generate_policy_certificate(policy)
        except Exception as e:
            logger.error(f"Certificate generation error: {e}")
    
    # Send notifications
    send_payment_success_notifications(payment)
    
    # Log activity
    log_user_activity(
        payment.user, 
        'payment_completed', 
        None,
        {
            'payment_id': str(payment.id),
            'amount': str(payment.amount),
            'payment_type': payment_type or 'full',
            'transaction_id': transaction_data.get('id', '')
        }
    )
    
    logger.info(f"Payment {payment.id} successfully processed")
    
    
# apps/core/views.py - Manage auto-debit settings

@login_required
def manage_auto_debit(request, plan_id):
    """Enable/disable auto-debit for an installment plan"""
    plan = get_object_or_404(InstallmentPlan, id=plan_id, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'enable':
            # Create Flutterwave payment plan
            result = plan.create_flutterwave_payment_plan()
            if result['success']:
                plan.auto_debit_enabled = True
                plan.payment_mode = 'auto'
                plan.save()
                messages.success(request, 'Auto-debit enabled successfully!')
            else:
                messages.error(request, f'Failed to enable auto-debit: {result["message"]}')
                
        elif action == 'disable':
            plan.auto_debit_enabled = False
            plan.payment_mode = 'manual'
            plan.save()
            messages.success(request, 'Auto-debit disabled. You will need to pay manually.')
            
        elif action == 'update_card':
            # Redirect to card update page
            return redirect('core:update_payment_card', plan_id=plan.id)
        
        return redirect('core:my_installment_detail', plan_id=plan.id)
    
    context = {
        'plan': plan,
    }
    
    return render(request, 'core/customer/manage_auto_debit.html', context)


@login_required
def update_payment_card(request, plan_id):
    """Update card for auto-debit"""
    plan = get_object_or_404(InstallmentPlan, id=plan_id, user=request.user)
    settings = InsuranceSettings.get_settings()
    
    context = {
        'plan': plan,
        'settings': settings,
        'public_key': settings.flutterwave_public_key,
    }
    
    return render(request, 'core/customer/update_payment_card.html', context)




@login_required
@require_http_methods(["POST"])
def save_card_token(request):
    """Save card token after successful verification"""
    import json
    import requests
    
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        plan_id = data.get('plan_id')
        
        plan = get_object_or_404(InstallmentPlan, id=plan_id, user=request.user)
        settings = InsuranceSettings.get_settings()
        
        # Verify transaction with Flutterwave
        verify_url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
        headers = {'Authorization': f'Bearer {settings.flutterwave_secret_key}'}
        
        response = requests.get(verify_url, headers=headers)
        result = response.json()
        
        if result.get('status') == 'success':
            tx_data = result.get('data', {})
            card_data = tx_data.get('card', {})
            card_token = card_data.get('token') or tx_data.get('card_token')
            
            if card_token:
                plan.card_token = card_token
                plan.save()
                return JsonResponse({'success': True, 'message': 'Card saved successfully'})
        
        return JsonResponse({'success': False, 'message': 'Could not retrieve card token'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def my_installments(request):
    """View user's installment plans"""
    from django.db.models import Sum  # Local import as backup
    
    plans = InstallmentPlan.objects.filter(user=request.user).prefetch_related(
        'installments'
    ).order_by('-created_at')
    
    # Get all installments for this user
    installments = Installment.objects.filter(
        installment_plan__user=request.user
    ).select_related('installment_plan', 'installment_plan__policy', 'payment').order_by('due_date')
    
    # Upcoming/pending installments (not overdue)
    pending_installments = installments.filter(
        status='pending',
        due_date__gte=timezone.now().date()
    ).order_by('due_date')
    
    # Overdue installments
    overdue_installments = installments.filter(
        status='pending',
        due_date__lt=timezone.now().date()
    )
    
    # Paid installments
    paid_installments = installments.filter(status='paid').order_by('-paid_date')
    
    # Calculate totals - using .aggregate() with Sum
    total_pending = pending_installments.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_overdue = overdue_installments.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_paid = paid_installments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
    
    context = {
        'plans': plans,
        'pending_installments': pending_installments,
        'overdue_installments': overdue_installments,
        'paid_installments': paid_installments,
        'total_pending': total_pending,
        'total_overdue': total_overdue,
        'total_paid': total_paid,
        'today': timezone.now().date(),
    }
    
    return render(request, 'core/customer/my_installments.html', context)


@login_required
def installment_plan_detail(request, plan_id):
    """View installment plan details"""
    plan = get_object_or_404(InstallmentPlan, id=plan_id, user=request.user)
    installments = plan.installments.all().select_related('payment').order_by('installment_number')
    
    # Calculate progress
    paid_count = installments.filter(status='paid').count()
    total_count = installments.count()
    progress_percentage = (paid_count / total_count * 100) if total_count > 0 else 0
    
    context = {
        'plan': plan,
        'installments': installments,
        'policy': plan.policy,
        'paid_count': paid_count,
        'total_count': total_count,
        'progress_percentage': progress_percentage,
        'remaining_amount': plan.get_remaining_amount(),
        'paid_amount': plan.get_paid_amount(),
        'today': timezone.now().date(),  # ADD THIS LINE
    }
    
    return render(request, 'core/customer/installment_plan_detail.html', context)



# ============================================
# POLICY VIEWS
# ============================================
# apps/core/views.py - Complete updated my_policies and policy_detail views

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from decimal import Decimal
from datetime import timedelta

from .models import InsurancePolicy, Payment, Claim, DebitCreditNote, PolicyCertificate


@login_required
def my_policies(request):
    """View user's policies - Show both draft and active"""
    policies_list = request.user.policies.all().select_related(
        'vehicle', 'certificate'
    ).prefetch_related(
        'payments',
        'debit_credit_notes'
    ).order_by('-created_at')
    
    active_policies = policies_list.filter(status='active')
    active_count = active_policies.count()
    total_premium = active_policies.aggregate(Sum('premium_amount'))['premium_amount__sum'] or Decimal('0')
    
    expiring_soon = active_policies.filter(
        end_date__lte=timezone.now().date() + timedelta(days=30),
        end_date__gte=timezone.now().date()
    ).count()
    
    draft_policies = policies_list.filter(status='draft')
    draft_count = draft_policies.count()
    
    # Calculate total outstanding balance across all policies
    total_outstanding = Decimal('0')
    for policy in policies_list:
        if policy.status in ['active', 'pending']:
            total_outstanding += policy.get_outstanding_balance()
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        policies_list = policies_list.filter(status=status_filter)
    
    paginator = Paginator(policies_list, 10)
    page = request.GET.get('page')
    policies = paginator.get_page(page)
    
    context = {
        'policies': policies,
        'active_count': active_count,
        'draft_count': draft_count,
        'total_premium': total_premium,
        'total_outstanding': total_outstanding,
        'expiring_soon': expiring_soon,
        'status_filter': status_filter,
    }
    
    return render(request, 'core/customer/my_policies.html', context)


@login_required
def policy_detail(request, policy_id):
    """View policy details including debit/credit notes and balance"""
    from django.db.models import Sum, Q
    from decimal import Decimal
    
    policy = get_object_or_404(
        InsurancePolicy.objects.select_related('vehicle', 'certificate'), 
        id=policy_id, 
        user=request.user
    )
    
    # Get payments (exclude credit note payments from regular payments display)
    payments = policy.payments.all().order_by('-created_at')
    
    # Get claims
    claims = policy.claims.all().order_by('-created_at')
    
    # Get debit/credit notes
    debit_credit_notes = DebitCreditNote.objects.filter(
        policy=policy
    ).order_by('-created_at')
    
    # Calculate totals for financial summary
    # Regular payments (completed, positive amounts)
    total_paid = payments.filter(
        status='completed', 
        amount__gt=0,
        payment_method__in=['card', 'bank_transfer', 'cash', 'mobile_wallet']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Credit note payments (completed, negative amounts)
    total_credits_applied = payments.filter(
        status='completed', 
        amount__lt=0,
        payment_method='credit_note'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_credits_applied = abs(total_credits_applied)
    
    # Debit notes (paid/issued)
    total_debit_notes = debit_credit_notes.filter(
        note_type='debit',
        status__in=['paid', 'issued']
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    
    # Credit notes (paid/issued)
    total_credit_notes = debit_credit_notes.filter(
        note_type='credit',
        status__in=['paid', 'issued']
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    
    # Calculate outstanding balance
    base_premium = policy.premium_amount
    outstanding_balance = (
        base_premium + 
        total_debit_notes - 
        total_credit_notes - 
        total_paid + 
        total_credits_applied
    )
    
    # Determine payment status
    if outstanding_balance <= 0:
        payment_status = 'paid'
    elif outstanding_balance >= base_premium:
        payment_status = 'unpaid'
    else:
        payment_status = 'partial'
    
    # Pending payments
    pending_payments = payments.filter(status__in=['pending', 'pending_verification'])
    pending_amount = pending_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    context = {
        'policy': policy,
        'payments': payments,
        'claims': claims,
        'debit_credit_notes': debit_credit_notes,
        'total_paid': total_paid,
        'total_debit_notes': total_debit_notes,
        'total_credit_notes': total_credit_notes,
        'total_credits_applied': total_credits_applied,
        'outstanding_balance': outstanding_balance,
        'payment_status': payment_status,
        'pending_payments': pending_payments,
        'pending_amount': pending_amount,
    }
    
    return render(request, 'core/customer/policy_detail.html', context)




def regenerate_certificate(policy, generated_by=None):
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
        return generate_policy_certificate(policy, generated_by)
        
    except Exception as e:
        import traceback
        print(f"Error in regenerate_certificate: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to regenerate certificate: {str(e)}'
        }


from .Utils.utils import generate_policy_certificate, regenerate_certificate
from apps.core.models import PolicyCertificate, PublicDocument

@login_required
def view_certificate(request, certificate_id):
    """View certificate details"""
    certificate = get_object_or_404(PolicyCertificate, id=certificate_id)
    
    # Check permission
    if certificate.policy.user != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this certificate.')
        return redirect('core:dashboard')
    
    return render(request, 'core/customer/certificate_detail.html', {
        'certificate': certificate,
        'policy': certificate.policy,
    })


@login_required
def download_certificate(request, certificate_id):
    """Download certificate PDF"""
    certificate = get_object_or_404(PolicyCertificate, id=certificate_id)
    
    # Check permission
    if certificate.policy.user != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to download this certificate.')
        return redirect('core:dashboard')
    
    if certificate.certificate_file:
        response = HttpResponse(certificate.certificate_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="certificate_{certificate.policy.policy_number}.pdf"'
        
        # Log download
        DocumentAccessLog.objects.create(
            document=PublicDocument.objects.filter(policy=certificate.policy, document_type='certificate').first(),
            user=request.user,
            action='download',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        return response
    
    messages.error(request, 'Certificate file not found.')
    return redirect('core:my_policies')


@login_required
def my_certificates(request):
    """View all user certificates"""
    certificates = PolicyCertificate.objects.filter(
        policy__user=request.user,
        status='generated'
    ).select_related('policy').order_by('-issue_date')
    
    # Calculate statistics
    total_certificates = certificates.count()
    active_certificates = certificates.filter(policy__status='active').count()
    expired_certificates = certificates.filter(policy__end_date__lt=timezone.now().date()).count()
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        certificates = certificates.filter(policy__status='active')
    elif status_filter == 'expired':
        certificates = certificates.filter(policy__end_date__lt=timezone.now().date())
    
    paginator = Paginator(certificates, 10)
    page = request.GET.get('page')
    certificates_page = paginator.get_page(page)
    
    context = {
        'certificates': certificates_page,
        'total_certificates': total_certificates,
        'active_certificates': active_certificates,
        'expired_certificates': expired_certificates,
        'status_filter': status_filter,
    }
    
    return render(request, 'core/customer/my_certificates.html', context)


# apps/core/views.py

def verify_certificate_public(request, certificate_number):
    """Public certificate verification page - no login required"""
    from apps.core.models import PolicyCertificate
    from django.utils import timezone
    import hashlib
    
    try:
        certificate = PolicyCertificate.objects.select_related(
            'policy', 
            'policy__user',
            'policy__vehicle'
        ).get(
            certificate_number=certificate_number,
            status='generated'
        )
        policy = certificate.policy
        
        # Check if certificate is valid
        is_valid = policy.status == 'active' and policy.end_date >= timezone.now().date()
        
        # Get verification hash from request
        hash_param = request.GET.get('hash', '')
        
        # Verify hash if provided
        verification_data = f"{certificate_number}|{policy.policy_number}|{policy.user.email}"
        expected_hash = hashlib.sha256(verification_data.encode()).hexdigest()[:16]
        
        is_authentic = (hash_param == expected_hash) if hash_param else True
        
        context = {
            'certificate': certificate,
            'policy': policy,
            'is_valid': is_valid,
            'is_authentic': is_authentic,
            'verification_date': timezone.now(),
            # Don't pass user directly - access through policy.user in template
        }
        
        return render(request, 'core/public/verify_certificate.html', context)
        
    except PolicyCertificate.DoesNotExist:
        messages.error(request, 'Certificate not found or has been revoked.')
        return render(request, 'core/public/verify_certificate.html', {
            'error': 'Certificate not found',
            'certificate_number': certificate_number
        })
    
    

def verify_certificate_form(request):
    """Form to enter certificate number for verification"""
    if request.method == 'POST':
        certificate_number = request.POST.get('certificate_number', '').strip()
        if certificate_number:
            return redirect('core:verify_certificate_public', certificate_number=certificate_number)
        messages.error(request, 'Please enter a certificate number')
    return render(request, 'core/public/verify_certificate_form.html')



# ============================================
# CUSTOMER RENEWAL VIEWS
# ============================================

@login_required
def renew_policy(request, policy_id):
    """Renew an expiring policy - Main renewal page"""
    from decimal import Decimal
    
    policy = get_object_or_404(InsurancePolicy, id=policy_id, user=request.user)
    
    # Check if policy can be renewed (within 60 days of expiry or already expired)
    days_to_expiry = (policy.end_date - timezone.now().date()).days
    if days_to_expiry > 60:
        messages.error(request, 'Policy can only be renewed within 60 days of expiry.')
        return redirect('core:policy_detail', policy_id=policy.id)
    
    # Get or create renewal record
    renewal, created = PolicyRenewal.objects.get_or_create(
        original_policy=policy,
        defaults={
            'user': request.user,
            'original_premium': policy.premium_amount,
            'renewal_premium': policy.premium_amount,
            'renewal_date': policy.end_date - timezone.timedelta(days=30),
            'expiry_date': policy.end_date,
            'new_start_date': policy.end_date + timezone.timedelta(days=1),
            'new_end_date': policy.end_date + timezone.timedelta(days=365),
        }
    )
    
    # Calculate renewal premium with NCB
    renewal.calculate_renewal_premium()
    renewal.save()
    
    # Calculate age loading for display
    age_loading = Decimal('0')
    if policy.vehicle and policy.vehicle.vehicle_age > 5:
        age_loading = policy.premium_amount * Decimal('0.1')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accept_renewal':
            renewal.status = 'accepted'
            renewal.save()
            
            # Create new policy
            new_policy = InsurancePolicy.objects.create(
                user=request.user,
                vehicle=policy.vehicle,
                policy_type=policy.policy_type,
                coverage_amount=policy.coverage_amount,
                premium_amount=renewal.renewal_premium,
                deductible=policy.deductible,
                start_date=renewal.new_start_date,
                end_date=renewal.new_end_date,
                additional_benefits=policy.additional_benefits,
                custom_coverage=policy.custom_coverage,
                terms_accepted=True,
                status='pending'
            )
            
            # Generate policy document
            try:
                from .Utils.utils import generate_policy_document
                policy_doc = generate_policy_document(new_policy)
                new_policy.policy_document = policy_doc
                new_policy.save()
            except Exception as e:
                print(f"Error generating policy document: {e}")
            
            # Create payment for renewal
            payment = Payment.objects.create(
                policy=new_policy,
                user=request.user,
                amount=renewal.renewal_premium,
                payment_method='card',
                status='pending'
            )
            
            renewal.renewed_policy = new_policy
            renewal.status = 'renewed'
            renewal.save()
            
            # Update NCB
            ncb = NoClaimBonus.objects.filter(user=request.user, vehicle=policy.vehicle).first()
            if ncb:
                ncb.increment_year()
            
            messages.success(request, f'Policy renewed successfully! New policy #{new_policy.policy_number} created.')
            return redirect('core:payment_page', payment_id=payment.id)
    
    context = {
        'policy': policy,
        'renewal': renewal,
        'ncb': NoClaimBonus.objects.filter(user=request.user, vehicle=policy.vehicle).first(),
        'age_loading': age_loading,
    }
    
    return render(request, 'core/customer/renew_policy.html', context)


@login_required
def accept_renewal(request, renewal_id):
    """Accept renewal quote and proceed to payment"""
    renewal = get_object_or_404(PolicyRenewal, id=renewal_id, user=request.user)
    
    if request.method == 'POST':
        renewal.status = 'accepted'
        renewal.save()
        
        # Create new policy
        new_policy = InsurancePolicy.objects.create(
            user=request.user,
            vehicle=renewal.original_policy.vehicle,
            policy_type=renewal.original_policy.policy_type,
            coverage_amount=renewal.original_policy.coverage_amount,
            premium_amount=renewal.renewal_premium,
            start_date=renewal.new_start_date,
            end_date=renewal.new_end_date,
            status='pending'
        )
        
        renewal.renewed_policy = new_policy
        renewal.status = 'renewed'
        renewal.save()
        
        # Create payment
        payment = Payment.objects.create(
            policy=new_policy,
            user=request.user,
            amount=renewal.renewal_premium,
            status='pending'
        )
        
        return redirect('core:payment_page', payment_id=payment.id)
    
    return render(request, 'core/accept_renewal.html', {'renewal': renewal})




@login_required
def request_reinsurance(request, policy_id):
    """Request reinsurance for a policy"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id, user=request.user)
    
    # Check if policy can be reinsured (active or cancelled)
    if not policy.can_be_reinsured():
        messages.error(request, 'This policy cannot be reinsured.')
        return redirect('core:policy_detail', policy_id=policy.id)
    
    # Get active reinsurance treaties
    active_treaties = ReinsuranceTreaty.objects.filter(
        status='active',
        effective_date__lte=timezone.now().date(),
        expiry_date__gte=timezone.now().date()
    )
    
    if request.method == 'POST':
        treaty_id = request.POST.get('treaty_id')
        treaty = get_object_or_404(ReinsuranceTreaty, id=treaty_id, status='active')
        
        # Calculate reinsurance
        placement = PolicyReinsurance.objects.create(
            policy=policy,
            treaty=treaty,
            sum_insured=policy.coverage_amount,
            placement_date=timezone.now().date()
        )
        placement.calculate_cession()
        
        # Create debit note for reinsurance premium if applicable
        if placement.ceded_premium > 0:
            debit_note = DebitCreditNote.objects.create(
                policy=policy,
                user=request.user,
                note_type='debit',
                base_amount=placement.ceded_premium,
                total_amount=placement.ceded_premium,
                reason='additional_coverage',
                description=f'Reinsurance placement with {treaty.reinsurer_name}',
                status='issued',
                created_by=request.user
            )
            debit_note.apply_to_policy()
        
        # If policy was cancelled, reactivate it after reinsurance
        if policy.status == 'cancelled':
            policy.status = 'active'
            policy.save()
            messages.success(request, f'Policy reactivated and reinsured with {treaty.reinsurer_name}!')
        else:
            messages.success(request, f'Reinsurance placed successfully with {treaty.reinsurer_name}!')
        
        return redirect('core:policy_detail', policy_id=policy.id)
    
    context = {
        'policy': policy,
        'active_treaties': active_treaties,
    }
    
    return render(request, 'core/customer/request_reinsurance.html', context)

@login_required
def file_claim(request, policy_id=None):
    """File a claim"""
    if request.method == 'POST':
        form = ClaimForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                policy = form.cleaned_data['policy']
                vehicle = form.cleaned_data.get('vehicle')
                
                # Double check policy belongs to user and is active
                if policy.user != request.user:
                    messages.error(request, 'Invalid policy selected.')
                    return redirect('core:file_claim')
                
                if policy.status != 'active':
                    messages.error(request, 'You can only file claims against active policies.')
                    return redirect('core:file_claim')
                
                claim = form.save(commit=False)
                claim.user = request.user
                claim.status = 'pending'
                
                # Use policy vehicle if not explicitly selected
                if not claim.vehicle and policy.vehicle:
                    claim.vehicle = policy.vehicle
                
                # Initialize empty lists for files
                claim.documents = []
                claim.photos = []
                
                # Save claim first to get claim_number
                claim.save()
                
                # Handle file uploads
                uploaded_files = request.FILES.getlist('documents')
                uploaded_photos = request.FILES.getlist('photos')
                
                for file in uploaded_files:
                    doc = Document.objects.create(
                        user=request.user,
                        document_type='claim',
                        document_file=file,
                        name=f"Claim Document - {claim.claim_number}",
                        is_verified=False
                    )
                    claim.documents.append({
                        'id': str(doc.id),
                        'name': file.name,
                        'url': doc.document_file.url
                    })
                
                for photo in uploaded_photos:
                    if photo.content_type.startswith('image/'):
                        doc = Document.objects.create(
                            user=request.user,
                            document_type='claim',
                            document_file=photo,
                            name=f"Claim Photo - {claim.claim_number}",
                            is_verified=False
                        )
                        claim.photos.append({
                            'id': str(doc.id),
                            'name': photo.name,
                            'url': doc.document_file.url
                        })
                
                claim.save()
                
                # Log activity
                log_user_activity(request.user, 'file_claim', request, {
                    'claim_id': str(claim.id),
                    'claim_number': claim.claim_number,
                    'amount': str(claim.claimed_amount),
                    'vehicle': str(claim.vehicle.id) if claim.vehicle else None
                })
                
                # Send notification to user
                Notification.objects.create(
                    user=request.user,
                    title='Claim Filed Successfully',
                    message=f'Your claim #{claim.claim_number} for ₦{claim.claimed_amount:,.2f} has been filed successfully. We will review it shortly.',
                    notification_type='claim_update',
                    data={'claim_id': str(claim.id), 'claim_number': claim.claim_number}
                )
                
                # Notify admins and claims adjusters
                staff_users = User.objects.filter(role__in=['admin', 'claims_adjuster'], is_active=True)
                for staff in staff_users:
                    Notification.objects.create(
                        user=staff,
                        title='New Claim Filed',
                        message=f'New claim #{claim.claim_number} filed by {request.user.get_full_name()} for ₦{claim.claimed_amount:,.2f}',
                        notification_type='claim_update',
                        data={'claim_id': str(claim.id)}
                    )
                
                messages.success(request, f'Claim #{claim.claim_number} filed successfully! You will be notified of updates.')
                return redirect('core:claim_detail', claim_id=claim.id)
                
            except Exception as e:
                import traceback
                print(f"Claim Error: {traceback.format_exc()}")
                messages.error(request, f'Error filing claim: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        initial_data = {}
        if policy_id:
            try:
                policy = InsurancePolicy.objects.get(id=policy_id, user=request.user, status='active')
                initial_data = {'policy': policy, 'vehicle': policy.vehicle}
            except InsurancePolicy.DoesNotExist:
                messages.warning(request, 'Invalid or inactive policy selected.')
        
        form = ClaimForm(initial=initial_data, user=request.user)
    
    policies = request.user.policies.filter(status='active').select_related('vehicle')
    
    if not policies.exists():
        messages.warning(request, 'You need an active policy to file a claim.')
        return redirect('core:my_policies')
    
    return render(request, 'core/customer/file_claim.html', {
        'form': form,
        'policies': policies,
        'selected_policy_id': policy_id
    })
    
    
    

@login_required
def my_claims(request):
    """View user's claims"""
    claims_list = request.user.claims.select_related('policy', 'policy__vehicle').all().order_by('-created_at')
    
    # Calculate statistics
    total_claims = claims_list.count()
    pending_claims = claims_list.filter(status='pending').count()
    approved_claims = claims_list.filter(status='approved').count()
    settled_claims = claims_list.filter(status='settled').count()
    total_claimed = claims_list.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
    total_approved = claims_list.filter(status__in=['approved', 'settled']).aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0
    
    # Filter by status
    status = request.GET.get('status')
    status_filter = status
    if status:
        claims_list = claims_list.filter(status=status)
    
    paginator = Paginator(claims_list, 10)
    page = request.GET.get('page')
    claims = paginator.get_page(page)
    
    context = {
        'claims': claims,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'approved_claims': approved_claims,
        'settled_claims': settled_claims,
        'total_claimed': total_claimed,
        'total_approved': total_approved,
        'status_filter': status_filter,
    }
    
    return render(request, 'core/customer/my_claims.html', context)




@login_required
def claim_detail(request, claim_id):
    """View claim details"""
    claim = get_object_or_404(
        Claim.objects.select_related('user', 'policy', 'policy__vehicle', 'vehicle', 'approved_by'), 
        id=claim_id, 
        user=request.user
    )
    
    # Get vehicle information
    vehicle_info = claim.get_vehicle_info()
    
    # Get uploaded documents and photos
    documents = []
    photos = []
    
    if claim.documents:
        for doc in claim.documents:
            if isinstance(doc, dict):
                documents.append(doc)
    
    if claim.photos:
        for photo in claim.photos:
            if isinstance(photo, dict):
                photos.append(photo)
    
    has_admin_response = bool(claim.surveyor_notes or claim.rejection_reason or claim.status in ['approved', 'rejected', 'settled'])
    
    context = {
        'claim': claim,
        'documents': documents,
        'photos': photos,
        'has_admin_response': has_admin_response,
        'vehicle_info': vehicle_info,
    }
    
    return render(request, 'core/customer/claim_detail.html', context)






# apps/core/views.py - Add these customer views at the end

# ============================================
# CUSTOMER ENDORSEMENT VIEWS
# ============================================

@login_required
def request_endorsement(request, policy_id):
    """Request policy endorsement"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id, user=request.user)
    
    if request.method == 'POST':
        form = PolicyEndorsementForm(request.POST, user=request.user)
        if form.is_valid():
            endorsement = form.save(commit=False)
            endorsement.policy = policy
            endorsement.requested_by = request.user
            endorsement.save()
            
            messages.success(request, 'Endorsement request submitted successfully!')
            return redirect('core:endorsement_detail', endorsement_id=endorsement.id)
    else:
        form = PolicyEndorsementForm(user=request.user, initial={'policy': policy})
    
    return render(request, 'core/request_endorsement.html', {
        'form': form,
        'policy': policy
    })


@login_required
def endorsement_detail(request, endorsement_id):
    """View endorsement details"""
    endorsement = get_object_or_404(PolicyEndorsement, id=endorsement_id, requested_by=request.user)
    
    return render(request, 'core/endorsement_detail.html', {
        'endorsement': endorsement
    })



# ============================================
# CUSTOMER INSTALLMENT VIEWS
# ============================================

@login_required
def setup_installment_plan(request, payment_id):
    """Setup installment plan for premium payment"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    if request.method == 'POST':
        form = InstallmentPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.policy = payment.policy
            plan.user = request.user
            plan.total_premium = payment.amount
            plan.start_date = timezone.now().date()
            
            # Calculate next due date
            if plan.frequency == 'monthly':
                plan.next_due_date = plan.start_date + timezone.timedelta(days=30)
            elif plan.frequency == 'quarterly':
                plan.next_due_date = plan.start_date + timezone.timedelta(days=90)
            elif plan.frequency == 'semi_annual':
                plan.next_due_date = plan.start_date + timezone.timedelta(days=180)
            
            plan.save()
            
            # Create installments
            installment_amount = plan.installment_amount
            for i in range(plan.number_of_installments):
                due_date = plan.start_date + timezone.timedelta(days=30 * i)
                Installment.objects.create(
                    installment_plan=plan,
                    installment_number=i + 1,
                    principal_amount=plan.financed_amount / plan.number_of_installments,
                    total_amount=installment_amount,
                    due_date=due_date
                )
            
            # Process down payment
            if plan.down_payment > 0:
                down_payment = Payment.objects.create(
                    policy=payment.policy,
                    user=request.user,
                    amount=plan.down_payment,
                    status='pending'
                )
                return redirect('core:payment_page', payment_id=down_payment.id)
            
            messages.success(request, 'Installment plan setup successfully!')
            return redirect('core:my_policies')
    else:
        form = InstallmentPlanForm(initial={'policy': payment.policy})
    
    return render(request, 'core/setup_installment.html', {
        'form': form,
        'payment': payment
    })


@login_required
def pay_installment(request, installment_id):
    """Pay an individual installment"""
    installment = get_object_or_404(Installment, id=installment_id, 
                                    installment_plan__user=request.user)
    
    # Create payment for this installment
    payment = Payment.objects.create(
        policy=installment.installment_plan.policy,
        user=request.user,
        amount=installment.total_amount,
        status='pending'
    )
    
    return redirect('core:payment_page', payment_id=payment.id)


# ============================================
# CUSTOMER CANCELLATION VIEWS
# ============================================

@login_required
def request_cancellation(request, policy_id):
    """Request policy cancellation"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id, user=request.user)
    
    if request.method == 'POST':
        form = PolicyCancellationForm(request.POST, user=request.user)
        if form.is_valid():
            cancellation = form.save(commit=False)
            cancellation.policy = policy
            cancellation.user = request.user
            cancellation.total_premium = policy.premium_amount
            cancellation.calculate_refund()
            cancellation.save()
            
            messages.success(request, 'Cancellation request submitted successfully!')
            return redirect('core:cancellation_detail', cancellation_id=cancellation.id)
    else:
        form = PolicyCancellationForm(user=request.user, initial={'policy': policy})
    
    return render(request, 'core/request_cancellation.html', {
        'form': form,
        'policy': policy
    })


@login_required
def cancellation_detail(request, cancellation_id):
    """View cancellation details"""
    cancellation = get_object_or_404(PolicyCancellation, id=cancellation_id, user=request.user)
    
    return render(request, 'core/cancellation_detail.html', {
        'cancellation': cancellation
    })


# ============================================
# AGENT COMMISSION VIEWS
# ============================================

@login_required
@user_passes_test(lambda u: u.role == 'agent')
def agent_commissions(request):
    """View agent commissions"""
    commissions = Commission.objects.filter(agent=request.user).order_by('-earned_date')
    
    # Stats
    total_earned = commissions.aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    total_paid = commissions.filter(status='paid').aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    pending_amount = commissions.filter(status__in=['pending', 'calculated', 'approved']).aggregate(
        Sum('total_commission')
    )['total_commission__sum'] or 0
    
    paginator = Paginator(commissions, 20)
    page = request.GET.get('page')
    commissions_page = paginator.get_page(page)
    
    return render(request, 'core/agent/commissions.html', {
        'commissions': commissions_page,
        'total_earned': total_earned,
        'total_paid': total_paid,
        'pending_amount': pending_amount
    })


@login_required
@user_passes_test(lambda u: u.role == 'agent')
def agent_commission_detail(request, commission_id):
    """View commission details"""
    commission = get_object_or_404(Commission, id=commission_id, agent=request.user)
    
    return render(request, 'core/agent/commission_detail.html', {
        'commission': commission
    })


# ============================================
# NO CLAIM BONUS VIEWS
# ============================================

@login_required
def my_ncb(request):
    """View user's No Claim Bonus"""
    ncb_records = NoClaimBonus.objects.filter(user=request.user).select_related('vehicle')
    
    return render(request, 'core/my_ncb.html', {
        'ncb_records': ncb_records
    })


@login_required
def purchase_ncb_protection(request, ncb_id):
    """Purchase NCB protection"""
    ncb = get_object_or_404(NoClaimBonus, id=ncb_id, user=request.user)
    
    if request.method == 'POST':
        # Create payment for NCB protection
        protection_cost = 5000  # Example cost
        
        payment = Payment.objects.create(
            policy=None,  # Not tied to a specific policy
            user=request.user,
            amount=protection_cost,
            status='pending',
            payment_details={'type': 'ncb_protection', 'ncb_id': str(ncb.id)}
        )
        
        return redirect('core:payment_page', payment_id=payment.id)
    
    return render(request, 'core/purchase_ncb_protection.html', {'ncb': ncb})











from apps.core.decorators import secure_file_upload, check_ip_reputation, rate_limit

@login_required
@check_ip_reputation
@rate_limit(limit=10, window=60)
@secure_file_upload(file_types='image')
def profile(request):
    """User profile view"""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            # Ensure country is set
            if not form.cleaned_data.get('country'):
                form.instance.country = 'NG'
            
            # Save the form
            user = form.save(commit=False)
            
            # Handle empty phone number
            if not user.phone_number or str(user.phone_number).strip() == '':
                user.phone_number = None
            
            user.save()
            
            messages.success(request, 'Profile updated successfully!')
            
            # Log activity
            log_user_activity(request.user, 'update_profile', request)
            
            return redirect('core:profile')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # Set default country for new profiles
        initial_data = {}
        if not request.user.country:
            initial_data['country'] = 'NG'  # Default to Nigeria
        
        form = ProfileUpdateForm(instance=request.user, initial=initial_data)
    
    documents = request.user.documents.all()
    return render(request, 'core/customer/profile.html', {
        'form': form,
        'documents': documents
    })
    
    
    
@login_required
@check_ip_reputation
@rate_limit(limit=5, window=60)
@secure_file_upload(file_types='document')
@require_http_methods(["POST"])
def upload_kyc(request):
    """Upload KYC documents with front/back and selfie options"""
    try:
        document_type = request.POST.get('document_type')
        document_number = request.POST.get('document_number', '')
        document_front = request.FILES.get('document_front')
        document_back = request.FILES.get('document_back')
        selfie_upload = request.FILES.get('selfie')
        selfie_camera = request.POST.get('selfie_camera')
        
        if not all([document_type, document_front]):
            return JsonResponse({'success': False, 'message': 'Document type and front image are required'})
        
        if not selfie_upload and not selfie_camera:
            return JsonResponse({'success': False, 'message': 'Selfie is required'})
        
        # Validate file types
        allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if document_front.content_type not in allowed_types:
            return JsonResponse({'success': False, 'message': 'Document must be PDF, JPG, or PNG'})
        
        if document_back and document_back.content_type not in allowed_types:
            return JsonResponse({'success': False, 'message': 'Document back must be PDF, JPG, or PNG'})
        
        # Check file sizes (5MB max)
        if document_front.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'message': 'Document front must be less than 5MB'})
        if document_back and document_back.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'message': 'Document back must be less than 5MB'})
        
        # Map document type
        doc_type_mapping = {
            'national_id': 'aadhar',
            'drivers_license': 'driving_license',
            'passport': 'other',
            'voters_card': 'other',
        }
        model_doc_type = doc_type_mapping.get(document_type, 'other')
        
        # Save document front
        doc_front = Document.objects.create(
            user=request.user,
            name=f"KYC - {document_type.replace('_', ' ').title()} (Front)",
            document_type=model_doc_type,
            document_number=document_number or '',
            document_file=document_front,
            is_verified=False
        )
        
        # Save document back if provided
        if document_back:
            doc_back = Document.objects.create(
                user=request.user,
                name=f"KYC - {document_type.replace('_', ' ').title()} (Back)",
                document_type=model_doc_type,
                document_number=document_number or '',
                document_file=document_back,
                is_verified=False
            )
        
        # Handle selfie (upload or camera)
        if selfie_upload:
            selfie_doc = Document.objects.create(
                user=request.user,
                name="KYC - Selfie with ID",
                document_type='other',
                document_number='',
                document_file=selfie_upload,
                is_verified=False
            )
        elif selfie_camera:
            # Convert base64 to file
            import base64
            from django.core.files.base import ContentFile
            
            format, imgstr = selfie_camera.split(';base64,')
            ext = format.split('/')[-1]
            
            selfie_file = ContentFile(
                base64.b64decode(imgstr), 
                name=f'selfie_{request.user.id}_{uuid.uuid4().hex[:8]}.{ext}'
            )
            
            selfie_doc = Document.objects.create(
                user=request.user,
                name="KYC - Selfie with ID (Camera)",
                document_type='other',
                document_number='',
                document_file=selfie_file,
                is_verified=False
            )
        
        # Update user KYC status
        request.user.kyc_documents_submitted = True
        request.user.save(update_fields=['kyc_documents_submitted'])
        
        # Log activity
        log_user_activity(request.user, 'upload_kyc', request, {
            'document_type': document_type,
            'has_back': bool(document_back)
        })
        
        # Notify admins
        admin_users = User.objects.filter(role='admin', is_active=True)
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='New KYC Submission',
                message=f'{request.user.get_full_name()} ({request.user.email}) has submitted KYC documents.',
                notification_type='system_alert',
                data={'user_id': str(request.user.id)}
            )
        
        # Notify user
        Notification.objects.create(
            user=request.user,
            title='KYC Documents Submitted',
            message='Your documents have been submitted and are under review.',
            notification_type='system_alert'
        )
        
        return JsonResponse({
            'success': True, 
            'message': 'KYC documents uploaded successfully! Review takes 24-48 hours.'
        })
        
    except Exception as e:
        import traceback
        print(f"KYC Upload Error: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': 'An error occurred. Please try again.'})
    
    

@login_required
def change_password(request):
    """Change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('core:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'core/customer/change_password.html', {'form': form})

import time
from django.core.cache import cache

@login_required
def support_tickets(request):
    """Support tickets view with rate limiting"""
    # Rate limiting - max 3 tickets per hour
    cache_key = f"ticket_rate_{request.user.id}"
    ticket_count = cache.get(cache_key, 0)
    
    if ticket_count >= 5:
        messages.error(request, 'You have reached the maximum number of tickets. Please wait before creating more.')
        return redirect('core:support_tickets')
    
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            
            # Increment rate limit counter
            cache.set(cache_key, ticket_count + 1, 3600)  # 1 hour expiry
            
            # Send notification to support staff
            staff_users = User.objects.filter(role__in=['support', 'admin'], is_active=True)
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title='New Support Ticket',
                    message=f'New ticket #{ticket.ticket_number} from {request.user.get_full_name()}',
                    notification_type='system_alert',
                    data={'ticket_id': str(ticket.id)}
                )
            
            messages.success(request, f'Ticket #{ticket.ticket_number} created successfully! We will respond within 24 hours.')
            return redirect('core:ticket_detail', ticket_id=ticket.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SupportTicketForm()
    
    tickets = request.user.support_tickets.all().order_by('-created_at')
    
    # Calculate statistics
    open_count = tickets.filter(status__in=['open', 'in_progress']).count()
    resolved_count = tickets.filter(status='resolved').count()
    
    paginator = Paginator(tickets, 10)
    page = request.GET.get('page')
    tickets = paginator.get_page(page)
    
    return render(request, 'core/customer/support_tickets.html', {
        'form': form,
        'tickets': tickets,
        'open_count': open_count,
        'resolved_count': resolved_count,
    })


@login_required
def ticket_detail(request, ticket_id):
    """Ticket detail view with security checks"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    if request.method == 'POST':
        form = TicketReplyForm(request.POST, request.FILES)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.ticket = ticket
            reply.user = request.user
            reply.save()
            
            # Reopen ticket if closed
            if ticket.status == 'closed':
                ticket.status = 'open'
                ticket.save()
            
            # Notify assigned staff or all support staff
            if ticket.assigned_to:
                Notification.objects.create(
                    user=ticket.assigned_to,
                    title=f'New Reply - {ticket.ticket_number}',
                    message=f'Customer replied to ticket #{ticket.ticket_number}',
                    notification_type='system_alert'
                )
            
            messages.success(request, 'Reply added successfully!')
            return redirect('core:ticket_detail', ticket_id=ticket.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TicketReplyForm()
    
    return render(request, 'core/customer/ticket_detail.html', {
        'ticket': ticket,
        'form': form
    })

@login_required
def notifications(request):
    """View all notifications"""
    notifications_list = request.user.notifications.all().order_by('-created_at')
    
    # Mark as read
    if request.GET.get('mark_read'):
        notification = get_object_or_404(Notification, id=request.GET['mark_read'], user=request.user)
        notification.is_read = True
        notification.save()
        return redirect('core:notifications')
    
    paginator = Paginator(notifications_list, 20)
    page = request.GET.get('page')
    notifications = paginator.get_page(page)
    
    return render(request, 'core/customer/notifications.html', {'notifications': notifications})


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'success': True})

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip









def home(request):
    """Home page view"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    # Get active promos for home page
    now = timezone.now()
    active_promos = PromoCode.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now,
        applicable_to__in=['all', 'new']
    ).exclude(used_count__gte=models.F('max_uses'))[:3]
    
    # Get recent blog posts
    recent_blog_posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=now
    ).select_related('category')[:3]
    
    # Get insurance settings for plan prices
    from apps.core.models import InsuranceSettings
    settings = InsuranceSettings.get_settings()
    
    context = {
        'total_policies': InsurancePolicy.objects.filter(status='active').count(),
        'total_claims': Claim.objects.filter(status='settled').count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'active_promos': active_promos,
        'recent_blog_posts': recent_blog_posts,
        'min_premium_third_party': int(settings.min_premium_third_party),
        'min_premium_comprehensive': int(settings.min_premium_comprehensive),
        'min_premium_standalone': int(settings.min_premium_standalone),
        'min_premium_personal_accident': int(settings.min_premium_personal_accident),
    }
    return render(request, 'core/home.html', context)


def about(request):
    return render(request, 'core/about.html')


def motor_insurance(request):
    """Display motor insurance plans with dynamic pricing from settings"""
    from apps.core.models import InsuranceSettings
    
    settings = InsuranceSettings.get_settings()
    
    context = {
        'min_premium_third_party': int(settings.min_premium_third_party),
        'min_premium_comprehensive': int(settings.min_premium_comprehensive),
        'min_premium_standalone': int(settings.min_premium_standalone),
        'min_premium_personal_accident': int(settings.min_premium_personal_accident),
        # Add-on costs for reference
        'roadside_assistance_cost': int(settings.roadside_assistance_cost),
        'zero_depreciation_cost': int(settings.zero_depreciation_cost),
        'engine_protection_cost': int(settings.engine_protection_cost),
        'personal_accident_cover_cost': int(settings.personal_accident_cover_cost),
    }
    
    return render(request, 'core/motor_insurance.html', context)


def instant_quote(request):
    return render(request, 'core/instant_quote.html')


def policies_public(request):
    return render(request, 'core/policies.html')


def digital_documents(request):
    return render(request, 'core/digital_documents.html')


def file_claim_public(request):
    return render(request, 'core/file_claim.html')


def track_claims(request):
    return render(request, 'core/track_claims.html')


def secure_payments(request):
    return render(request, 'core/secure_payments.html')


def individual_plans(request):
    """Display individual insurance plans with dynamic pricing from settings"""
    from apps.core.models import InsuranceSettings
    
    settings = InsuranceSettings.get_settings()
    
    context = {
        'min_premium_third_party': int(settings.min_premium_third_party),
        'min_premium_comprehensive': int(settings.min_premium_comprehensive),
        'min_premium_standalone': int(settings.min_premium_standalone),
        'min_premium_personal_accident': int(settings.min_premium_personal_accident),
        # Add-on costs for reference
        'roadside_assistance_cost': int(settings.roadside_assistance_cost),
        'zero_depreciation_cost': int(settings.zero_depreciation_cost),
        'engine_protection_cost': int(settings.engine_protection_cost),
        'personal_accident_cover_cost': int(settings.personal_accident_cover_cost),
    }
    
    return render(request, 'core/individual_plans.html', context)


def premium_calculator(request):
    return render(request, 'core/premium_calculator.html')


def easy_renewals(request):
    return render(request, 'core/easy_renewals.html')


def fleet_insurance(request):
    return render(request, 'core/fleet_insurance.html')


def commercial_coverage(request):
    return render(request, 'core/commercial_coverage.html')


def claims_management(request):
    return render(request, 'core/claims_management.html')


def solutions(request):
    return render(request, 'core/solutions.html')


def support(request):
    return render(request, 'core/support.html')


def faqs(request):
    return render(request, 'core/faqs.html')


def contact(request):
    return render(request, 'core/contact.html')


def claims_support(request):
    return render(request, 'core/claims_support.html')


def careers(request):
    return render(request, 'core/careers.html')


def press(request):
    return render(request, 'core/press.html')

def renew_policy_public(request):
    """Public renew policy page - Information about renewals"""
    return render(request, 'core/renew_policy.html')

def terms(request):
    return render(request, 'core/terms.html')


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


def cookie_policy(request):
    return render(request, 'core/cookie_policy.html')


def cookie_settings(request):
    return render(request, 'core/cookie_settings.html')


def licenses(request):
    return render(request, 'core/licenses.html')


def public_promotions(request):
    """Display available promotions for non-authenticated users (public page)"""
    now = timezone.now()
    
    # Get active promo codes that are valid for new customers or all users
    available_promos = PromoCode.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(used_count__gte=models.F('max_uses'))
    
    # Filter for promos applicable to new customers or all users
    public_promos = []
    new_customer_promos = []
    
    for promo in available_promos:
        if promo.applicable_to in ['all', 'new']:
            public_promos.append(promo)
            if promo.applicable_to == 'new':
                new_customer_promos.append(promo)
    
    context = {
        'promotions': public_promos,
        'new_customer_promos': new_customer_promos,
        'total_promos': len(public_promos),
    }
    
    return render(request, 'core/public_promotions.html', context)













# core/views.py - Add these blog-related views

from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count
from django.utils.text import slugify
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from django.utils.text import slugify

from .models import BlogPost, BlogCategory, BlogTag, BlogComment, NewsletterSubscriber
from .forms import BlogPostForm, BlogCategoryForm, BlogCommentForm, NewsletterSubscribeForm


# ==================== PUBLIC BLOG VIEWS ====================

# core/views.py - Update the blog view and add category/tag views

def blog(request):
    """Public blog listing page"""
    # Get all published posts
    posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    ).select_related('category', 'author').prefetch_related('tags')
    
    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query)
        ).distinct()
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(posts, 9)
    
    try:
        posts_page = paginator.page(page)
    except PageNotAnInteger:
        posts_page = paginator.page(1)
    except EmptyPage:
        posts_page = paginator.page(paginator.num_pages)
    
    # Get featured post
    featured_post = BlogPost.objects.filter(
        status='published',
        is_featured=True,
        published_at__lte=timezone.now()
    ).select_related('category', 'author').first()
    
    # Get categories with post counts
    categories = BlogCategory.objects.filter(
        is_active=True
    ).annotate(post_count=Count('posts', filter=Q(posts__status='published'))).filter(post_count__gt=0)
    
    # Get popular posts
    popular_posts = BlogPost.get_popular_posts(limit=5)
    
    # Get recent posts
    recent_posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    )[:5]
    
    # Get all tags
    tags = BlogTag.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).filter(post_count__gt=0)[:20]
    
    context = {
        'posts': posts_page,
        'featured_post': featured_post,
        'categories': categories,
        'popular_posts': popular_posts,
        'recent_posts': recent_posts,
        'tags': tags,
        'selected_category': None,
        'selected_tag': None,
        'search_query': search_query,
        'total_posts': paginator.count,
    }
    
    return render(request, 'core/blog.html', context)


def blog_by_category(request, category_slug):
    """Public blog listing filtered by category"""
    # Get the category
    selected_category = get_object_or_404(BlogCategory, slug=category_slug, is_active=True)
    
    # Get all published posts in this category
    posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now(),
        category=selected_category
    ).select_related('category', 'author').prefetch_related('tags')
    
    # Search functionality (within category)
    search_query = request.GET.get('q', '')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query)
        ).distinct()
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(posts, 9)
    
    try:
        posts_page = paginator.page(page)
    except PageNotAnInteger:
        posts_page = paginator.page(1)
    except EmptyPage:
        posts_page = paginator.page(paginator.num_pages)
    
    # Get featured post (from this category if available, otherwise general)
    featured_post = BlogPost.objects.filter(
        status='published',
        is_featured=True,
        published_at__lte=timezone.now(),
        category=selected_category
    ).select_related('category', 'author').first()
    
    if not featured_post:
        featured_post = BlogPost.objects.filter(
            status='published',
            is_featured=True,
            published_at__lte=timezone.now()
        ).select_related('category', 'author').first()
    
    # Get categories with post counts
    categories = BlogCategory.objects.filter(
        is_active=True
    ).annotate(post_count=Count('posts', filter=Q(posts__status='published'))).filter(post_count__gt=0)
    
    # Get popular posts
    popular_posts = BlogPost.get_popular_posts(limit=5)
    
    # Get recent posts
    recent_posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    )[:5]
    
    # Get all tags
    tags = BlogTag.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).filter(post_count__gt=0)[:20]
    
    context = {
        'posts': posts_page,
        'featured_post': featured_post,
        'categories': categories,
        'popular_posts': popular_posts,
        'recent_posts': recent_posts,
        'tags': tags,
        'selected_category': selected_category,
        'selected_tag': None,
        'search_query': search_query,
        'total_posts': paginator.count,
    }
    
    return render(request, 'core/blog.html', context)


def blog_by_tag(request, tag_slug):
    """Public blog listing filtered by tag"""
    # Get the tag
    selected_tag = get_object_or_404(BlogTag, slug=tag_slug)
    
    # Get all published posts with this tag
    posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now(),
        tags=selected_tag
    ).select_related('category', 'author').prefetch_related('tags').distinct()
    
    # Search functionality (within tag)
    search_query = request.GET.get('q', '')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query)
        ).distinct()
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(posts, 9)
    
    try:
        posts_page = paginator.page(page)
    except PageNotAnInteger:
        posts_page = paginator.page(1)
    except EmptyPage:
        posts_page = paginator.page(paginator.num_pages)
    
    # Get featured post
    featured_post = BlogPost.objects.filter(
        status='published',
        is_featured=True,
        published_at__lte=timezone.now()
    ).select_related('category', 'author').first()
    
    # Get categories with post counts
    categories = BlogCategory.objects.filter(
        is_active=True
    ).annotate(post_count=Count('posts', filter=Q(posts__status='published'))).filter(post_count__gt=0)
    
    # Get popular posts
    popular_posts = BlogPost.get_popular_posts(limit=5)
    
    # Get recent posts
    recent_posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    )[:5]
    
    # Get all tags
    tags = BlogTag.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).filter(post_count__gt=0)[:20]
    
    context = {
        'posts': posts_page,
        'featured_post': featured_post,
        'categories': categories,
        'popular_posts': popular_posts,
        'recent_posts': recent_posts,
        'tags': tags,
        'selected_category': None,
        'selected_tag': selected_tag,
        'search_query': search_query,
        'total_posts': paginator.count,
    }
    
    return render(request, 'core/blog.html', context)


def blog_detail(request, slug):
    """Public blog detail page"""
    post = get_object_or_404(
        BlogPost.objects.select_related('category', 'author').prefetch_related('tags'),
        slug=slug,
        status='published',
        published_at__lte=timezone.now()
    )
    
    # Increment view count
    post.increment_views()
    
    # Get related posts
    related_posts = BlogPost.get_related_posts(post, limit=3)
    
    # Get comments
    comments = post.comments.filter(is_approved=True, parent=None).select_related('user')
    
    # Comment form
    if request.method == 'POST':
        comment_form = BlogCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            if request.user.is_authenticated:
                comment.user = request.user
                comment.name = request.user.get_full_name() or request.user.username
                comment.email = request.user.email
            comment.ip_address = get_client_ip(request)
            comment.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            comment.save()
            messages.success(request, 'Your comment has been submitted and is awaiting approval.')
            return redirect('core:blog_detail', slug=post.slug)
    else:
        comment_form = BlogCommentForm()
    
    # Get categories for sidebar
    categories = BlogCategory.objects.filter(
        is_active=True
    ).annotate(post_count=Count('posts', filter=Q(posts__status='published'))).filter(post_count__gt=0)
    
    # Get popular posts for sidebar
    popular_posts = BlogPost.get_popular_posts(limit=5)
    
    context = {
        'post': post,
        'related_posts': related_posts,
        'comments': comments,
        'comment_form': comment_form,
        'categories': categories,
        'popular_posts': popular_posts,
        'meta_title': post.meta_title or post.title,
        'meta_description': post.meta_description or post.excerpt[:160],
    }
    
    return render(request, 'core/blog_detail.html', context)


@require_http_methods(["POST"])
def newsletter_subscribe(request):
    """Handle newsletter subscription"""
    form = NewsletterSubscribeForm(request.POST)
    
    if form.is_valid():
        email = form.cleaned_data['email']
        name = form.cleaned_data.get('name', '')
        
        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
                'is_active': True,
                'ip_address': get_client_ip(request),
                'source': 'blog_sidebar'
            }
        )
        
        if not created and not subscriber.is_active:
            subscriber.is_active = True
            subscriber.unsubscribed_at = None
            subscriber.save()
            messages.success(request, 'You have been re-subscribed to our newsletter!')
        elif created:
            messages.success(request, 'Successfully subscribed to our newsletter!')
        else:
            messages.info(request, 'You are already subscribed to our newsletter.')
    else:
        messages.error(request, 'Please enter a valid email address.')
    
    # Redirect back to the referring page
    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)


# ==================== STAFF BLOG MANAGEMENT VIEWS ====================

def is_staff_user(user):
    """Check if user has staff permissions"""
    return user.is_authenticated and user.role in ['admin', 'agent', 'support']


@login_required
@user_passes_test(is_staff_user)
def blog_manage(request):
    """Staff blog management dashboard"""
    posts = BlogPost.objects.all().select_related('category', 'author')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        posts = posts.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(posts, 20)
    
    try:
        posts_page = paginator.page(page)
    except:
        posts_page = paginator.page(1)
    
    # Stats
    stats = {
        'total': BlogPost.objects.count(),
        'published': BlogPost.objects.filter(status='published').count(),
        'draft': BlogPost.objects.filter(status='draft').count(),
        'archived': BlogPost.objects.filter(status='archived').count(),
        'total_views': BlogPost.objects.aggregate(total=Sum('views_count'))['total'] or 0,
    }
    
    context = {
        'posts': posts_page,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/staff/blog_manage.html', context)


@login_required
@user_passes_test(is_staff_user)
def blog_create(request):
    """Create a new blog post (Staff)"""
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_tags(post)
            
            messages.success(request, f'Blog post "{post.title}" created successfully!')
            return redirect('core:blog_manage')
    else:
        form = BlogPostForm()
    
    context = {
        'form': form,
        'title': 'Create New Blog Post',
        'submit_text': 'Create Post',
    }
    
    return render(request, 'core/staff/blog_form.html', context)


@login_required
@user_passes_test(is_staff_user)
def blog_edit(request, post_id):
    """Edit an existing blog post (Staff)"""
    post = get_object_or_404(BlogPost, id=post_id)
    
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save()
            form.save_tags(post)
            
            messages.success(request, f'Blog post "{post.title}" updated successfully!')
            return redirect('core:blog_manage')
    else:
        form = BlogPostForm(instance=post)
    
    context = {
        'form': form,
        'post': post,
        'title': f'Edit: {post.title}',
        'submit_text': 'Update Post',
    }
    
    return render(request, 'core/staff/blog_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def blog_delete(request, post_id):
    """Delete a blog post (Staff)"""
    post = get_object_or_404(BlogPost, id=post_id)
    title = post.title
    post.delete()
    
    messages.success(request, f'Blog post "{title}" deleted successfully!')
    return redirect('core:blog_manage')


@login_required
@user_passes_test(is_staff_user)
def blog_categories_manage(request):
    """Manage blog categories (Staff)"""
    categories = BlogCategory.objects.all().annotate(post_count=Count('posts'))
    
    if request.method == 'POST':
        form = BlogCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('core:blog_categories_manage')
    else:
        form = BlogCategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'core/staff/blog_categories.html', context)


@login_required
@user_passes_test(is_staff_user)
def blog_category_edit(request, category_id):
    """Edit a blog category (Staff)"""
    category = get_object_or_404(BlogCategory, id=category_id)
    
    if request.method == 'POST':
        form = BlogCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('core:blog_categories_manage')
    else:
        form = BlogCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
    }
    
    return render(request, 'core/staff/blog_category_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def blog_category_delete(request, category_id):
    """Delete a blog category (Staff)"""
    category = get_object_or_404(BlogCategory, id=category_id)
    name = category.name
    category.delete()
    
    messages.success(request, f'Category "{name}" deleted successfully!')
    return redirect('core:blog_categories_manage')


@login_required
@user_passes_test(is_staff_user)
def blog_comments_manage(request):
    """Manage blog comments (Staff)"""
    comments = BlogComment.objects.all().select_related('post', 'user')
    
    # Filter by approval status
    filter_status = request.GET.get('status', 'pending')
    if filter_status == 'pending':
        comments = comments.filter(is_approved=False)
    elif filter_status == 'approved':
        comments = comments.filter(is_approved=True)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(comments, 30)
    
    try:
        comments_page = paginator.page(page)
    except:
        comments_page = paginator.page(1)
    
    stats = {
        'total': BlogComment.objects.count(),
        'pending': BlogComment.objects.filter(is_approved=False).count(),
        'approved': BlogComment.objects.filter(is_approved=True).count(),
    }
    
    context = {
        'comments': comments_page,
        'stats': stats,
        'filter_status': filter_status,
    }
    
    return render(request, 'core/staff/blog_comments.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def blog_comment_approve(request, comment_id):
    """Approve a blog comment (Staff)"""
    comment = get_object_or_404(BlogComment, id=comment_id)
    comment.is_approved = True
    comment.save()
    
    return JsonResponse({'success': True, 'message': 'Comment approved!'})


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def blog_comment_delete(request, comment_id):
    """Delete a blog comment (Staff)"""
    comment = get_object_or_404(BlogComment, id=comment_id)
    comment.delete()
    
    return JsonResponse({'success': True, 'message': 'Comment deleted!'})


@login_required
@user_passes_test(is_staff_user)
def newsletter_subscribers_manage(request):
    """Manage newsletter subscribers (Staff)"""
    subscribers = NewsletterSubscriber.objects.all()
    
    # Filter by status
    filter_status = request.GET.get('status', 'active')
    if filter_status == 'active':
        subscribers = subscribers.filter(is_active=True)
    elif filter_status == 'inactive':
        subscribers = subscribers.filter(is_active=False)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        subscribers = subscribers.filter(email__icontains=search_query)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(subscribers, 50)
    
    try:
        subscribers_page = paginator.page(page)
    except:
        subscribers_page = paginator.page(1)
    
    stats = {
        'total': NewsletterSubscriber.objects.count(),
        'active': NewsletterSubscriber.objects.filter(is_active=True).count(),
        'inactive': NewsletterSubscriber.objects.filter(is_active=False).count(),
        'confirmed': NewsletterSubscriber.objects.filter(is_confirmed=True).count(),
    }
    
    context = {
        'subscribers': subscribers_page,
        'stats': stats,
        'filter_status': filter_status,
        'search_query': search_query,
    }
    
    return render(request, 'core/staff/newsletter_subscribers.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def blog_preview(request):
    """Preview blog post content (AJAX)"""
    data = json.loads(request.body)
    content = data.get('content', '')
    title = data.get('title', '')
    
    # You can add markdown processing here if needed
    html_content = content
    
    return JsonResponse({
        'success': True,
        'html': html_content
    })
    
    
    
    
    
    
    
# Add these views to your views.py
import csv
from django.http import HttpResponse

@login_required
@user_passes_test(is_staff_user)
def newsletter_subscribers_manage(request):
    """Manage newsletter subscribers (Staff)"""
    subscribers = NewsletterSubscriber.objects.all()
    
    # Filter by status
    filter_status = request.GET.get('status', 'all')
    if filter_status == 'active':
        subscribers = subscribers.filter(is_active=True)
    elif filter_status == 'inactive':
        subscribers = subscribers.filter(is_active=False)
    elif filter_status == 'confirmed':
        subscribers = subscribers.filter(is_confirmed=True)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        subscribers = subscribers.filter(
            Q(email__icontains=search_query) | 
            Q(name__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(subscribers, 50)
    
    try:
        subscribers_page = paginator.page(page)
    except:
        subscribers_page = paginator.page(1)
    
    stats = {
        'total': NewsletterSubscriber.objects.count(),
        'active': NewsletterSubscriber.objects.filter(is_active=True).count(),
        'inactive': NewsletterSubscriber.objects.filter(is_active=False).count(),
        'confirmed': NewsletterSubscriber.objects.filter(is_confirmed=True).count(),
    }
    
    context = {
        'subscribers': subscribers_page,
        'stats': stats,
        'filter_status': filter_status,
        'search_query': search_query,
    }
    
    return render(request, 'core/staff/newsletter_subscribers.html', context)


@login_required
@user_passes_test(is_staff_user)
def newsletter_subscribers_export(request):
    """Export subscribers to CSV"""
    filter_status = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    subscribers = NewsletterSubscriber.objects.all()
    
    if filter_status == 'active':
        subscribers = subscribers.filter(is_active=True)
    elif filter_status == 'inactive':
        subscribers = subscribers.filter(is_active=False)
    elif filter_status == 'confirmed':
        subscribers = subscribers.filter(is_confirmed=True)
    
    if search_query:
        subscribers = subscribers.filter(
            Q(email__icontains=search_query) | 
            Q(name__icontains=search_query)
        )
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="newsletter_subscribers_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Email', 'Name', 'Status', 'Confirmed', 'Source', 'Subscribed Date', 'IP Address'])
    
    for subscriber in subscribers:
        writer.writerow([
            subscriber.email,
            subscriber.name or '',
            'Active' if subscriber.is_active else 'Inactive',
            'Yes' if subscriber.is_confirmed else 'No',
            subscriber.source or 'Website',
            subscriber.subscribed_at.strftime('%Y-%m-%d %H:%M'),
            subscriber.ip_address or '',
        ])
    
    return response


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def newsletter_unsubscribe(request, subscriber_id):
    """Unsubscribe a subscriber"""
    subscriber = get_object_or_404(NewsletterSubscriber, id=subscriber_id)
    subscriber.unsubscribe()
    messages.success(request, f'{subscriber.email} has been unsubscribed.')
    return redirect('core:newsletter_subscribers_manage')


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def newsletter_resubscribe(request, subscriber_id):
    """Reactivate a subscriber"""
    subscriber = get_object_or_404(NewsletterSubscriber, id=subscriber_id)
    subscriber.is_active = True
    subscriber.unsubscribed_at = None
    subscriber.save()
    messages.success(request, f'{subscriber.email} has been reactivated.')
    return redirect('core:newsletter_subscribers_manage')


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def newsletter_delete(request, subscriber_id):
    """Permanently delete a subscriber"""
    subscriber = get_object_or_404(NewsletterSubscriber, id=subscriber_id)
    email = subscriber.email
    subscriber.delete()
    messages.success(request, f'{email} has been permanently deleted.')
    return redirect('core:newsletter_subscribers_manage')





# Add to your views.py

from .models import PressRelease, PressCategory, MediaCoverage, MediaKit
from .forms import PressReleaseForm, PressCategoryForm, MediaCoverageForm, MediaKitForm


# ==================== PUBLIC PRESS VIEWS ====================

def press(request):
    """Public press and media page"""
    # Get all published press releases
    releases = PressRelease.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    ).select_related('category', 'author')
    
    # Filter by category
    category_slug = request.GET.get('category')
    selected_category = None
    if category_slug:
        selected_category = get_object_or_404(PressCategory, slug=category_slug, is_active=True)
        releases = releases.filter(category=selected_category)
    
    # Filter by year
    year = request.GET.get('year')
    if year:
        releases = releases.filter(press_date__year=year)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        releases = releases.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query)
        ).distinct()
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(releases, 12)
    
    try:
        releases_page = paginator.page(page)
    except:
        releases_page = paginator.page(1)
    
    # Get featured releases
    featured_releases = PressRelease.get_featured_releases(limit=3)
    
    # Get recent releases
    recent_releases = PressRelease.get_recent_releases(limit=5)
    
    # Get categories
    categories = PressCategory.objects.filter(is_active=True).annotate(
        release_count=Count('releases', filter=Q(releases__status='published'))
    ).filter(release_count__gt=0)
    
    # Get media coverage
    media_coverage = MediaCoverage.objects.filter(is_active=True).order_by('-coverage_date')[:6]
    
    # Get media kit resources
    media_kit = MediaKit.objects.filter(is_active=True)[:6]
    
    # Get available years for filtering
    years = PressRelease.objects.filter(status='published').dates('press_date', 'year').distinct()
    
    context = {
        'releases': releases_page,
        'featured_releases': featured_releases,
        'recent_releases': recent_releases,
        'categories': categories,
        'media_coverage': media_coverage,
        'media_kit': media_kit,
        'years': years,
        'selected_category': selected_category,
        'selected_year': year,
        'search_query': search_query,
        'total_releases': paginator.count,
    }
    
    return render(request, 'core/press.html', context)


def press_detail(request, slug):
    """Public press release detail page"""
    release = get_object_or_404(
        PressRelease.objects.select_related('category', 'author'),
        slug=slug,
        status='published',
        published_at__lte=timezone.now()
    )
    
    # Increment view count
    release.increment_views()
    
    # Get related releases (same category)
    related_releases = PressRelease.objects.filter(
        status='published',
        category=release.category,
        published_at__lte=timezone.now()
    ).exclude(id=release.id)[:3]
    
    # Get recent releases
    recent_releases = PressRelease.get_recent_releases(limit=5)
    
    # Get categories
    categories = PressCategory.objects.filter(is_active=True).annotate(
        release_count=Count('releases', filter=Q(releases__status='published'))
    ).filter(release_count__gt=0)
    
    context = {
        'release': release,
        'related_releases': related_releases,
        'recent_releases': recent_releases,
        'categories': categories,
        'meta_title': release.meta_title or release.title,
        'meta_description': release.meta_description or release.excerpt[:160],
    }
    
    return render(request, 'core/press_detail.html', context)


def media_kit_download(request, kit_id):
    """Download media kit file"""
    kit = get_object_or_404(MediaKit, id=kit_id, is_active=True)
    kit.increment_downloads()
    return redirect(kit.file.url)


# ==================== STAFF PRESS MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_staff_user)
def press_manage(request):
    """Staff press management dashboard"""
    releases = PressRelease.objects.all().select_related('category', 'author')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        releases = releases.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        releases = releases.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(releases, 20)
    
    try:
        releases_page = paginator.page(page)
    except:
        releases_page = paginator.page(1)
    
    stats = {
        'total': PressRelease.objects.count(),
        'published': PressRelease.objects.filter(status='published').count(),
        'draft': PressRelease.objects.filter(status='draft').count(),
        'archived': PressRelease.objects.filter(status='archived').count(),
    }
    
    context = {
        'releases': releases_page,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/staff/press_manage.html', context)


@login_required
@user_passes_test(is_staff_user)
def press_create(request):
    """Create a new press release (Staff)"""
    if request.method == 'POST':
        form = PressReleaseForm(request.POST, request.FILES)
        if form.is_valid():
            release = form.save(commit=False)
            release.author = request.user
            release.save()
            
            messages.success(request, f'Press release "{release.title}" created successfully!')
            return redirect('core:press_manage')
    else:
        form = PressReleaseForm()
    
    context = {
        'form': form,
        'title': 'Create New Press Release',
        'submit_text': 'Publish Release',
    }
    
    return render(request, 'core/staff/press_form.html', context)


@login_required
@user_passes_test(is_staff_user)
def press_edit(request, release_id):
    """Edit a press release (Staff)"""
    release = get_object_or_404(PressRelease, id=release_id)
    
    if request.method == 'POST':
        form = PressReleaseForm(request.POST, request.FILES, instance=release)
        if form.is_valid():
            release = form.save()
            messages.success(request, f'Press release "{release.title}" updated successfully!')
            return redirect('core:press_manage')
    else:
        form = PressReleaseForm(instance=release)
    
    context = {
        'form': form,
        'release': release,
        'title': f'Edit: {release.title}',
        'submit_text': 'Update Release',
    }
    
    return render(request, 'core/staff/press_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def press_delete(request, release_id):
    """Delete a press release (Staff)"""
    release = get_object_or_404(PressRelease, id=release_id)
    title = release.title
    release.delete()
    
    messages.success(request, f'Press release "{title}" deleted successfully!')
    return redirect('core:press_manage')


@login_required
@user_passes_test(is_staff_user)
def press_categories_manage(request):
    """Manage press categories (Staff)"""
    categories = PressCategory.objects.all().annotate(release_count=Count('releases'))
    
    if request.method == 'POST':
        form = PressCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('core:press_categories_manage')
    else:
        form = PressCategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'core/staff/press_categories.html', context)


# In views.py
def press_category_edit(request, category_id):
    """Edit a press category (Staff)"""
    # Try to get by UUID first, fallback to integer ID
    try:
        category = PressCategory.objects.get(id=category_id)
    except (PressCategory.DoesNotExist, ValueError):
        # If it's an integer, try to get by pk
        try:
            category = PressCategory.objects.get(pk=category_id)
        except PressCategory.DoesNotExist:
            raise Http404("Category not found")
    
    if request.method == 'POST':
        form = PressCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('core:press_categories_manage')
    else:
        form = PressCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
    }
    
    return render(request, 'core/staff/press_category_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def press_category_delete(request, category_id):
    """Delete a press category (Staff)"""
    try:
        category = PressCategory.objects.get(id=category_id)
    except (PressCategory.DoesNotExist, ValueError):
        try:
            category = PressCategory.objects.get(pk=category_id)
        except PressCategory.DoesNotExist:
            raise Http404("Category not found")
    
    name = category.name
    category.delete()
    
    messages.success(request, f'Category "{name}" deleted successfully!')
    return redirect('core:press_categories_manage')


@login_required
@user_passes_test(is_staff_user)
def media_coverage_manage(request):
    """Manage media coverage (Staff)"""
    coverage = MediaCoverage.objects.all()
    
    if request.method == 'POST':
        form = MediaCoverageForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Media coverage added successfully!')
            return redirect('core:media_coverage_manage')
    else:
        form = MediaCoverageForm()
    
    context = {
        'coverage_items': coverage,
        'form': form,
    }
    
    return render(request, 'core/staff/media_coverage.html', context)


@login_required
@user_passes_test(is_staff_user)
def media_coverage_edit(request, coverage_id):
    """Edit media coverage (Staff)"""
    coverage = get_object_or_404(MediaCoverage, id=coverage_id)
    
    if request.method == 'POST':
        form = MediaCoverageForm(request.POST, request.FILES, instance=coverage)
        if form.is_valid():
            form.save()
            messages.success(request, 'Media coverage updated successfully!')
            return redirect('core:media_coverage_manage')
    else:
        form = MediaCoverageForm(instance=coverage)
    
    context = {
        'form': form,
        'coverage': coverage,
    }
    
    return render(request, 'core/staff/media_coverage_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def media_coverage_delete(request, coverage_id):
    """Delete media coverage (Staff)"""
    coverage = get_object_or_404(MediaCoverage, id=coverage_id)
    coverage.delete()
    
    messages.success(request, 'Media coverage deleted successfully!')
    return redirect('core:media_coverage_manage')


@login_required
@user_passes_test(is_staff_user)
def media_kit_manage(request):
    """Manage media kit resources (Staff)"""
    kits = MediaKit.objects.all()
    
    if request.method == 'POST':
        form = MediaKitForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Media kit item added successfully!')
            return redirect('core:media_kit_manage')
    else:
        form = MediaKitForm()
    
    context = {
        'kits': kits,
        'form': form,
    }
    
    return render(request, 'core/staff/media_kit.html', context)


@login_required
@user_passes_test(is_staff_user)
def media_kit_edit(request, kit_id):
    """Edit media kit item (Staff)"""
    kit = get_object_or_404(MediaKit, id=kit_id)
    
    if request.method == 'POST':
        form = MediaKitForm(request.POST, request.FILES, instance=kit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Media kit item updated successfully!')
            return redirect('core:media_kit_manage')
    else:
        form = MediaKitForm(instance=kit)
    
    context = {
        'form': form,
        'kit': kit,
    }
    
    return render(request, 'core/staff/media_kit_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def media_kit_delete(request, kit_id):
    """Delete media kit item (Staff)"""
    kit = get_object_or_404(MediaKit, id=kit_id)
    kit.delete()
    
    messages.success(request, 'Media kit item deleted successfully!')
    return redirect('core:media_kit_manage')





# Add to your views.py
from django.db.models import Q
from .models import JobPosting, JobCategory, JobLocation, JobType, JobApplication
from .forms import JobPostingForm, JobCategoryForm, JobLocationForm, JobTypeForm, JobApplicationForm


# ==================== PUBLIC CAREERS VIEWS ====================

def careers(request):
    """Public careers/job listings page"""
    # Get open jobs
    jobs = JobPosting.get_open_jobs().select_related('category', 'location', 'job_type')
    
    # Filter by category
    category_slug = request.GET.get('category')
    selected_category = None
    if category_slug:
        selected_category = get_object_or_404(JobCategory, slug=category_slug, is_active=True)
        jobs = jobs.filter(category=selected_category)
    
    # Filter by location
    location_slug = request.GET.get('location')
    selected_location = None
    if location_slug:
        selected_location = get_object_or_404(JobLocation, slug=location_slug, is_active=True)
        jobs = jobs.filter(location=selected_location)
    
    # Filter by job type
    type_slug = request.GET.get('type')
    selected_type = None
    if type_slug:
        selected_type = get_object_or_404(JobType, slug=type_slug, is_active=True)
        jobs = jobs.filter(job_type=selected_type)
    
    # Filter remote only
    remote_only = request.GET.get('remote') == 'true'
    if remote_only:
        jobs = jobs.filter(is_remote=True)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(description__icontains=search_query)
        ).distinct()
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(jobs, 10)
    
    try:
        jobs_page = paginator.page(page)
    except:
        jobs_page = paginator.page(1)
    
    # Get featured jobs
    featured_jobs = JobPosting.get_featured_jobs(limit=3)
    
    # Get categories with job counts
    categories = JobCategory.objects.filter(is_active=True).annotate(
        job_count=Count('jobs', filter=Q(
            jobs__status='published', 
            jobs__is_active=True
        ) & (Q(jobs__expires_at__isnull=True) | Q(jobs__expires_at__gte=timezone.now().date())))
    ).filter(job_count__gt=0)
    
    # Get locations with job counts
    locations = JobLocation.objects.filter(is_active=True).annotate(
        job_count=Count('jobs', filter=Q(
            jobs__status='published', 
            jobs__is_active=True
        ) & (Q(jobs__expires_at__isnull=True) | Q(jobs__expires_at__gte=timezone.now().date())))
    ).filter(job_count__gt=0)
    
    # Get job types
    job_types = JobType.objects.filter(is_active=True).annotate(
        job_count=Count('jobs', filter=Q(
            jobs__status='published', 
            jobs__is_active=True
        ) & (Q(jobs__expires_at__isnull=True) | Q(jobs__expires_at__gte=timezone.now().date())))
    ).filter(job_count__gt=0)
    
    context = {
        'jobs': jobs_page,
        'featured_jobs': featured_jobs,
        'categories': categories,
        'locations': locations,
        'job_types': job_types,
        'selected_category': selected_category,
        'selected_location': selected_location,
        'selected_type': selected_type,
        'remote_only': remote_only,
        'search_query': search_query,
        'total_jobs': paginator.count,
    }
    
    return render(request, 'core/careers.html', context)


def job_detail(request, slug):
    """Public job detail page"""
    job = get_object_or_404(
        JobPosting.objects.select_related('category', 'location', 'job_type'),
        slug=slug,
        status='published',
        is_active=True
    )
    
    # Check if job is still open
    if job.expires_at and job.expires_at < timezone.now().date():
        messages.warning(request, 'This job posting has expired.')
    
    # Increment view count
    job.increment_views()
    
    # Get related jobs (same category)
    related_jobs = JobPosting.objects.filter(
        status='published',
        is_active=True,
        category=job.category
    ).exclude(id=job.id).select_related('location', 'job_type')[:3]
    
    # Application form
    if request.method == 'POST' and job.is_open:
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.ip_address = get_client_ip(request)
            application.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            application.save()
            
            job.increment_applications()
            
            messages.success(request, 'Your application has been submitted successfully! We will review it and get back to you soon.')
            return redirect('core:job_detail', slug=job.slug)
    else:
        form = JobApplicationForm()
    
    context = {
        'job': job,
        'related_jobs': related_jobs,
        'form': form,
        'meta_title': job.meta_title or job.title,
        'meta_description': job.meta_description or job.short_description[:160],
    }
    
    return render(request, 'core/job_detail.html', context)


# ==================== STAFF JOB MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_staff_user)
def jobs_manage(request):
    """Staff job management dashboard"""
    jobs = JobPosting.objects.all().select_related('category', 'location', 'job_type')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        jobs = jobs.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query) |
            Q(short_description__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(jobs, 20)
    
    try:
        jobs_page = paginator.page(page)
    except:
        jobs_page = paginator.page(1)
    
    stats = {
        'total': JobPosting.objects.count(),
        'published': JobPosting.objects.filter(status='published').count(),
        'draft': JobPosting.objects.filter(status='draft').count(),
        'closed': JobPosting.objects.filter(status='closed').count(),
        'total_applications': JobApplication.objects.count(),
        'pending_applications': JobApplication.objects.filter(status='pending').count(),
    }
    
    context = {
        'jobs': jobs_page,
        'stats': stats,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/staff/jobs_manage.html', context)


@login_required
@user_passes_test(is_staff_user)
def job_create(request):
    """Create a new job posting (Staff)"""
    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by = request.user
            job.save()
            
            messages.success(request, f'Job "{job.title}" created successfully!')
            return redirect('core:jobs_manage')
    else:
        form = JobPostingForm()
    
    context = {
        'form': form,
        'title': 'Create New Job Posting',
        'submit_text': 'Create Job',
    }
    
    return render(request, 'core/staff/job_form.html', context)


@login_required
@user_passes_test(is_staff_user)
def job_edit(request, job_id):
    """Edit a job posting (Staff)"""
    job = get_object_or_404(JobPosting, id=job_id)
    
    if request.method == 'POST':
        form = JobPostingForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save(commit=False)
            job.updated_by = request.user
            job.save()
            
            messages.success(request, f'Job "{job.title}" updated successfully!')
            return redirect('core:jobs_manage')
    else:
        form = JobPostingForm(instance=job)
    
    context = {
        'form': form,
        'job': job,
        'title': f'Edit: {job.title}',
        'submit_text': 'Update Job',
    }
    
    return render(request, 'core/staff/job_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def job_delete(request, job_id):
    """Delete a job posting (Staff)"""
    job = get_object_or_404(JobPosting, id=job_id)
    title = job.title
    job.delete()
    
    messages.success(request, f'Job "{title}" deleted successfully!')
    return redirect('core:jobs_manage')


@login_required
@user_passes_test(is_staff_user)
def job_categories_manage(request):
    """Manage job categories (Staff)"""
    categories = JobCategory.objects.all().annotate(job_count=Count('jobs'))
    
    if request.method == 'POST':
        form = JobCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('core:job_categories_manage')
    else:
        form = JobCategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'core/staff/job_categories.html', context)


@login_required
@user_passes_test(is_staff_user)
def job_category_edit(request, category_id):
    """Edit a job category (Staff)"""
    # Try to get by UUID first, fallback to integer ID
    try:
        category = JobCategory.objects.get(id=category_id)
    except (JobCategory.DoesNotExist, ValueError):
        try:
            category = JobCategory.objects.get(pk=category_id)
        except JobCategory.DoesNotExist:
            raise Http404("Category not found")
    
    if request.method == 'POST':
        form = JobCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('core:job_categories_manage')
    else:
        form = JobCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
    }
    
    return render(request, 'core/staff/job_category_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def job_category_delete(request, category_id):
    """Delete a job category (Staff)"""
    try:
        category = JobCategory.objects.get(id=category_id)
    except (JobCategory.DoesNotExist, ValueError):
        try:
            category = JobCategory.objects.get(pk=category_id)
        except JobCategory.DoesNotExist:
            raise Http404("Category not found")
    
    name = category.name
    category.delete()
    
    messages.success(request, f'Category "{name}" deleted successfully!')
    return redirect('core:job_categories_manage')


@login_required
@user_passes_test(is_staff_user)
def job_locations_manage(request):
    """Manage job locations (Staff)"""
    locations = JobLocation.objects.all().annotate(job_count=Count('jobs'))
    
    if request.method == 'POST':
        form = JobLocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Location created successfully!')
            return redirect('core:job_locations_manage')
    else:
        form = JobLocationForm()
    
    context = {
        'locations': locations,
        'form': form,
    }
    
    return render(request, 'core/staff/job_locations.html', context)


@login_required
@user_passes_test(is_staff_user)
def job_location_edit(request, location_id):
    """Edit a job location (Staff)"""
    try:
        location = JobLocation.objects.get(id=location_id)
    except (JobLocation.DoesNotExist, ValueError):
        try:
            location = JobLocation.objects.get(pk=location_id)
        except JobLocation.DoesNotExist:
            raise Http404("Location not found")
    
    if request.method == 'POST':
        form = JobLocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, 'Location updated successfully!')
            return redirect('core:job_locations_manage')
    else:
        form = JobLocationForm(instance=location)
    
    context = {
        'form': form,
        'location': location,
    }
    
    return render(request, 'core/staff/job_location_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def job_location_delete(request, location_id):
    """Delete a job location (Staff)"""
    try:
        location = JobLocation.objects.get(id=location_id)
    except (JobLocation.DoesNotExist, ValueError):
        try:
            location = JobLocation.objects.get(pk=location_id)
        except JobLocation.DoesNotExist:
            raise Http404("Location not found")
    
    name = location.name
    location.delete()
    
    messages.success(request, f'Location "{name}" deleted successfully!')
    return redirect('core:job_locations_manage')


@login_required
@user_passes_test(is_staff_user)
def job_types_manage(request):
    """Manage job types (Staff)"""
    job_types = JobType.objects.all().annotate(job_count=Count('jobs'))
    
    if request.method == 'POST':
        form = JobTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job type created successfully!')
            return redirect('core:job_types_manage')
    else:
        form = JobTypeForm()
    
    context = {
        'job_types': job_types,
        'form': form,
    }
    
    return render(request, 'core/staff/job_types.html', context)


@login_required
@user_passes_test(is_staff_user)
def job_type_edit(request, type_id):
    """Edit a job type (Staff)"""
    try:
        job_type = JobType.objects.get(id=type_id)
    except (JobType.DoesNotExist, ValueError):
        try:
            job_type = JobType.objects.get(pk=type_id)
        except JobType.DoesNotExist:
            raise Http404("Job type not found")
    
    if request.method == 'POST':
        form = JobTypeForm(request.POST, instance=job_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job type updated successfully!')
            return redirect('core:job_types_manage')
    else:
        form = JobTypeForm(instance=job_type)
    
    context = {
        'form': form,
        'job_type': job_type,
    }
    
    return render(request, 'core/staff/job_type_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def job_type_delete(request, type_id):
    """Delete a job type (Staff)"""
    try:
        job_type = JobType.objects.get(id=type_id)
    except (JobType.DoesNotExist, ValueError):
        try:
            job_type = JobType.objects.get(pk=type_id)
        except JobType.DoesNotExist:
            raise Http404("Job type not found")
    
    name = job_type.name
    job_type.delete()
    
    messages.success(request, f'Job type "{name}" deleted successfully!')
    return redirect('core:job_types_manage')


@login_required
@user_passes_test(is_staff_user)
def job_applications_manage(request):
    """Manage job applications (Staff)"""
    applications = JobApplication.objects.all().select_related('job')
    
    # Filter by job
    job_id = request.GET.get('job')
    selected_job = None
    if job_id:
        selected_job = get_object_or_404(JobPosting, id=job_id)
        applications = applications.filter(job=selected_job)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        applications = applications.filter(
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(applications, 20)
    
    try:
        applications_page = paginator.page(page)
    except:
        applications_page = paginator.page(1)
    
    stats = {
        'total': JobApplication.objects.count(),
        'pending': JobApplication.objects.filter(status='pending').count(),
        'shortlisted': JobApplication.objects.filter(status='shortlisted').count(),
        'hired': JobApplication.objects.filter(status='hired').count(),
    }
    
    # Get all jobs for filter dropdown
    jobs = JobPosting.objects.filter(status='published').order_by('-created_at')
    
    context = {
        'applications': applications_page,
        'stats': stats,
        'jobs': jobs,
        'selected_job': selected_job,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/staff/job_applications.html', context)


@login_required
@user_passes_test(is_staff_user)
def job_application_detail(request, application_id):
    """View job application details (Staff)"""
    application = get_object_or_404(JobApplication.objects.select_related('job'), id=application_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        rating = request.POST.get('rating')
        
        if status:
            application.status = status
        if notes:
            application.notes = notes
        if rating:
            application.rating = int(rating)
        
        application.updated_by = request.user
        application.save()
        
        messages.success(request, 'Application updated successfully!')
        return redirect('core:job_application_detail', application_id=application.id)
    
    context = {
        'application': application,
    }
    
    return render(request, 'core/staff/job_application_detail.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def job_application_status_update(request, application_id):
    """Update application status via AJAX"""
    application = get_object_or_404(JobApplication, id=application_id)
    data = json.loads(request.body)
    
    application.status = data.get('status', application.status)
    application.updated_by = request.user
    application.save()
    
    return JsonResponse({'success': True})






# Add to your views.py
import os
import hashlib
from .models import PublicDocument, DocumentCategory, DocumentAccessLog
from .forms import PublicDocumentForm, DocumentCategoryForm


# ==================== PUBLIC/USER DOCUMENT VIEWS ====================

@login_required
def digital_documents(request):
    """User's digital documents page"""
    # Get user's documents
    documents = PublicDocument.get_user_documents(request.user)
    
    # Filter by type
    doc_type = request.GET.get('type')
    if doc_type:
        documents = documents.filter(document_type=doc_type)
    
    # Filter by category
    category_id = request.GET.get('category')
    selected_category = None
    if category_id:
        selected_category = get_object_or_404(DocumentCategory, id=category_id, is_active=True)
        documents = documents.filter(category=selected_category)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        documents = documents.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(document_number__icontains=search_query) |
            Q(tags__icontains=search_query)
        ).distinct()
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(documents, 12)
    
    try:
        documents_page = paginator.page(page)
    except:
        documents_page = paginator.page(1)
    
    # Get stats
    stats = PublicDocument.get_document_stats(request.user)
    
    # Get categories
    categories = DocumentCategory.objects.filter(is_active=True).annotate(
        doc_count=Count('public_documents', filter=Q(
            public_documents__user=request.user,
            public_documents__is_active=True,
            public_documents__is_public=True,
            public_documents__status='published'
        ))
    ).filter(doc_count__gt=0)
    
    context = {
        'documents': documents_page,
        'stats': stats,
        'categories': categories,
        'selected_category': selected_category,
        'doc_type': doc_type,
        'search_query': search_query,
        'total_documents': paginator.count,
        'document_types': PublicDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'core/customer/digital_documents.html', context)


@login_required
def public_document_detail(request, slug):
    """Public document detail page"""
    document = get_object_or_404(
        PublicDocument.objects.select_related('user', 'policy', 'category'),
        slug=slug,
        is_active=True,
        is_public=True,
        status='published'
    )
    
    # Check if user has access
    if document.user and document.user != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this document.')
        return redirect('core:digital_documents')
    
    # Increment view count
    document.increment_views()
    
    # Log access
    DocumentAccessLog.objects.create(
        document=document,
        user=request.user,
        action='view',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
    )
    
    # Get related documents
    related_documents = PublicDocument.objects.filter(
        user=document.user,
        is_active=True,
        is_public=True,
        status='published'
    ).exclude(id=document.id)[:5]
    
    context = {
        'document': document,
        'related_documents': related_documents,
    }
    
    return render(request, 'core/customer/document_detail.html', context)


@login_required
def public_document_download(request, slug):
    """Download a public document"""
    document = get_object_or_404(
        PublicDocument,
        slug=slug,
        is_active=True,
        is_public=True,
        status='published'
    )
    
    # Check if user has access
    if document.user and document.user != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to download this document.')
        return redirect('core:digital_documents')
    
    # Increment download count
    document.increment_downloads()
    
    # Log access
    DocumentAccessLog.objects.create(
        document=document,
        user=request.user,
        action='download',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
    )
    
    # Serve file
    response = HttpResponse(document.document_file, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(document.document_file.name)}"'
    return response


@login_required
def public_document_verify(request, slug):
    """Verify document authenticity"""
    document = get_object_or_404(PublicDocument, slug=slug)
    
    verification_data = {
        'document_number': document.document_number,
        'title': document.title,
        'issue_date': document.issue_date.strftime('%Y-%m-%d') if document.issue_date else None,
        'verification_hash': document.verification_hash[:16] if document.verification_hash else None,
        'is_verified': document.is_verified,
        'verified_at': document.verified_at.strftime('%Y-%m-%d %H:%M') if document.verified_at else None,
    }
    
    return JsonResponse(verification_data)


# ==================== STAFF DOCUMENT MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_staff_user)
def documents_manage(request):
    """Staff document management dashboard"""
    documents = PublicDocument.objects.all().select_related('user', 'category', 'policy')
    
    # Filter by type
    doc_type = request.GET.get('type')
    if doc_type:
        documents = documents.filter(document_type=doc_type)
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        documents = documents.filter(status=status_filter)
    
    # Filter by user
    user_id = request.GET.get('user')
    selected_user = None
    if user_id:
        selected_user = get_object_or_404(User, id=user_id)
        documents = documents.filter(user=selected_user)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        documents = documents.filter(
            Q(title__icontains=search_query) |
            Q(document_number__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(documents, 20)
    
    try:
        documents_page = paginator.page(page)
    except:
        documents_page = paginator.page(1)
    
    stats = {
        'total': PublicDocument.objects.count(),
        'published': PublicDocument.objects.filter(status='published').count(),
        'draft': PublicDocument.objects.filter(status='draft').count(),
        'certificates': PublicDocument.objects.filter(document_type='certificate').count(),
        'policies': PublicDocument.objects.filter(document_type='policy').count(),
        'receipts': PublicDocument.objects.filter(document_type='receipt').count(),
        'total_downloads': PublicDocument.objects.aggregate(total=Sum('download_count'))['total'] or 0,
    }
    
    # Get users for filter
    users = User.objects.filter(public_documents__isnull=False).distinct()
    
    context = {
        'documents': documents_page,
        'stats': stats,
        'users': users,
        'selected_user': selected_user,
        'doc_type': doc_type,
        'status_filter': status_filter,
        'search_query': search_query,
        'document_types': PublicDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'core/staff/documents_manage.html', context)


@login_required
@user_passes_test(is_staff_user)
def document_create(request):
    """Create a new public document (Staff)"""
    if request.method == 'POST':
        form = PublicDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.created_by = request.user
            document.save()
            
            messages.success(request, f'Document "{document.title}" created successfully!')
            return redirect('core:documents_manage')
    else:
        form = PublicDocumentForm()
    
    context = {
        'form': form,
        'title': 'Upload New Document',
        'submit_text': 'Upload Document',
    }
    
    return render(request, 'core/staff/document_form.html', context)


@login_required
@user_passes_test(is_staff_user)
def document_edit(request, document_id):
    """Edit a public document (Staff)"""
    document = get_object_or_404(PublicDocument, id=document_id)
    
    if request.method == 'POST':
        form = PublicDocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            document = form.save(commit=False)
            document.updated_by = request.user
            document.save()
            
            messages.success(request, f'Document "{document.title}" updated successfully!')
            return redirect('core:documents_manage')
    else:
        form = PublicDocumentForm(instance=document)
    
    context = {
        'form': form,
        'document': document,
        'title': f'Edit: {document.title}',
        'submit_text': 'Update Document',
    }
    
    return render(request, 'core/staff/document_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def document_delete(request, document_id):
    """Delete a public document (Staff)"""
    document = get_object_or_404(PublicDocument, id=document_id)
    title = document.title
    document.delete()
    
    messages.success(request, f'Document "{title}" deleted successfully!')
    return redirect('core:documents_manage')


@login_required
@user_passes_test(is_staff_user)
def document_verify_toggle(request, document_id):
    """Toggle document verification status"""
    document = get_object_or_404(PublicDocument, id=document_id)
    document.is_verified = not document.is_verified
    if document.is_verified:
        document.verified_by = request.user
        document.verified_at = timezone.now()
    document.save()
    
    return JsonResponse({
        'success': True,
        'is_verified': document.is_verified
    })


@login_required
@user_passes_test(is_staff_user)
def document_categories_manage(request):
    """Manage document categories (Staff)"""
    categories = DocumentCategory.objects.all().annotate(doc_count=Count('public_documents'))
    
    if request.method == 'POST':
        form = DocumentCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('core:document_categories_manage')
    else:
        form = DocumentCategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'core/staff/document_categories.html', context)


# In views.py - Update document category views

@login_required
@user_passes_test(is_staff_user)
def document_category_edit(request, category_id):
    """Edit a document category (Staff)"""
    category = get_object_or_404(DocumentCategory, pk=category_id)
    
    if request.method == 'POST':
        form = DocumentCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('core:document_categories_manage')
    else:
        form = DocumentCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
    }
    
    return render(request, 'core/staff/document_category_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def document_category_delete(request, category_id):
    """Delete a document category (Staff)"""
    category = get_object_or_404(DocumentCategory, pk=category_id)
    name = category.name
    category.delete()
    
    messages.success(request, f'Category "{name}" deleted successfully!')
    return redirect('core:document_categories_manage')


@login_required
@user_passes_test(is_staff_user)
def document_bulk_upload(request):
    """Bulk upload public documents (Staff)"""
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        user_id = request.POST.get('user')
        document_type = request.POST.get('document_type')
        category_id = request.POST.get('category')
        
        user = get_object_or_404(User, id=user_id) if user_id else None
        category = get_object_or_404(DocumentCategory, id=category_id) if category_id else None
        
        uploaded_count = 0
        for file in files:
            document = PublicDocument.objects.create(
                title=file.name,
                user=user,
                document_type=document_type,
                category=category,
                document_file=file,
                created_by=request.user,
                status='published',
                is_public=True
            )
            uploaded_count += 1
        
        messages.success(request, f'{uploaded_count} document(s) uploaded successfully!')
        return redirect('core:documents_manage')
    
    users = User.objects.filter(is_active=True)
    categories = DocumentCategory.objects.filter(is_active=True)
    
    context = {
        'users': users,
        'categories': categories,
        'document_types': PublicDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'core/staff/document_bulk_upload.html', context)










# Add to your views.py

from .models import ContactInquiry, OfficeLocation
from .forms import ContactInquiryForm, OfficeLocationForm
from .Utils.email_utils import send_contact_confirmation_email, send_staff_notification_email
import time


def contact(request):
    """Contact page with dynamic office locations and protected form"""
    
    # Get active office locations
    offices = OfficeLocation.objects.filter(is_active=True).order_by('-is_headquarters', 'order', 'city')
    
    # Get headquarters for map
    headquarters = offices.filter(is_headquarters=True).first() or offices.first()
    
    if request.method == 'POST':
        form = ContactInquiryForm(request.POST)
        
        # Rate limiting check (prevent multiple submissions from same IP)
        client_ip = get_client_ip(request)
        recent_inquiries = ContactInquiry.objects.filter(
            ip_address=client_ip,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        
        if recent_inquiries >= 3:
            messages.warning(request, 'Too many inquiries. Please wait a few minutes before trying again.')
            return redirect('core:contact')
        
        if form.is_valid():
            inquiry = form.save(commit=False)
            
            # Set tracking information
            inquiry.ip_address = client_ip
            inquiry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            
            # Auto-generate subject if not provided
            if not inquiry.subject:
                inquiry.subject = f"{inquiry.get_inquiry_type_display()} - {inquiry.full_name}"
            
            # Set user if authenticated
            if request.user.is_authenticated:
                inquiry.user = request.user
            
            # Set spam score and suspicious flag
            inquiry.spam_score = getattr(form, 'spam_score', 0)
            inquiry.is_suspicious = getattr(form, 'is_suspicious', False)
            
            # If suspicious, mark for review but still save
            if inquiry.is_suspicious:
                inquiry.status = 'pending'
                inquiry.priority = 'low'
            
            inquiry.save()
            
            # Send confirmation email to user (only if not suspicious)
            if not inquiry.is_suspicious:
                try:
                    send_contact_confirmation_email(inquiry)
                except Exception as e:
                    print(f"Failed to send confirmation email: {e}")
            
            # Send notification to staff (always notify, but flag suspicious ones)
            try:
                send_staff_notification_email(inquiry)
            except Exception as e:
                print(f"Failed to send staff notification: {e}")
            
            # Success message
            messages.success(
                request, 
                f'Thank you for contacting us, {inquiry.full_name}! Your inquiry (#{inquiry.inquiry_number}) has been received. We will respond within 2 business hours.'
            )
            
            # Log activity if user is authenticated
            if request.user.is_authenticated:
                log_user_activity(request.user, 'contact_inquiry', request, {
                    'inquiry_id': str(inquiry.id),
                    'inquiry_number': inquiry.inquiry_number
                })
            
            return redirect('core:contact')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Set initial timestamp for honeypot
        initial_data = {'timestamp': int(time.time() * 1000)}
        form = ContactInquiryForm(initial=initial_data)
    
    context = {
        'form': form,
        'offices': offices,
        'headquarters': headquarters,
        'total_offices': offices.count(),
        'page_title': 'Contact Us',
    }
    
    return render(request, 'core/contact.html', context)


# ==================== STAFF INQUIRY MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_staff_user)
def inquiries_manage(request):
    """Staff inquiry management dashboard"""
    inquiries = ContactInquiry.objects.all()
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        inquiries = inquiries.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.GET.get('type', '')
    if type_filter:
        inquiries = inquiries.filter(inquiry_type=type_filter)
    
    # Filter by priority
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        inquiries = inquiries.filter(priority=priority_filter)
    
    # Show suspicious only
    suspicious_only = request.GET.get('suspicious') == 'true'
    if suspicious_only:
        inquiries = inquiries.filter(is_suspicious=True)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        inquiries = inquiries.filter(
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(inquiry_number__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(inquiries, 20)
    
    try:
        inquiries_page = paginator.page(page)
    except:
        inquiries_page = paginator.page(1)
    
    stats = {
        'total': ContactInquiry.objects.count(),
        'pending': ContactInquiry.objects.filter(status='pending').count(),
        'in_progress': ContactInquiry.objects.filter(status='in_progress').count(),
        'resolved': ContactInquiry.objects.filter(status='resolved').count(),
        'suspicious': ContactInquiry.objects.filter(is_suspicious=True).count(),
        'urgent': ContactInquiry.objects.filter(priority='urgent').count(),
    }
    
    context = {
        'inquiries': inquiries_page,
        'stats': stats,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'priority_filter': priority_filter,
        'suspicious_only': suspicious_only,
        'search_query': search_query,
        'inquiry_types': ContactInquiry.INQUIRY_TYPE_CHOICES,
        'status_choices': ContactInquiry.STATUS_CHOICES,
        'priority_choices': ContactInquiry.PRIORITY_CHOICES,
    }
    
    return render(request, 'core/staff/inquiries_manage.html', context)


@login_required
@user_passes_test(is_staff_user)
def inquiry_detail(request, inquiry_id):
    """View inquiry details and respond"""
    inquiry = get_object_or_404(ContactInquiry, id=inquiry_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_status':
            inquiry.status = request.POST.get('status')
            inquiry.priority = request.POST.get('priority')
            inquiry.internal_notes = request.POST.get('internal_notes', '')
            inquiry.save()
            messages.success(request, 'Inquiry updated successfully!')
            
        elif action == 'send_response':
            response_text = request.POST.get('response')
            send_email = request.POST.get('send_email') == 'true'
            
            inquiry.response = response_text
            inquiry.responded_by = request.user
            inquiry.responded_at = timezone.now()
            inquiry.status = 'resolved'
            inquiry.save()
            
            if send_email and response_text:
                # Send response email
                subject = f"Re: Your Inquiry #{inquiry.inquiry_number} - VehicleInsure"
                html_content = render_to_string('core/emails/inquiry_response.html', {
                    'inquiry': inquiry,
                    'response': response_text,
                })
                
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=strip_tags(html_content),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[inquiry.email],
                )
                email.attach_alternative(html_content, "text/html")
                email.send(fail_silently=True)
            
            messages.success(request, 'Response sent successfully!')
        
        elif action == 'mark_spam':
            inquiry.status = 'spam'
            inquiry.is_suspicious = True
            inquiry.save()
            messages.success(request, 'Inquiry marked as spam!')
        
        return redirect('core:inquiry_detail', inquiry_id=inquiry.id)
    
    context = {
        'inquiry': inquiry,
    }
    
    return render(request, 'core/staff/inquiry_detail.html', context)


@login_required
@user_passes_test(is_staff_user)
def offices_manage(request):
    """Manage office locations (Staff)"""
    offices = OfficeLocation.objects.all()
    
    if request.method == 'POST':
        form = OfficeLocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Office location added successfully!')
            return redirect('core:offices_manage')
    else:
        form = OfficeLocationForm()
    
    context = {
        'offices': offices,
        'form': form,
    }
    
    return render(request, 'core/staff/offices_manage.html', context)


@login_required
@user_passes_test(is_staff_user)
def office_edit(request, office_id):
    """Edit office location (Staff)"""
    office = get_object_or_404(OfficeLocation, id=office_id)
    
    if request.method == 'POST':
        form = OfficeLocationForm(request.POST, instance=office)
        if form.is_valid():
            form.save()
            messages.success(request, 'Office location updated successfully!')
            return redirect('core:offices_manage')
    else:
        form = OfficeLocationForm(instance=office)
    
    context = {
        'form': form,
        'office': office,
    }
    
    return render(request, 'core/staff/office_form.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def office_delete(request, office_id):
    """Delete office location (Staff)"""
    office = get_object_or_404(OfficeLocation, id=office_id)
    name = office.name
    office.delete()
    
    messages.success(request, f'Office "{name}" deleted successfully!')
    return redirect('core:offices_manage')







# Add to your views.py

from django.shortcuts import render


def handler404(request, exception=None):
    """Custom 404 error page"""
    context = {
        'error_code': '404',
        'error_title': 'Page Not Found',
        'error_message': 'The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.',
    }
    return render(request, 'core/errors/404.html', context, status=404)


def handler500(request):
    """Custom 500 error page"""
    context = {
        'error_code': '500',
        'error_title': 'Server Error',
        'error_message': 'Something went wrong on our end. Our team has been notified and we are working to fix the issue.',
    }
    return render(request, 'core/errors/500.html', context, status=500)


def handler403(request, exception=None):
    """Custom 403 error page"""
    context = {
        'error_code': '403',
        'error_title': 'Access Denied',
        'error_message': 'You do not have permission to access this page. Please contact support if you believe this is an error.',
    }
    return render(request, 'core/errors/403.html', context, status=403)


def handler400(request, exception=None):
    """Custom 400 error page"""
    context = {
        'error_code': '400',
        'error_title': 'Bad Request',
        'error_message': 'The request could not be understood by the server. Please check your input and try again.',
    }
    return render(request, 'core/errors/400.html', context, status=400)