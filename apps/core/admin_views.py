from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models.functions import TruncMonth, TruncDay
from datetime import datetime, timedelta
import json
import csv
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

from apps.core.models import (
    User, Vehicle, InsurancePolicy, Claim, Payment, 
    InsuranceQuote, Notification, Document, SupportTicket, 
    PromoCode, UserActivityLog
)

from .forms import (
    AdminUserForm, AdminPolicyForm, AdminClaimForm, 
    PromoCodeForm, AdminNotificationForm
)
from .decorators import admin_required
from .utils import export_to_excel, generate_report

import logging

logger = logging.getLogger(__name__)



@admin_required
def admin_dashboard(request):
    """Admin dashboard view"""
    # Get statistics
    total_users = User.objects.count()
    verified_users = User.objects.filter(is_verified=True).count()
    kyc_pending = User.objects.filter(kyc_documents_submitted=True, is_kyc_completed=False).count()
    
    total_policies = InsurancePolicy.objects.count()
    active_policies = InsurancePolicy.objects.filter(status='active').count()
    expiring_policies = InsurancePolicy.objects.filter(
        status='active',
        end_date__lte=timezone.now().date() + timezone.timedelta(days=30)
    ).count()
    
    total_claims = Claim.objects.count()
    pending_claims = Claim.objects.filter(status__in=['pending', 'under_review']).count()
    approved_claims = Claim.objects.filter(status='approved').count()
    settled_claims = Claim.objects.filter(status='settled').count()
    
    total_revenue = Payment.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    pending_payments = Payment.objects.filter(status__in=['pending', 'pending_verification']).count()
    
    total_vehicles = Vehicle.objects.count()
    insured_vehicles = Vehicle.objects.filter(is_insured=True).count()
    
    # Support tickets statistics - FIXED
    open_tickets = SupportTicket.objects.filter(status__in=['open', 'in_progress']).count()
    total_tickets = SupportTicket.objects.count()
    unassigned_tickets = SupportTicket.objects.filter(assigned_to__isnull=True).count()
    
    # Recent activities
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_policies = InsurancePolicy.objects.select_related('user').order_by('-created_at')[:5]
    recent_claims = Claim.objects.select_related('user').order_by('-created_at')[:5]
    recent_payments = Payment.objects.filter(status='completed').select_related('user').order_by('-paid_at')[:5]
    recent_tickets = SupportTicket.objects.select_related('user').order_by('-created_at')[:5]
    
    # Monthly revenue chart data (last 6 months)
    months = []
    revenues = []
    
    for i in range(5, -1, -1):
        month_date = timezone.now().date() - timezone.timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = timezone.now().date()
        else:
            month_end = (month_start + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)
        
        month_revenue = Payment.objects.filter(
            status='completed',
            paid_at__date__gte=month_start,
            paid_at__date__lte=month_end
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        months.append(month_start.strftime('%b %Y'))
        revenues.append(float(month_revenue))
    
    # Policy distribution by type
    policy_by_type = InsurancePolicy.objects.values('policy_type').annotate(
        count=Count('id')
    )
    
    policy_types = [item['policy_type'].replace('_', ' ').title() for item in policy_by_type]
    policy_counts = [item['count'] for item in policy_by_type]
    
    # Claim status distribution
    claim_by_status = Claim.objects.values('status').annotate(
        count=Count('id')
    )
    
    status_display = {
        'pending': 'Pending',
        'under_review': 'Under Review',
        'approved': 'Approved',
        'rejected': 'Rejected',
        'settled': 'Settled',
        'withdrawn': 'Withdrawn'
    }
    claim_statuses = [status_display.get(item['status'], item['status'].title()) for item in claim_by_status]
    claim_counts = [item['count'] for item in claim_by_status]
    
    # User growth chart (last 6 months)
    user_growth_labels = []
    user_growth_data = []
    for i in range(5, -1, -1):
        month_date = timezone.now().date() - timezone.timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = timezone.now().date()
        else:
            month_end = (month_start + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)
        
        month_users = User.objects.filter(
            date_joined__date__gte=month_start,
            date_joined__date__lte=month_end
        ).count()
        
        user_growth_labels.append(month_start.strftime('%b'))
        user_growth_data.append(month_users)
    
    context = {
        'total_users': total_users,
        'verified_users': verified_users,
        'kyc_pending': kyc_pending,
        'total_policies': total_policies,
        'active_policies': active_policies,
        'expiring_policies': expiring_policies,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'approved_claims': approved_claims,
        'settled_claims': settled_claims,
        'total_revenue': total_revenue,
        'pending_payments': pending_payments,
        'total_vehicles': total_vehicles,
        'insured_vehicles': insured_vehicles,
        'open_tickets': open_tickets,
        'total_tickets': total_tickets,
        'unassigned_tickets': unassigned_tickets,
        'recent_users': recent_users,
        'recent_policies': recent_policies,
        'recent_claims': recent_claims,
        'recent_payments': recent_payments,
        'recent_tickets': recent_tickets,
        'months': json.dumps(months),
        'revenues': json.dumps(revenues),
        'policy_types': json.dumps(policy_types),
        'policy_counts': json.dumps(policy_counts),
        'claim_statuses': json.dumps(claim_statuses),
        'claim_counts': json.dumps(claim_counts),
        'user_growth_labels': json.dumps(user_growth_labels),
        'user_growth_data': json.dumps(user_growth_data),
    }
    
    return render(request, 'core/admin/dashboard.html', context)

@admin_required
def admin_users(request):
    """Manage users view"""
    users_list = User.objects.all().order_by('-date_joined')
    
    # Calculate statistics
    total_users = users_list.count()
    verified_count = users_list.filter(is_verified=True).count()
    kyc_completed_count = users_list.filter(is_kyc_completed=True).count()
    active_count = users_list.filter(is_active=True).count()
    
    # Filter by role
    role = request.GET.get('role')
    role_filter = role
    if role:
        users_list = users_list.filter(role=role)
    
    # Filter by verification status
    is_verified = request.GET.get('is_verified')
    verified_filter = is_verified
    if is_verified:
        users_list = users_list.filter(is_verified=is_verified == 'true')
    
    # Filter by KYC status
    kyc_completed = request.GET.get('kyc_completed')
    kyc_filter = kyc_completed
    if kyc_completed:
        users_list = users_list.filter(is_kyc_completed=kyc_completed == 'true')
    
    # Filter by active status
    is_active = request.GET.get('is_active')
    active_filter = is_active
    if is_active:
        users_list = users_list.filter(is_active=is_active == 'true')
    
    # Search
    search = request.GET.get('search')
    if search:
        users_list = users_list.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone_number__icontains=search)
        )
    
    paginator = Paginator(users_list, 20)
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    context = {
        'users': users,
        'total_users': total_users,
        'verified_count': verified_count,
        'kyc_completed_count': kyc_completed_count,
        'active_count': active_count,
        'role_filter': role_filter,
        'verified_filter': verified_filter,
        'kyc_filter': kyc_filter,
        'active_filter': active_filter,
        'search_query': search,
    }
    
    return render(request, 'core/admin/users.html', context)

@admin_required
def admin_user_detail(request, user_id):
    """View user details"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = AdminUserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.email} updated successfully!')
            return redirect('core:admin_user_detail', user_id=user.id)
    else:
        form = AdminUserForm(instance=user)
    
    policies = user.policies.all()
    claims = user.claims.all()
    payments = user.payments.all()
    activities = user.activities.all()[:50]
    documents = user.documents.all()
    
    return render(request, 'core/admin/user_detail.html', {
        'user': user,
        'form': form,
        'policies': policies,
        'claims': claims,
        'payments': payments,
        'activities': activities,
        'documents': documents
    })

@admin_required
def admin_verify_user(request, user_id):
    """Verify user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.is_verified = True
        user.is_kyc_completed = True
        user.save()
        
        # Send notification
        Notification.objects.create(
            user=user,
            title='Account Verified',
            message='Your account has been verified successfully!',
            notification_type='system_alert'
        )
        
        messages.success(request, f'User {user.email} verified successfully!')
    
    return redirect('core:admin_user_detail', user_id=user.id)

@admin_required
def admin_suspend_user(request, user_id):
    """Suspend user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.is_active = False
        user.save()
        messages.success(request, f'User {user.email} suspended successfully!')
    
    return redirect('core:admin_user_detail', user_id=user.id)

@admin_required
def admin_activate_user(request, user_id):
    """Activate user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.is_active = True
        user.save()
        messages.success(request, f'User {user.email} activated successfully!')
    
    return redirect('core:admin_user_detail', user_id=user.id)


@admin_required
@require_http_methods(["POST"])
def admin_verify_document(request, doc_id):
    """Verify a single document"""
    document = get_object_or_404(Document, id=doc_id)
    
    try:
        document.is_verified = True
        document.verified_by = request.user
        document.verified_at = timezone.now()
        document.save()
        
        # Log activity
        log_user_activity(request.user, 'verify_document', request, {
            'document_id': str(document.id),
            'user_id': str(document.user.id)
        })
        
        return JsonResponse({'success': True, 'message': 'Document verified successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    

@admin_required
def admin_policies(request):
    """Manage policies view"""
    policies_list = InsurancePolicy.objects.select_related('user', 'vehicle').all().order_by('-created_at')
    
    # Calculate statistics
    total_policies = policies_list.count()
    active_count = policies_list.filter(status='active').count()
    total_premium = policies_list.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0
    
    # Count expiring soon (within 30 days)
    from datetime import timedelta
    expiring_count = policies_list.filter(
        status='active',
        end_date__lte=timezone.now().date() + timedelta(days=30),
        end_date__gte=timezone.now().date()
    ).count()
    
    # Filter by status
    status = request.GET.get('status')
    status_filter = status
    if status:
        policies_list = policies_list.filter(status=status)
    
    # Filter by policy type
    policy_type = request.GET.get('policy_type')
    type_filter = policy_type
    if policy_type:
        policies_list = policies_list.filter(policy_type=policy_type)
    
    # Filter by date
    date = request.GET.get('date')
    date_filter = date
    if date:
        policies_list = policies_list.filter(created_at__date=date)
    
    # Search
    search = request.GET.get('search')
    if search:
        policies_list = policies_list.filter(
            Q(policy_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(vehicle__registration_number__icontains=search)
        )
    
    paginator = Paginator(policies_list, 20)
    page = request.GET.get('page')
    policies = paginator.get_page(page)
    
    context = {
        'policies': policies,
        'total_policies': total_policies,
        'active_count': active_count,
        'total_premium': total_premium,
        'expiring_count': expiring_count,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'date_filter': date_filter,
        'search_query': search,
    }
    
    return render(request, 'core/admin/policies.html', context)

@admin_required
def admin_policy_detail(request, policy_id):
    """View policy details"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    if request.method == 'POST':
        form = AdminPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, f'Policy {policy.policy_number} updated successfully!')
            return redirect('core:admin_policy_detail', policy_id=policy.id)
    else:
        form = AdminPolicyForm(instance=policy)
    
    payments = policy.payments.all()
    claims = policy.claims.all()
    
    return render(request, 'core/admin/policy_detail.html', {
        'policy': policy,
        'form': form,
        'payments': payments,
        'claims': claims
    })

@admin_required
def admin_claims(request):
    """Manage claims view"""
    claims_list = Claim.objects.select_related('user', 'policy').all().order_by('-created_at')
    
    # Calculate summary stats
    total_claims = claims_list.count()
    pending_claims = claims_list.filter(status='pending').count()
    under_review_claims = claims_list.filter(status='under_review').count()
    approved_claims = claims_list.filter(status='approved').count()
    total_claimed = claims_list.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
    total_approved = claims_list.filter(status='approved').aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0
    
    # Filter by status
    status = request.GET.get('status')
    status_filter = status
    if status:
        claims_list = claims_list.filter(status=status)
    
    # Filter by claim type
    claim_type = request.GET.get('claim_type')
    type_filter = claim_type
    if claim_type:
        claims_list = claims_list.filter(claim_type=claim_type)
    
    # Search
    search = request.GET.get('search')
    if search:
        claims_list = claims_list.filter(
            Q(claim_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(policy__policy_number__icontains=search)
        )
    
    paginator = Paginator(claims_list, 20)
    page = request.GET.get('page')
    claims = paginator.get_page(page)
    
    context = {
        'claims': claims,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'under_review_claims': under_review_claims,
        'approved_claims': approved_claims,
        'total_claimed': total_claimed,
        'total_approved': total_approved,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    
    return render(request, 'core/admin/claims.html', context)


@admin_required
def admin_claim_detail(request, claim_id):
    """View claim details and process"""
    claim = get_object_or_404(Claim.objects.select_related('user', 'policy', 'policy__vehicle'), id=claim_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Create form instance with POST data
        form = AdminClaimForm(request.POST, request.FILES, instance=claim)
        
        if action in ['approve', 'reject', 'settle', 'review']:
            # For these actions, we need to validate the form
            if action == 'approve':
                if not form.data.get('approved_amount'):
                    messages.error(request, 'Please enter an approved amount.')
                    return redirect('core:admin_claim_detail', claim_id=claim.id)
            
            if action == 'reject':
                if not form.data.get('rejection_reason'):
                    messages.error(request, 'Please provide a rejection reason.')
                    return redirect('core:admin_claim_detail', claim_id=claim.id)
            
            # Process the action
            if action == 'review':
                claim.status = 'under_review'
                claim.surveyor_notes = request.POST.get('surveyor_notes', '')
                
                if request.FILES.get('surveyor_report'):
                    claim.surveyor_report = request.FILES['surveyor_report']
                
                claim.save()
                messages.success(request, f'Claim {claim.claim_number} marked as under review')
                
            elif action == 'approve':
                claim.status = 'approved'
                claim.approved_amount = Decimal(request.POST.get('approved_amount', claim.claimed_amount))
                claim.approved_by = request.user
                claim.approval_date = timezone.now()
                claim.surveyor_notes = request.POST.get('surveyor_notes', '')
                
                if request.FILES.get('surveyor_report'):
                    claim.surveyor_report = request.FILES['surveyor_report']
                
                claim.save()
                
                # Send notification
                Notification.objects.create(
                    user=claim.user,
                    title='Claim Approved',
                    message=f'Your claim #{claim.claim_number} has been approved for ₦{claim.approved_amount:,.2f}',
                    notification_type='claim_update',
                    data={'claim_id': str(claim.id)}
                )
                
                messages.success(request, f'Claim {claim.claim_number} approved for ₦{claim.approved_amount:,.2f}!')
                
            elif action == 'reject':
                claim.status = 'rejected'
                claim.rejection_reason = request.POST.get('rejection_reason', '')
                claim.surveyor_notes = request.POST.get('surveyor_notes', '')
                claim.save()
                
                Notification.objects.create(
                    user=claim.user,
                    title='Claim Rejected',
                    message=f'Your claim #{claim.claim_number} has been rejected. Reason: {claim.rejection_reason}',
                    notification_type='claim_update',
                    data={'claim_id': str(claim.id)}
                )
                
                messages.warning(request, f'Claim {claim.claim_number} rejected!')
                
            elif action == 'settle':
                claim.status = 'settled'
                claim.settlement_date = timezone.now()
                claim.save()
                
                Notification.objects.create(
                    user=claim.user,
                    title='Claim Settled',
                    message=f'Your claim #{claim.claim_number} has been settled for ₦{claim.approved_amount or claim.claimed_amount:,.2f}',
                    notification_type='claim_update',
                    data={'claim_id': str(claim.id)}
                )
                
                messages.success(request, f'Claim {claim.claim_number} settled!')
            
            # Log activity
            log_user_activity(request.user, f'claim_{action}', request, {
                'claim_id': str(claim.id),
                'claim_number': claim.claim_number
            })
            
            return redirect('core:admin_claim_detail', claim_id=claim.id)
        else:
            messages.error(request, 'Invalid action.')
            return redirect('core:admin_claim_detail', claim_id=claim.id)
    else:
        form = AdminClaimForm(instance=claim)
    
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
    
    context = {
        'claim': claim,
        'form': form,
        'documents': documents,
        'photos': photos,
    }
    
    return render(request, 'core/admin/claim_detail.html', context)





from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json

from apps.core.models import Payment, InsurancePolicy, Notification, User
from apps.core.decorators import admin_required
from .Utils.utils import log_user_activity

@admin_required
def admin_payments(request):
    """Manage payments view"""
    payments_list = Payment.objects.select_related('user', 'policy').all().order_by('-created_at')
    
    # Calculate summary statistics
    total_payments = payments_list.count()
    total_revenue = payments_list.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    completed_count = payments_list.filter(status='completed').count()
    pending_count = payments_list.filter(status__in=['pending', 'pending_verification']).count()
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        payments_list = payments_list.filter(status=status)
    
    # Filter by payment method
    method = request.GET.get('method')
    if method:
        payments_list = payments_list.filter(payment_method=method)
    
    # Filter by date
    date = request.GET.get('date')
    if date:
        payments_list = payments_list.filter(created_at__date=date)
    
    # Search
    search = request.GET.get('search')
    if search:
        payments_list = payments_list.filter(
            Q(transaction_id__icontains=search) |
            Q(payment_reference__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    paginator = Paginator(payments_list, 20)
    page = request.GET.get('page')
    payments = paginator.get_page(page)
    
    context = {
        'payments': payments,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'status_filter': status,
        'method_filter': method,
        'date_filter': date,
        'search_query': search,
    }
    
    return render(request, 'core/admin/payments.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_payment_action(request, payment_id):
    """Handle payment actions: mark completed, failed, verify transfer, refund"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Determine action from URL path
    path = request.path
    action = None
    
    if 'mark-completed' in path:
        action = 'mark_completed'
    elif 'verify-transfer' in path:
        action = 'verify_transfer'
    elif 'mark-failed' in path:
        action = 'mark_failed'
    elif 'refund' in path:
        action = 'refund'
    
    try:
        if action == 'mark_completed':
            payment.status = 'completed'
            payment.paid_at = timezone.now()
            payment.verified_by = request.user
            payment.verified_at = timezone.now()
            payment.save()
            
            # Update policy status
            if payment.policy and payment.policy.status == 'pending':
                payment.policy.status = 'active'
                payment.policy.save()
            
            # Send notification to user
            Notification.objects.create(
                user=payment.user,
                title='Payment Confirmed',
                message=f'Your payment of ₦{payment.amount:,.2f} for policy #{payment.policy.policy_number} has been confirmed.',
                notification_type='payment_confirmation',
                data={'payment_id': str(payment.id), 'policy_id': str(payment.policy.id)}
            )
            
            log_user_activity(request.user, 'mark_payment_completed', request, {
                'payment_id': str(payment.id),
                'amount': str(payment.amount)
            })
            
            return JsonResponse({'success': True, 'message': 'Payment marked as completed'})
            
        elif action == 'verify_transfer':
            try:
                data = json.loads(request.body)
                notes = data.get('notes', '')
            except:
                notes = ''
            
            payment.status = 'completed'
            payment.paid_at = timezone.now()
            payment.verified_by = request.user
            payment.verified_at = timezone.now()
            
            # Update payment details
            if payment.payment_details:
                if isinstance(payment.payment_details, dict):
                    payment.payment_details['verified_notes'] = notes
                    payment.payment_details['verified_by'] = request.user.get_full_name()
                    payment.payment_details['verified_at'] = str(timezone.now())
            else:
                payment.payment_details = {
                    'verified_notes': notes,
                    'verified_by': request.user.get_full_name(),
                    'verified_at': str(timezone.now())
                }
            payment.save()
            
            # Update policy status
            if payment.policy and payment.policy.status == 'pending':
                payment.policy.status = 'active'
                payment.policy.save()
            
            # Send notification
            Notification.objects.create(
                user=payment.user,
                title='Bank Transfer Verified',
                message=f'Your bank transfer of ₦{payment.amount:,.2f} has been verified. Your policy is now active!',
                notification_type='payment_confirmation',
                data={'payment_id': str(payment.id), 'policy_id': str(payment.policy.id)}
            )
            
            log_user_activity(request.user, 'verify_bank_transfer', request, {
                'payment_id': str(payment.id)
            })
            
            return JsonResponse({'success': True, 'message': 'Bank transfer verified successfully'})
            
        elif action == 'mark_failed':
            try:
                data = json.loads(request.body)
                reason = data.get('reason', '')
            except:
                reason = ''
            
            payment.status = 'failed'
            payment.failure_reason = reason
            payment.save()
            
            # Send notification
            Notification.objects.create(
                user=payment.user,
                title='Payment Failed',
                message=f'Your payment of ₦{payment.amount:,.2f} could not be processed. Reason: {reason}',
                notification_type='payment_confirmation',
                data={'payment_id': str(payment.id)}
            )
            
            log_user_activity(request.user, 'mark_payment_failed', request, {
                'payment_id': str(payment.id),
                'reason': reason
            })
            
            return JsonResponse({'success': True, 'message': 'Payment marked as failed'})
            
        elif action == 'refund':
            payment.status = 'refunded'
            payment.refunded_at = timezone.now()
            payment.refunded_by = request.user
            payment.save()
            
            # Update policy status
            if payment.policy:
                payment.policy.status = 'cancelled'
                payment.policy.save()
            
            # Send notification
            Notification.objects.create(
                user=payment.user,
                title='Payment Refunded',
                message=f'Your payment of ₦{payment.amount:,.2f} has been refunded.',
                notification_type='payment_confirmation',
                data={'payment_id': str(payment.id)}
            )
            
            log_user_activity(request.user, 'refund_payment', request, {
                'payment_id': str(payment.id)
            })
            
            return JsonResponse({'success': True, 'message': 'Payment refunded successfully'})
            
        else:
            return JsonResponse({'success': False, 'message': f'Invalid action: {action}'}, status=400)
            
    except Exception as e:
        import traceback
        print(f"Payment Action Error: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@admin_required
def admin_payment_detail(request, payment_id):
    """View payment details"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'core/admin/payment_detail.html', context)




@admin_required
def admin_promo_codes(request):
    """Manage promo codes"""
    promo_codes = PromoCode.objects.all().order_by('-created_at')
    
    # Calculate statistics
    total_codes = promo_codes.count()
    active_count = promo_codes.filter(is_active=True, valid_from__lte=timezone.now(), 
                                      valid_to__gte=timezone.now()).count()
    total_used = promo_codes.aggregate(Sum('used_count'))['used_count__sum'] or 0
    expired_count = promo_codes.filter(valid_to__lt=timezone.now()).count()
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST)
        if form.is_valid():
            promo = form.save(commit=False)
            promo.created_by = request.user
            promo.code = promo.code.upper()
            promo.save()
            messages.success(request, f'Promo code {promo.code} created successfully!')
            return redirect('core:admin_promo_codes')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = PromoCodeForm()
    
    context = {
        'promo_codes': promo_codes,
        'form': form,
        'now': timezone.now(),
        'active_count': active_count,
        'total_used': total_used,
        'expired_count': expired_count,
    }
    
    return render(request, 'core/admin/promo_codes.html', context)


@admin_required
def admin_edit_promo_code(request, code_id):
    """Edit promo code"""
    promo = get_object_or_404(PromoCode, id=code_id)
    
    if request.method == 'POST':
        form = PromoCodeForm(request.POST, instance=promo)
        if form.is_valid():
            promo = form.save(commit=False)
            promo.code = promo.code.upper()
            promo.save()
            messages.success(request, f'Promo code {promo.code} updated successfully!')
            return redirect('core:admin_promo_codes')
    else:
        form = PromoCodeForm(instance=promo)
    
    return render(request, 'core/admin/edit_promo_code.html', {
        'form': form,
        'promo': promo
    })


@admin_required
@require_http_methods(["POST"])
def admin_toggle_promo_code(request, code_id):
    """Toggle promo code active status"""
    promo = get_object_or_404(PromoCode, id=code_id)
    promo.is_active = not promo.is_active
    promo.save()
    status = 'activated' if promo.is_active else 'deactivated'
    return JsonResponse({'success': True, 'message': f'Promo code {status}'})


@admin_required
def admin_delete_promo_code(request, code_id):
    """Delete promo code"""
    promo = get_object_or_404(PromoCode, id=code_id)
    
    if request.method == 'POST':
        code = promo.code
        promo.delete()
        messages.success(request, f'Promo code {code} deleted successfully!')
    
    return redirect('core:admin_promo_codes')



@admin_required
def admin_support_tickets(request):
    """Manage support tickets"""
    tickets_list = SupportTicket.objects.select_related('user', 'assigned_to').all().order_by('-created_at')
    
    # Calculate statistics
    total_tickets = tickets_list.count()
    open_count = tickets_list.filter(status='open').count()
    in_progress_count = tickets_list.filter(status='in_progress').count()
    resolved_count = tickets_list.filter(status='resolved').count()
    
    # Filter by status
    status = request.GET.get('status')
    status_filter = status
    if status:
        tickets_list = tickets_list.filter(status=status)
    
    # Filter by priority
    priority = request.GET.get('priority')
    priority_filter = priority
    if priority:
        tickets_list = tickets_list.filter(priority=priority)
    
    # Filter by assigned
    assigned = request.GET.get('assigned')
    if assigned == 'unassigned':
        tickets_list = tickets_list.filter(assigned_to__isnull=True)
    elif assigned == 'me':
        tickets_list = tickets_list.filter(assigned_to=request.user)
    elif assigned:
        tickets_list = tickets_list.filter(assigned_to_id=assigned)
    
    # Search
    search = request.GET.get('search')
    if search:
        tickets_list = tickets_list.filter(
            Q(ticket_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(subject__icontains=search)
        )
    
    paginator = Paginator(tickets_list, 20)
    page = request.GET.get('page')
    tickets = paginator.get_page(page)
    
    staff_users = User.objects.filter(role__in=['support', 'admin'], is_active=True)
    
    context = {
        'tickets': tickets,
        'staff_users': staff_users,
        'total_tickets': total_tickets,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search,
    }
    
    return render(request, 'core/admin/support_tickets.html', context)



@admin_required
@require_http_methods(["POST"])
def admin_bulk_assign_tickets(request):
    """Bulk assign tickets to staff"""
    data = json.loads(request.body)
    ticket_ids = data.get('ticket_ids', '').split(',')
    staff_id = data.get('assigned_to')
    priority = data.get('priority')
    note = data.get('note')
    is_bulk = data.get('is_bulk', False)
    
    if not staff_id:
        return JsonResponse({'success': False, 'message': 'Please select a staff member'})
    
    staff = get_object_or_404(User, id=staff_id)
    count = 0
    
    for ticket_id in ticket_ids:
        if ticket_id.strip():
            try:
                ticket = SupportTicket.objects.get(id=ticket_id.strip())
                ticket.assigned_to = staff
                if priority:
                    ticket.priority = priority
                ticket.save()
                count += 1
            except SupportTicket.DoesNotExist:
                pass
    
    return JsonResponse({'success': True, 'message': f'{count} ticket(s) assigned successfully'})


@admin_required
@require_http_methods(["POST"])
def admin_bulk_update_tickets(request):
    """Bulk update ticket status"""
    data = json.loads(request.body)
    ticket_ids = data.get('tickets', [])
    new_status = data.get('status')
    note = data.get('note')
    
    if not new_status:
        return JsonResponse({'success': False, 'message': 'Please select a status'})
    
    count = 0
    for ticket_id in ticket_ids:
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            ticket.status = new_status
            if note:
                ticket.resolution = note
            ticket.save()
            count += 1
        except SupportTicket.DoesNotExist:
            pass
    
    return JsonResponse({'success': True, 'message': f'{count} ticket(s) updated successfully'})



@admin_required
def admin_ticket_detail(request, ticket_id):
    """View and manage ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        assigned_to_id = request.POST.get('assigned_to')
        resolution = request.POST.get('resolution')
        
        if status:
            ticket.status = status
        
        if assigned_to_id:
            ticket.assigned_to_id = assigned_to_id
        
        if resolution:
            ticket.resolution = resolution
        
        ticket.save()
        messages.success(request, f'Ticket {ticket.ticket_number} updated successfully!')
        
        # Send notification to user
        Notification.objects.create(
            user=ticket.user,
            title=f'Ticket Update - {ticket.ticket_number}',
            message=f'Your ticket status has been updated to {ticket.status}',
            notification_type='system_alert'
        )
        
        return redirect('core:admin_ticket_detail', ticket_id=ticket.id)
    
    staff_users = User.objects.filter(role__in=['support', 'admin'])
    
    return render(request, 'core/admin/ticket_detail.html', {
        'ticket': ticket,
        'staff_users': staff_users
    })

# Updated admin_reports view in your views.py

@admin_required
def admin_reports(request):
    """Generate reports with dynamic data"""
    report_type = request.GET.get('type', 'summary')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    context = {'report_type': report_type, 'date_from': date_from, 'date_to': date_to}
    
    # Always provide summary data
    from django.utils import timezone
    from datetime import datetime, timedelta
    import json
    
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)
    last_month_start = (first_day_of_month - timedelta(days=1)).replace(day=1)
    
    # Summary statistics - FRESH QUERIES (no cache)
    context['total_users'] = User.objects.count()
    context['new_users_this_month'] = User.objects.filter(date_joined__date__gte=first_day_of_month).count()
    context['active_policies'] = InsurancePolicy.objects.filter(status='active').count()
    context['total_premium_value'] = InsurancePolicy.objects.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0
    context['total_vehicles'] = Vehicle.objects.count()  # ADDED
    
    # Pending claims - count all statuses that are not final
    context['pending_claims'] = Claim.objects.filter(status__in=['pending', 'under_review']).count()
    context['pending_claims_value'] = Claim.objects.filter(status__in=['pending', 'under_review']).aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
    
    # Approved claims count
    context['approved_claims'] = Claim.objects.filter(status='approved').count()
    context['approved_claims_value'] = Claim.objects.filter(status='approved').aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0
    
    # Settled claims count
    context['settled_claims'] = Claim.objects.filter(status='settled').count()
    context['settled_claims_value'] = Claim.objects.filter(status='settled').aggregate(Sum('approved_amount'))['approved_amount__sum'] or 0
    
    # Rejected claims count
    context['rejected_claims'] = Claim.objects.filter(status='rejected').count()
    
    # Monthly revenue
    current_month_revenue = Payment.objects.filter(
        status='completed',
        paid_at__date__gte=first_day_of_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    context['monthly_revenue'] = current_month_revenue
    
    last_month_revenue = Payment.objects.filter(
        status='completed',
        paid_at__date__gte=last_month_start,
        paid_at__date__lt=first_day_of_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    if last_month_revenue > 0:
        context['revenue_growth'] = round(((current_month_revenue - last_month_revenue) / last_month_revenue) * 100, 1)
    else:
        context['revenue_growth'] = 0 if current_month_revenue == 0 else 100
    
    # Chart data for summary
    # Monthly revenue for the last 6 months
    month_labels = []
    revenue_data = []
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = today
        else:
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_revenue = Payment.objects.filter(
            status='completed',
            paid_at__date__gte=month_start,
            paid_at__date__lte=month_end
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        month_labels.append(month_start.strftime('%b %Y'))
        revenue_data.append(float(month_revenue))
    
    context['month_labels'] = json.dumps(month_labels)
    context['revenue_data'] = json.dumps(revenue_data)
    
    # Policy type distribution
    policy_types = InsurancePolicy.objects.values('policy_type').annotate(count=Count('id'))
    context['policy_type_labels'] = json.dumps([pt.get('policy_type', 'other').replace('_', ' ').title() for pt in policy_types])
    context['policy_type_data'] = json.dumps([pt['count'] for pt in policy_types])
    
    # Claim status distribution - ALL STATUSES
    claim_statuses = Claim.objects.values('status').annotate(count=Count('id'))
    status_display = {
        'pending': 'Pending',
        'under_review': 'Under Review',
        'approved': 'Approved',
        'rejected': 'Rejected',
        'settled': 'Settled',
        'withdrawn': 'Withdrawn'
    }
    context['claim_status_labels'] = json.dumps([status_display.get(cs['status'], cs['status'].title()) for cs in claim_statuses])
    context['claim_status_data'] = json.dumps([cs['count'] for cs in claim_statuses])
    
    # Monthly policy sales
    policy_sales_labels = []
    policy_sales_data = []
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = today
        else:
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_sales = InsurancePolicy.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).count()
        
        policy_sales_labels.append(month_start.strftime('%b'))
        policy_sales_data.append(month_sales)
    
    context['policy_sales_labels'] = json.dumps(policy_sales_labels)
    context['policy_sales_data'] = json.dumps(policy_sales_data)
    
    # User report data
    context['total_users_all'] = User.objects.count()
    context['verified_users'] = User.objects.filter(is_verified=True).count()
    context['recent_users'] = User.objects.order_by('-date_joined')[:20]
    
    # User growth chart
    user_growth_labels = []
    user_growth_data = []
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = today
        else:
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_users = User.objects.filter(
            date_joined__date__gte=month_start,
            date_joined__date__lte=month_end
        ).count()
        
        user_growth_labels.append(month_start.strftime('%b'))
        user_growth_data.append(month_users)
    
    context['user_growth_labels'] = json.dumps(user_growth_labels)
    context['user_growth_data'] = json.dumps(user_growth_data)
    
    # User role distribution
    user_roles = User.objects.values('role').annotate(count=Count('id'))
    context['user_role_labels'] = json.dumps([ur['role'].replace('_', ' ').title() for ur in user_roles])
    context['user_role_data'] = json.dumps([ur['count'] for ur in user_roles])
    
    # Date filtered data
    if date_from and date_to:
        start_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        
        if report_type == 'policies':
            policies = InsurancePolicy.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).select_related('user', 'vehicle').order_by('-created_at')
            
            context['data'] = policies
            context['total'] = policies.count()
            context['total_premium'] = policies.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0
            context['active_count'] = policies.filter(status='active').count()
            context['avg_premium'] = (context['total_premium'] / context['total']) if context['total'] > 0 else 0
            
        elif report_type == 'claims':
            claims = Claim.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).select_related('user', 'policy').order_by('-created_at')
            
            context['data'] = claims
            context['total'] = claims.count()
            context['total_amount'] = claims.aggregate(Sum('claimed_amount'))['claimed_amount__sum'] or 0
            context['approved_count'] = claims.filter(status='approved').count()
            context['settled_count'] = claims.filter(status='settled').count()
            context['rejected_count'] = claims.filter(status='rejected').count()
            context['pending_count'] = claims.filter(status__in=['pending', 'under_review']).count()
            context['avg_claim'] = (context['total_amount'] / context['total']) if context['total'] > 0 else 0
            
        elif report_type == 'revenue':
            payments = Payment.objects.filter(
                status='completed',
                paid_at__date__gte=start_date,
                paid_at__date__lte=end_date
            ).select_related('user').order_by('-paid_at')
            
            context['data'] = payments
            context['total_revenue'] = payments.aggregate(Sum('amount'))['amount__sum'] or 0
            context['transaction_count'] = payments.count()
            context['avg_transaction'] = (context['total_revenue'] / context['transaction_count']) if context['transaction_count'] > 0 else 0
            context['by_method'] = payments.values('payment_method').annotate(
                total=Sum('amount'),
                count=Count('id')
            )
    
    return render(request, 'core/admin/reports.html', context)

@admin_required
def admin_export_data(request):
    """Export data to CSV"""
    model = request.GET.get('model')
    format = request.GET.get('format', 'csv')
    
    if model == 'users':
        data = User.objects.all().values('email', 'first_name', 'last_name', 'role', 'is_verified', 'date_joined')
    elif model == 'policies':
        data = InsurancePolicy.objects.all().values('policy_number', 'user__email', 'policy_type', 'status', 'premium_amount', 'created_at')
    elif model == 'claims':
        data = Claim.objects.all().values('claim_number', 'user__email', 'claim_type', 'status', 'claimed_amount', 'created_at')
    elif model == 'payments':
        data = Payment.objects.all().values('transaction_id', 'user__email', 'amount', 'payment_method', 'status', 'created_at')
    else:
        return HttpResponse('Invalid model', status=400)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{model}_{timezone.now().date()}.csv"'
    
    writer = csv.DictWriter(response, fieldnames=data[0].keys() if data else [])
    writer.writeheader()
    writer.writerows(data)
    
    return response

@admin_required
def admin_send_notification(request):
    """Send notification to users"""
    # Get recent notifications for sidebar
    recent_notifications = Notification.objects.filter(
        notification_type='system_alert'
    ).order_by('-created_at')[:10]
    
    # Add recipient count to recent notifications
    for notification in recent_notifications:
        # Count how many users received this notification (based on title and created_at)
        notification.recipient_count = Notification.objects.filter(
            title=notification.title,
            created_at__date=notification.created_at.date()
        ).count()
    
    if request.method == 'POST':
        form = AdminNotificationForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            message = form.cleaned_data['message']
            user_type = form.cleaned_data['user_type']
            specific_user = form.cleaned_data.get('specific_user')
            
            # Get delivery methods
            send_email = request.POST.get('send_email') == 'on'
            send_sms = request.POST.get('send_sms') == 'on'
            send_push = request.POST.get('send_push') == 'on'
            
            # Filter users based on selection
            if user_type == 'all':
                users = User.objects.filter(is_active=True)
            elif user_type == 'customers':
                users = User.objects.filter(role='customer', is_active=True)
            elif user_type == 'staff':
                users = User.objects.filter(
                    role__in=['agent', 'underwriter', 'claims_adjuster', 'support'], 
                    is_active=True
                )
            elif user_type == 'specific' and specific_user:
                users = User.objects.filter(id=specific_user.id, is_active=True)
            else:
                users = User.objects.none()
            
            success_count = 0
            email_count = 0
            sms_count = 0
            
            # Process each user
            for user in users:
                # Replace placeholders in message
                personalized_message = message
                personalized_title = title
                
                if '{name}' in message or '{name}' in title:
                    name = user.get_full_name() or user.email
                    personalized_message = personalized_message.replace('{name}', name)
                    personalized_title = personalized_title.replace('{name}', name)
                
                if '{email}' in message:
                    personalized_message = personalized_message.replace('{email}', user.email)
                
                if '{phone}' in message and user.phone_number:
                    personalized_message = personalized_message.replace('{phone}', str(user.phone_number))
                
                # Create in-app notification
                if send_push:
                    Notification.objects.create(
                        user=user,
                        title=personalized_title,
                        message=personalized_message,
                        notification_type='system_alert'
                    )
                    success_count += 1
                
                # Send email
                if send_email and user.email:
                    try:
                        send_email_notification(
                            user.email,
                            personalized_title,
                            personalized_message
                        )
                        email_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send email to {user.email}: {e}")
                
                # Send SMS
                if send_sms and user.phone_number:
                    try:
                        send_sms_notification(
                            str(user.phone_number),
                            f"{personalized_title}\n\n{personalized_message[:160]}"
                        )
                        sms_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send SMS to {user.phone_number}: {e}")
            
            # Build success message
            msg_parts = []
            if send_push:
                msg_parts.append(f"{success_count} in-app notifications")
            if send_email:
                msg_parts.append(f"{email_count} emails")
            if send_sms:
                msg_parts.append(f"{sms_count} SMS")
            
            messages.success(request, f"Sent: {', '.join(msg_parts)} to {users.count()} users!")
            
            # Log activity
            log_user_activity(request.user, 'send_notification', request, {
                'user_type': user_type,
                'recipient_count': users.count(),
                'channels': {
                    'push': send_push,
                    'email': send_email,
                    'sms': send_sms
                }
            })
            
            return redirect('core:admin_send_notification')
    else:
        form = AdminNotificationForm()
    
    context = {
        'form': form,
        'recent_notifications': recent_notifications,
    }
    
    return render(request, 'core/admin/send_notification.html', context)


@admin_required
def get_recipient_count(request):
    """API endpoint to get recipient count"""
    user_type = request.GET.get('user_type')
    
    if user_type == 'all':
        count = User.objects.filter(is_active=True).count()
        customers = User.objects.filter(role='customer', is_active=True).count()
        staff = User.objects.filter(role__in=['agent', 'underwriter', 'claims_adjuster', 'support'], is_active=True).count()
        admins = User.objects.filter(role='admin', is_active=True).count()
        
        return JsonResponse({
            'count': count,
            'customers': customers,
            'staff': staff,
            'admins': admins
        })
    
    elif user_type == 'customers':
        count = User.objects.filter(role='customer', is_active=True).count()
        return JsonResponse({'count': count})
    
    elif user_type == 'staff':
        count = User.objects.filter(role__in=['agent', 'underwriter', 'claims_adjuster', 'support'], is_active=True).count()
        agents = User.objects.filter(role='agent', is_active=True).count()
        underwriters = User.objects.filter(role='underwriter', is_active=True).count()
        adjusters = User.objects.filter(role='claims_adjuster', is_active=True).count()
        support = User.objects.filter(role='support', is_active=True).count()
        
        return JsonResponse({
            'count': count,
            'agents': agents,
            'underwriters': underwriters,
            'adjusters': adjusters,
            'support': support
        })
    
    return JsonResponse({'count': 0})






from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from apps.core.models import InsuranceSettings
from apps.core.decorators import admin_required
from decimal import Decimal

@admin_required
def admin_insurance_settings(request):
    """Admin view to manage insurance premium settings"""
    settings = InsuranceSettings.get_settings()
    
    if request.method == 'POST':
        try:
            # Coverage Type Multipliers
            settings.comprehensive_multiplier = Decimal(request.POST.get('comprehensive_multiplier', '1.8'))
            settings.third_party_multiplier = Decimal(request.POST.get('third_party_multiplier', '1.0'))
            settings.standalone_multiplier = Decimal(request.POST.get('standalone_multiplier', '1.3'))
            settings.personal_accident_multiplier = Decimal(request.POST.get('personal_accident_multiplier', '0.6'))
            
            # Base Premium Settings
            settings.base_premium_amount = Decimal(request.POST.get('base_premium_amount', '50000'))
            settings.base_coverage_reference = Decimal(request.POST.get('base_coverage_reference', '1000000'))
            
            # Minimum Premium Settings
            settings.min_premium_comprehensive = Decimal(request.POST.get('min_premium_comprehensive', '75000'))
            settings.min_premium_third_party = Decimal(request.POST.get('min_premium_third_party', '15000'))
            settings.min_premium_standalone = Decimal(request.POST.get('min_premium_standalone', '35000'))
            settings.min_premium_personal_accident = Decimal(request.POST.get('min_premium_personal_accident', '10000'))
            
            # Vehicle Age Multipliers
            settings.age_0_1_multiplier = Decimal(request.POST.get('age_0_1_multiplier', '0.9'))
            settings.age_2_3_multiplier = Decimal(request.POST.get('age_2_3_multiplier', '1.0'))
            settings.age_4_5_multiplier = Decimal(request.POST.get('age_4_5_multiplier', '1.2'))
            settings.age_6_10_multiplier = Decimal(request.POST.get('age_6_10_multiplier', '1.5'))
            settings.age_10_plus_multiplier = Decimal(request.POST.get('age_10_plus_multiplier', '2.0'))
            
            # Vehicle Type Multipliers
            settings.car_multiplier = Decimal(request.POST.get('car_multiplier', '1.0'))
            settings.motorcycle_multiplier = Decimal(request.POST.get('motorcycle_multiplier', '0.7'))
            settings.truck_multiplier = Decimal(request.POST.get('truck_multiplier', '1.5'))
            settings.bus_multiplier = Decimal(request.POST.get('bus_multiplier', '1.6'))
            settings.rickshaw_multiplier = Decimal(request.POST.get('rickshaw_multiplier', '0.8'))
            
            # Engine Capacity Multipliers
            settings.engine_above_3000_multiplier = Decimal(request.POST.get('engine_above_3000_multiplier', '1.3'))
            settings.engine_2000_3000_multiplier = Decimal(request.POST.get('engine_2000_3000_multiplier', '1.15'))
            settings.engine_1000_2000_multiplier = Decimal(request.POST.get('engine_1000_2000_multiplier', '1.0'))
            settings.engine_below_1000_multiplier = Decimal(request.POST.get('engine_below_1000_multiplier', '0.9'))
            
            # Deductible Settings
            settings.deductible_percentage = Decimal(request.POST.get('deductible_percentage', '10'))
            settings.min_deductible = Decimal(request.POST.get('min_deductible', '5000'))
            settings.max_deductible = Decimal(request.POST.get('max_deductible', '100000'))
            
            # Add-on Costs
            settings.roadside_assistance_cost = Decimal(request.POST.get('roadside_assistance_cost', '15000'))
            settings.zero_depreciation_cost = Decimal(request.POST.get('zero_depreciation_cost', '25000'))
            settings.engine_protection_cost = Decimal(request.POST.get('engine_protection_cost', '20000'))
            settings.personal_accident_cover_cost = Decimal(request.POST.get('personal_accident_cover_cost', '10000'))
            
            # Promo Default
            settings.default_promo_percentage = Decimal(request.POST.get('default_promo_percentage', '10'))
            
            settings.updated_by = request.user
            settings.save()
            
            messages.success(request, 'Insurance settings updated successfully!')
            return redirect('core:admin_insurance_settings')
            
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
    
    context = {
        'settings': settings,
    }
    return render(request, 'core/admin/insurance_settings.html', context)







from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.core.models import Vehicle, User, InsurancePolicy, Claim
from apps.core.decorators import admin_required
from apps.core.forms import VehicleForm


@admin_required
def admin_vehicles(request):
    """Admin view to manage all vehicles"""
    vehicles_list = Vehicle.objects.select_related('user', 'created_by', 'updated_by').all().order_by('-created_at')
    
    # Summary statistics
    total_vehicles = vehicles_list.count()
    insured_vehicles = vehicles_list.filter(is_insured=True).count()
    uninsured_vehicles = vehicles_list.filter(is_insured=False).count()
    
    # Count by type
    vehicle_types = vehicles_list.values('vehicle_type').annotate(count=Count('id'))
    type_counts = {vt['vehicle_type']: vt['count'] for vt in vehicle_types}
    
    # Filter by vehicle type
    vehicle_type = request.GET.get('vehicle_type')
    if vehicle_type:
        vehicles_list = vehicles_list.filter(vehicle_type=vehicle_type)
    
    # Filter by insurance status
    is_insured = request.GET.get('is_insured')
    if is_insured is not None:
        vehicles_list = vehicles_list.filter(is_insured=is_insured == 'true')
    
    # Filter by user
    user_id = request.GET.get('user_id')
    if user_id:
        vehicles_list = vehicles_list.filter(user_id=user_id)
    
    # Search
    search = request.GET.get('search')
    if search:
        vehicles_list = vehicles_list.filter(
            Q(registration_number__icontains=search) |
            Q(make__icontains=search) |
            Q(model__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(engine_number__icontains=search) |
            Q(chassis_number__icontains=search)
        )
    
    paginator = Paginator(vehicles_list, 20)
    page = request.GET.get('page')
    vehicles = paginator.get_page(page)
    
    # Get all users for filter dropdown
    users = User.objects.filter(vehicles__isnull=False).distinct().order_by('first_name', 'last_name')
    
    context = {
        'vehicles': vehicles,
        'total_vehicles': total_vehicles,
        'insured_vehicles': insured_vehicles,
        'uninsured_vehicles': uninsured_vehicles,
        'type_counts': type_counts,
        'users': users,
        'vehicle_type_filter': vehicle_type,
        'is_insured_filter': is_insured,
        'user_filter': user_id,
        'search_query': search,
    }
    
    return render(request, 'core/admin/vehicles.html', context)


@admin_required
def admin_vehicle_detail(request, vehicle_id):
    """Admin view to see vehicle details"""
    vehicle = get_object_or_404(Vehicle.objects.select_related(
        'user', 'created_by', 'updated_by'
    ), id=vehicle_id)
    
    # Get related policies and claims
    policies = vehicle.policies.all().order_by('-created_at')
    claims = Claim.objects.filter(policy__vehicle=vehicle).order_by('-created_at')
    
    # Get activity history (you can add a VehicleActivityLog model if needed)
    # For now, we'll show basic info
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            updated_vehicle = form.save(commit=False)
            updated_vehicle.updated_by = request.user
            updated_vehicle.save()
            
            messages.success(request, f'Vehicle {vehicle.registration_number} updated successfully!')
            return redirect('core:admin_vehicle_detail', vehicle_id=vehicle.id)
    else:
        form = VehicleForm(instance=vehicle)
    
    context = {
        'vehicle': vehicle,
        'form': form,
        'policies': policies,
        'claims': claims,
    }
    
    return render(request, 'core/admin/vehicle_detail.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_vehicle_action(request, vehicle_id, action):
    """Handle vehicle actions"""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    
    try:
        if action == 'toggle_insured':
            vehicle.is_insured = not vehicle.is_insured
            vehicle.updated_by = request.user
            vehicle.save()
            status = 'insured' if vehicle.is_insured else 'uninsured'
            return JsonResponse({'success': True, 'message': f'Vehicle marked as {status}'})
            
        elif action == 'delete':
            reg_number = vehicle.registration_number
            vehicle.delete()
            return JsonResponse({'success': True, 'message': f'Vehicle {reg_number} deleted successfully'})
            
        else:
            return JsonResponse({'success': False, 'message': 'Invalid action'}, status=400)
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@admin_required
def admin_vehicles_by_user(request, user_id):
    """View vehicles belonging to a specific user"""
    user = get_object_or_404(User, id=user_id)
    vehicles = Vehicle.objects.filter(user=user).select_related('created_by', 'updated_by').order_by('-created_at')
    
    # Calculate statistics
    insured_count = vehicles.filter(is_insured=True).count()
    uninsured_count = vehicles.filter(is_insured=False).count()
    active_policies = InsurancePolicy.objects.filter(user=user, status='active').count()
    total_claims = Claim.objects.filter(user=user).count()
    
    context = {
        'user': user,
        'vehicles': vehicles,
        'total_vehicles': vehicles.count(),
        'insured_count': insured_count,
        'uninsured_count': uninsured_count,
        'active_policies': active_policies,
        'total_claims': total_claims,
    }
    
    return render(request, 'core/admin/vehicles_by_user.html', context)