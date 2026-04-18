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
from django.core.mail import send_mail
from django.db.models import Sum
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from .views import generate_policy_certificate, regenerate_certificate, generate_policy_document
from apps.core.models import (
    User, Vehicle, InsurancePolicy, Claim, Payment, PolicyCancellation,
    InsuranceQuote, Notification, Document, SupportTicket, InstallmentPlan, AgentCommissionOverride,
    PromoCode, UserActivityLog, PolicyCertificate, PolicyEndorsement, PolicyRenewal, NoClaimBonus, CommissionStructure, Commission, DebitCreditNote, DebitCreditNote
)

from .forms import (
    AdminUserForm, AdminPolicyForm, AdminClaimForm, CommissionStructureForm, PolicyCancellationForm, PolicyEndorsementForm, PolicyRenewalForm, AdminNotificationForm, 
    PromoCodeForm, AdminNotificationForm, PolicyEndorsementForm, PolicyRenewalForm, DebitCreditNoteForm, PolicyCancellationForm,
    AgentCommissionOverrideForm
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


@staff_member_required
def admin_policy_detail(request, policy_id):
    """View policy details with financial summary"""
    policy = get_object_or_404(
        InsurancePolicy.objects.select_related('user', 'vehicle', 'certificate'),
        id=policy_id
    )
    
    if request.method == 'POST':
        form = AdminPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, f'Policy {policy.policy_number} updated successfully!')
            return redirect('core:admin_policy_detail', policy_id=policy.id)
    else:
        form = AdminPolicyForm(instance=policy)
    
    certificate = None
    if hasattr(policy, 'certificate'):
        certificate = policy.certificate
    
    # Get all related data
    payments = policy.payments.all().order_by('-created_at')
    claims = policy.claims.all().order_by('-created_at')
    debit_credit_notes = policy.debit_credit_notes.all().order_by('-created_at')
    installment_plans = policy.installment_plans.all().order_by('-created_at')
    cancellations = policy.cancellations.all().order_by('-created_at')
    
    # Calculate financial summary
    total_paid = policy.get_total_paid()
    total_debit_notes = policy.get_total_debit_notes()
    total_credit_notes = policy.get_total_credit_notes()
    total_credits_applied = policy.get_total_credits_applied()
    outstanding_balance = policy.get_outstanding_balance()
    payment_status = policy.get_payment_status()
    pending_amount = policy.get_pending_payments_total()
    
    context = {
        'policy': policy,
        'form': form,
        'payments': payments,
        'claims': claims,
        'certificate': certificate,
        'debit_credit_notes': debit_credit_notes,
        'installment_plans': installment_plans,
        'cancellations': cancellations,
        'total_paid': total_paid,
        'total_debit_notes': total_debit_notes,
        'total_credit_notes': total_credit_notes,
        'total_credits_applied': total_credits_applied,
        'outstanding_balance': outstanding_balance,
        'payment_status': payment_status,
        'pending_amount': pending_amount,
    }
    
    return render(request, 'core/admin/policy_detail.html', context)


@require_http_methods(["POST"])
@staff_member_required
def admin_activate_policy(request, policy_id):
    """Activate a policy"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    try:
        old_status = policy.status
        policy.status = 'active'
        policy.save()
        
        if old_status != 'active':
            result = generate_policy_certificate(policy, generated_by=request.user)
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': 'Policy activated and certificate generated!'
                })
        
        return JsonResponse({
            'success': True,
            'message': 'Policy activated successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })



@require_http_methods(["POST"])
@staff_member_required
def admin_cancel_policy(request, policy_id):
    """Cancel a policy - Creates cancellation record and processes refund if applicable"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    try:
        # Check if policy is already cancelled
        if policy.status == 'cancelled':
            return JsonResponse({
                'success': False,
                'message': 'Policy is already cancelled.'
            })
        
        # Create cancellation record
        cancellation = PolicyCancellation.objects.create(
            policy=policy,
            user=policy.user,
            reason='other',
            other_reason='Cancelled by admin',
            cancellation_date=timezone.now().date(),
            effective_date=timezone.now().date(),
            total_premium=policy.premium_amount,
            status='approved',
            approved_by=request.user,
            approved_date=timezone.now()
        )
        
        # Calculate refund
        cancellation.calculate_refund()
        cancellation.save()
        
        # Process the cancellation (this updates policy status and creates credit note)
        success = cancellation.process_cancellation()
        
        if success:
            # Send notification to user
            Notification.objects.create(
                user=policy.user,
                title='Policy Cancelled',
                message=f'Your policy #{policy.policy_number} has been cancelled. ' +
                        f'Refund amount: ₦{cancellation.refund_amount:,.2f}',
                notification_type='system_alert',
                data={'policy_id': str(policy.id), 'cancellation_id': str(cancellation.id)}
            )
            
            # Log activity
            log_user_activity(request.user, 'cancel_policy', request, {
                'policy_id': str(policy.id),
                'cancellation_id': str(cancellation.id),
                'refund_amount': str(cancellation.refund_amount)
            })
            
            return JsonResponse({
                'success': True,
                'message': f'Policy cancelled successfully. Refund amount: ₦{cancellation.refund_amount:,.2f}'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Failed to process cancellation.'
            })
        
    except Exception as e:
        logger.error(f"Error cancelling policy: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


# apps/core/admin_views.py

@require_http_methods(["POST"])
@staff_member_required
def admin_generate_certificate(request, policy_id):
    """Manually generate certificate for a policy"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    try:
        # Pass request object to the function
        result = generate_policy_certificate(policy, generated_by=request.user, request=request)
        
        if result['success']:
            Notification.objects.create(
                user=policy.user,
                title='Insurance Certificate Ready',
                message=f'Your insurance certificate for policy #{policy.policy_number} is now available.',
                notification_type='system_alert',
                data={'policy_id': str(policy.id)}
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Certificate generated successfully!'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': result.get('message', 'Failed to generate certificate')
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@require_http_methods(["POST"])
@staff_member_required
def admin_regenerate_certificate(request, policy_id):
    """Regenerate certificate for a policy"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    try:
        # Pass request object to the function
        result = regenerate_certificate(policy, generated_by=request.user, request=request)
        
        if result['success']:
            Notification.objects.create(
                user=policy.user,
                title='Certificate Regenerated',
                message=f'Your certificate for policy #{policy.policy_number} has been regenerated.',
                notification_type='system_alert',
                data={'policy_id': str(policy.id)}
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Certificate regenerated successfully!'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': result.get('message', 'Failed to regenerate certificate')
            })
            
    except Exception as e:
        import traceback
        print(f"Certificate Regeneration Error: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@require_http_methods(["POST"])
@staff_member_required
def admin_regenerate_document(request, policy_id):
    """Regenerate policy document"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    try:
        if policy.policy_document:
            policy.policy_document.delete(save=False)
        
        policy_doc = generate_policy_document(policy)
        policy.policy_document = policy_doc
        policy.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Policy document regenerated!'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
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





# apps/core/admin_views.py - Complete updated admin views

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json
import logging

from apps.core.models import Payment, InsurancePolicy, Notification, User, InstallmentPlan, Installment
from apps.core.decorators import admin_required
from .Utils.utils import log_user_activity, generate_policy_certificate

logger = logging.getLogger(__name__)


# Email Functions
def send_customer_payment_email(payment):
    """Send payment confirmation email to customer"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings as django_settings
    
    try:
        subject = f'Payment Confirmation - {payment.policy.policy_number}'
        
        context = {
            'user': payment.user,
            'payment': payment,
            'policy': payment.policy,
            'amount': payment.amount,
            'transaction_id': payment.payment_details.get('id', payment.transaction_id) if payment.payment_details else payment.transaction_id,
            'payment_date': payment.paid_at or timezone.now(),
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
        return True
        
    except Exception as e:
        logger.error(f"Failed to send customer payment email: {str(e)}")
        return False


def send_staff_payment_email(payment):
    """Send payment notification email to staff"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings as django_settings
    
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
            'transaction_id': payment.payment_details.get('id', payment.transaction_id) if payment.payment_details else payment.transaction_id,
            'payment_date': payment.paid_at or timezone.now(),
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
        return True
        
    except Exception as e:
        logger.error(f"Failed to send staff payment email: {str(e)}")
        return False


@admin_required
def admin_payments(request):
    """Manage payments view"""
    payments_list = Payment.objects.select_related(
        'user', 'policy', 'policy__vehicle'
    ).prefetch_related(
        'policy__installment_plans'
    ).all().order_by('-created_at')
    
    # Calculate summary statistics
    total_payments = payments_list.count()
    total_revenue = payments_list.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    completed_count = payments_list.filter(status='completed').count()
    pending_count = payments_list.filter(status__in=['pending', 'pending_verification']).count()
    
    # Count installment payments
    installment_payments = payments_list.filter(
        Q(payment_details__type='installment') | 
        Q(payment_details__type='down_payment')
    ).count()
    
    full_payments = total_payments - installment_payments
    
    # Filter by status
    status = request.GET.get('status')
    status_filter = status
    if status:
        payments_list = payments_list.filter(status=status)
    
    # Filter by payment method
    method = request.GET.get('method')
    method_filter = method
    if method:
        payments_list = payments_list.filter(payment_method=method)
    
    # Filter by payment type (full or installment)
    payment_type = request.GET.get('payment_type')
    payment_type_filter = payment_type
    if payment_type == 'full':
        payments_list = payments_list.exclude(
            Q(payment_details__type='installment') | 
            Q(payment_details__type='down_payment')
        )
    elif payment_type == 'installment':
        payments_list = payments_list.filter(
            Q(payment_details__type='installment') | 
            Q(payment_details__type='down_payment')
        )
    
    # Filter by date
    date = request.GET.get('date')
    date_filter = date
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
            Q(user__last_name__icontains=search) |
            Q(policy__policy_number__icontains=search)
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
        'installment_payments': installment_payments,
        'full_payments': full_payments,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'payment_type_filter': payment_type_filter,
        'date_filter': date_filter,
        'search_query': search,
    }
    
    return render(request, 'core/admin/payments.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_verify_bank_transfer(request, payment_id):
    """Verify bank transfer payment"""
    try:
        data = json.loads(request.body)
        notes = data.get('notes', '')
    except:
        notes = ''
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status != 'pending_verification':
        return JsonResponse({'success': False, 'message': 'Payment is not pending verification'})
    
    payment.status = 'completed'
    payment.paid_at = timezone.now()
    payment.verified_by = request.user
    payment.verified_at = timezone.now()
    if notes:
        if not payment.payment_details:
            payment.payment_details = {}
        payment.payment_details['verification_notes'] = notes
    payment.save()
    
    # Activate policy if this is a full payment
    if payment.policy:
        policy = payment.policy
        
        # Check if this is part of an installment plan
        if payment.payment_details and payment.payment_details.get('type') in ['installment', 'down_payment']:
            # Handle installment payment
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
                        
                        # Check if all installments are paid
                        if not plan.installments.filter(status='pending').exists():
                            plan.status = 'completed'
                            plan.save()
                            policy.status = 'active'
                            policy.save()
                            generate_policy_certificate(policy)
                        
                        # Update next due date
                        next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
                        if next_installment:
                            plan.next_due_date = next_installment.due_date
                            plan.save()
                    except Installment.DoesNotExist:
                        pass
            
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
                        
                        policy.status = 'active'
                        policy.save()
                        generate_policy_certificate(policy)
                        
                        next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
                        if next_installment:
                            plan.next_due_date = next_installment.due_date
                            plan.save()
                    except InstallmentPlan.DoesNotExist:
                        pass
        else:
            # Full payment - activate immediately
            policy.status = 'active'
            policy.save()
            generate_policy_certificate(policy)
    
    # Send notifications
    Notification.objects.create(
        user=payment.user,
        title='Payment Verified - Policy Active',
        message=f'Your payment of ₦{payment.amount:,.2f} has been verified. Your policy is now active!',
        notification_type='payment_confirmation',
        data={'policy_id': str(payment.policy.id) if payment.policy else None}
    )
    
    send_customer_payment_email(payment)
    send_staff_payment_email(payment)
    
    log_user_activity(request.user, 'verify_payment', request, {
        'payment_id': str(payment.id),
        'amount': str(payment.amount)
    })
    
    return JsonResponse({'success': True, 'message': 'Payment verified successfully'})


@admin_required
@require_http_methods(["POST"])
def admin_mark_payment_completed(request, payment_id):
    """Mark payment as completed"""
    try:
        data = json.loads(request.body)
    except:
        data = {}
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status == 'completed':
        return JsonResponse({'success': False, 'message': 'Payment is already completed'})
    
    payment.status = 'completed'
    payment.paid_at = timezone.now()
    payment.verified_by = request.user
    payment.verified_at = timezone.now()
    payment.save()
    
    # Activate policy
    if payment.policy:
        policy = payment.policy
        
        # Handle installment payments
        if payment.payment_details and payment.payment_details.get('type') in ['installment', 'down_payment']:
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
                            policy.status = 'active'
                            policy.save()
                            generate_policy_certificate(policy)
                    except Installment.DoesNotExist:
                        pass
            elif payment.payment_details.get('type') == 'down_payment':
                plan_id = payment.payment_details.get('installment_plan_id')
                if plan_id:
                    try:
                        plan = InstallmentPlan.objects.get(id=plan_id)
                        first_installment = plan.installments.filter(installment_number=1).first()
                        if first_installment:
                            first_installment.status = 'paid'
                            first_installment.paid_date = timezone.now()
                            first_installment.save()
                        
                        policy.status = 'active'
                        policy.save()
                        generate_policy_certificate(policy)
                    except InstallmentPlan.DoesNotExist:
                        pass
        else:
            policy.status = 'active'
            policy.save()
            generate_policy_certificate(policy)
    
    Notification.objects.create(
        user=payment.user,
        title='Payment Confirmed',
        message=f'Your payment of ₦{payment.amount:,.2f} has been confirmed.',
        notification_type='payment_confirmation',
        data={'payment_id': str(payment.id)}
    )
    
    send_customer_payment_email(payment)
    
    log_user_activity(request.user, 'mark_payment_completed', request, {
        'payment_id': str(payment.id)
    })
    
    return JsonResponse({'success': True, 'message': 'Payment marked as completed'})


@admin_required
@require_http_methods(["POST"])
def admin_mark_payment_failed(request, payment_id):
    """Mark payment as failed"""
    try:
        data = json.loads(request.body)
        reason = data.get('reason', 'Payment verification failed')
    except:
        reason = 'Payment verification failed'
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    payment.status = 'failed'
    payment.failure_reason = reason
    payment.save()
    
    Notification.objects.create(
        user=payment.user,
        title='Payment Failed',
        message=f'Your payment of ₦{payment.amount:,.2f} could not be verified. Reason: {reason}',
        notification_type='payment_confirmation',
        data={'payment_id': str(payment.id)}
    )
    
    log_user_activity(request.user, 'mark_payment_failed', request, {
        'payment_id': str(payment.id),
        'reason': reason
    })
    
    return JsonResponse({'success': True, 'message': 'Payment marked as failed'})


@admin_required
@require_http_methods(["POST"])
def admin_process_refund(request, payment_id):
    """Process refund for a payment"""
    try:
        data = json.loads(request.body)
    except:
        data = {}
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status != 'completed':
        return JsonResponse({'success': False, 'message': 'Only completed payments can be refunded'})
    
    payment.status = 'refunded'
    payment.refunded_at = timezone.now()
    payment.refunded_by = request.user
    payment.save()
    
    # Cancel policy if refunded
    if payment.policy:
        payment.policy.status = 'cancelled'
        payment.policy.save()
    
    Notification.objects.create(
        user=payment.user,
        title='Payment Refunded',
        message=f'Your payment of ₦{payment.amount:,.2f} has been refunded.',
        notification_type='payment_confirmation',
        data={'payment_id': str(payment.id)}
    )
    
    log_user_activity(request.user, 'refund_payment', request, {
        'payment_id': str(payment.id),
        'amount': str(payment.amount)
    })
    
    return JsonResponse({'success': True, 'message': 'Refund processed successfully'})


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






# apps/core/admin_views.py - Add these views at the end

# ============================================
# DEBIT/CREDIT NOTE ADMIN VIEWS
# ============================================
# apps/core/admin_views.py - Updated debit/credit note views

@admin_required
def admin_debit_credit_notes(request):
    """Manage debit and credit notes"""
    notes_list = DebitCreditNote.objects.select_related(
        'policy', 'user', 'policy__user', 'created_by'
    ).all().order_by('-created_at')
    
    # Filters
    note_type = request.GET.get('note_type')
    note_type_filter = note_type
    if note_type:
        notes_list = notes_list.filter(note_type=note_type)
    
    status = request.GET.get('status')
    status_filter = status
    if status:
        notes_list = notes_list.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        notes_list = notes_list.filter(
            Q(note_number__icontains=search) |
            Q(policy__policy_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    # Summary stats
    total_notes = notes_list.count()
    total_debit = notes_list.filter(note_type='debit', status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_credit = notes_list.filter(note_type='credit', status='paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    pending_notes = notes_list.filter(status__in=['draft', 'issued']).count()
    
    paginator = Paginator(notes_list, 20)
    page = request.GET.get('page')
    notes = paginator.get_page(page)
    
    context = {
        'notes': notes,
        'total_notes': total_notes,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'pending_notes': pending_notes,
        'note_type': note_type_filter,
        'status': status_filter,
        'search_query': search,
        'today': timezone.now().date(),
    }
    
    return render(request, 'core/admin/debit_credit_notes.html', context)


@admin_required
def admin_create_debit_credit_note(request):
    """Create new debit/credit note"""
    if request.method == 'POST':
        form = DebitCreditNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            # Set the user from the selected policy if not already set
            if not note.user_id:
                note.user = note.policy.user
            note.created_by = request.user
            note.save()
            
            # Generate PDF document for the note
            generate_note_document(note)
            
            # If issued immediately, apply to policy
            if note.status == 'issued':
                note.apply_to_policy()
            
            messages.success(request, f'{note.get_note_type_display()} created successfully!')
            return redirect('core:admin_debit_credit_notes')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DebitCreditNoteForm()
    
    # Get policies for dropdown with customer info
    policies = InsurancePolicy.objects.select_related('user').filter(
        status__in=['active', 'pending']
    ).order_by('-created_at')
    
    context = {
        'form': form,
        'policies': policies,
    }
    
    return render(request, 'core/admin/debit_credit_note_form.html', context)


@admin_required
def admin_note_detail(request, note_id):
    """View debit/credit note details"""
    note = get_object_or_404(DebitCreditNote.objects.select_related(
        'policy', 'user', 'created_by', 'related_payment'
    ), id=note_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'issue':
            note.status = 'issued'
            note.save()
            note.apply_to_policy()
            messages.success(request, f'{note.note_number} issued and applied successfully!')
        
        elif action == 'mark_paid':
            note.status = 'paid'
            note.paid_date = timezone.now()
            note.save()
            messages.success(request, f'{note.note_number} marked as paid!')
        
        elif action == 'cancel':
            note.status = 'cancelled'
            note.save()
            messages.success(request, f'{note.note_number} cancelled!')
        
        elif action == 'apply':
            success = note.apply_to_policy()
            if success:
                messages.success(request, f'{note.note_number} applied to policy successfully!')
            else:
                messages.error(request, 'Note must be issued before applying.')
        
        return redirect('core:admin_note_detail', note_id=note.id)
    
    # Get related payments
    payments = note.note_payments.all()
    
    # Calculate user balance
    user_balance = note.get_user_balance()
    
    context = {
        'note': note,
        'payments': payments,
        'user_balance': user_balance,
    }
    
    return render(request, 'core/admin/note_detail.html', context)


@admin_required
@require_http_methods(["GET"])
def api_policy_summary(request, policy_id):
    """API endpoint to get policy summary for debit/credit note creation"""
    try:
        policy = InsurancePolicy.objects.select_related('user').get(id=policy_id)
        
        # Get existing balance
        from django.db.models import Sum
        
        total_paid = Payment.objects.filter(
            policy=policy,
            status='completed'
        ).exclude(amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0
        
        total_debits = DebitCreditNote.objects.filter(
            policy=policy,
            note_type='debit',
            status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        total_credits = DebitCreditNote.objects.filter(
            policy=policy,
            note_type='credit',
            status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        outstanding_balance = policy.premium_amount + total_debits - total_credits - total_paid
        
        data = {
            'policy_number': policy.policy_number,
            'customer_name': policy.user.get_full_name() or policy.user.email,
            'customer_email': policy.user.email,
            'customer_id': str(policy.user.id),
            'premium_amount': float(policy.premium_amount),
            'coverage_amount': float(policy.coverage_amount),
            'total_paid': float(total_paid),
            'outstanding_balance': float(outstanding_balance),
            'start_date': policy.start_date.strftime('%b %d, %Y'),
            'end_date': policy.end_date.strftime('%b %d, %Y'),
            'status': policy.status,
            'status_display': policy.get_status_display(),
        }
        
        return JsonResponse(data)
    except InsurancePolicy.DoesNotExist:
        return JsonResponse({'error': 'Policy not found'}, status=404)


def generate_note_document(note):
    """Generate PDF for debit/credit note"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    from django.core.files.base import ContentFile
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"{note.get_note_type_display().upper()}")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Note Number: {note.note_number}")
    p.drawString(100, 710, f"Policy Number: {note.policy.policy_number}")
    p.drawString(100, 690, f"Customer: {note.user.get_full_name() or note.user.email}")
    p.drawString(100, 670, f"Issue Date: {note.issue_date}")
    
    if note.due_date:
        p.drawString(100, 650, f"Due Date: {note.due_date}")
    
    # Amounts
    p.drawString(100, 610, f"Base Amount: ₦{note.base_amount:,.2f}")
    p.drawString(100, 590, f"Tax Amount: ₦{note.tax_amount:,.2f}")
    p.drawString(100, 570, f"Total Amount: ₦{note.total_amount:,.2f}")
    
    # Description
    p.drawString(100, 530, "Description:")
    
    # Wrap text
    desc_lines = note.description.split('\n')
    y = 510
    for line in desc_lines[:5]:  # Limit to 5 lines
        p.drawString(120, y, line[:80])
        y -= 15
    
    # Reason
    p.drawString(100, y - 20, f"Reason: {note.get_reason_display()}")
    
    # Footer
    p.setFont("Helvetica", 8)
    p.drawString(100, 50, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
    p.drawString(100, 35, "This is a system-generated document.")
    
    p.save()
    
    buffer.seek(0)
    note.note_document.save(
        f"{note.note_number}.pdf",
        ContentFile(buffer.getvalue()),
        save=True
    )

# ============================================
# ENDORSEMENT ADMIN VIEWS
# ============================================
@admin_required
def admin_endorsements(request):
    """Manage policy endorsements"""
    endorsements_list = PolicyEndorsement.objects.select_related(
        'policy', 'policy__user', 'requested_by', 'approved_by'
    ).all().order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    status_filter = status
    if status:
        endorsements_list = endorsements_list.filter(status=status)
    
    endorsement_type = request.GET.get('type')
    type_filter = endorsement_type
    if endorsement_type:
        endorsements_list = endorsements_list.filter(endorsement_type=endorsement_type)
    
    # Search
    search = request.GET.get('search')
    if search:
        endorsements_list = endorsements_list.filter(
            Q(endorsement_number__icontains=search) |
            Q(policy__policy_number__icontains=search) |
            Q(policy__user__email__icontains=search) |
            Q(policy__user__first_name__icontains=search) |
            Q(policy__user__last_name__icontains=search)
        )
    
    # Stats
    total_endorsements = endorsements_list.count()
    pending_count = endorsements_list.filter(status='pending').count()
    approved_count = endorsements_list.filter(status='approved').count()
    applied_count = endorsements_list.filter(status='applied').count()
    rejected_count = endorsements_list.filter(status='rejected').count()
    
    # Financial summary
    total_adjustments = endorsements_list.filter(
        status__in=['approved', 'applied']
    ).aggregate(total=Sum('total_adjustment'))['total'] or Decimal('0')
    
    paginator = Paginator(endorsements_list, 20)
    page = request.GET.get('page')
    endorsements = paginator.get_page(page)
    
    context = {
        'endorsements': endorsements,
        'total_endorsements': total_endorsements,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'applied_count': applied_count,
        'rejected_count': rejected_count,
        'total_adjustments': total_adjustments,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search_query': search,
    }
    
    return render(request, 'core/admin/endorsements.html', context)


@admin_required
def admin_endorsement_detail(request, endorsement_id):
    """View and process endorsement"""
    endorsement = get_object_or_404(
        PolicyEndorsement.objects.select_related(
            'policy', 'policy__user', 'requested_by', 'approved_by'
        ).prefetch_related('debit_credit_notes'),
        id=endorsement_id
    )
    
    # Get related debit/credit notes
    related_notes = endorsement.debit_credit_notes.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            premium_adjustment = Decimal(request.POST.get('premium_adjustment', '0'))
            tax_adjustment = Decimal(request.POST.get('tax_adjustment', '0'))
            
            endorsement.status = 'approved'
            endorsement.premium_adjustment = premium_adjustment
            endorsement.tax_adjustment = tax_adjustment
            endorsement.save()
            
            # Apply endorsement
            success = endorsement.apply_endorsement(approved_by=request.user)
            
            if success:
                messages.success(request, 'Endorsement approved and applied successfully!')
                
                # Log activity
                log_user_activity(request.user, 'approve_endorsement', request, {
                    'endorsement_id': str(endorsement.id),
                    'policy_id': str(endorsement.policy.id),
                    'adjustment': str(endorsement.total_adjustment)
                })
            else:
                messages.error(request, 'Failed to apply endorsement.')
            
        elif action == 'reject':
            rejection_reason = request.POST.get('rejection_reason', '')
            
            if not rejection_reason:
                messages.error(request, 'Please provide a rejection reason.')
                return redirect('core:admin_endorsement_detail', endorsement_id=endorsement.id)
            
            endorsement.status = 'rejected'
            endorsement.rejection_reason = rejection_reason
            endorsement.save()
            
            # Send notification
            Notification.objects.create(
                user=endorsement.requested_by,
                title=f'Endorsement Rejected',
                message=f'Your endorsement request #{endorsement.endorsement_number} has been rejected. Reason: {rejection_reason}',
                notification_type='system_alert',
                data={'endorsement_id': str(endorsement.id)}
            )
            
            messages.warning(request, 'Endorsement rejected!')
            
            # Log activity
            log_user_activity(request.user, 'reject_endorsement', request, {
                'endorsement_id': str(endorsement.id),
                'reason': rejection_reason
            })
        
        return redirect('core:admin_endorsements')
    
    context = {
        'endorsement': endorsement,
        'related_notes': related_notes,
    }
    
    return render(request, 'core/admin/endorsement_detail.html', context)


# ============================================
# RENEWAL ADMIN VIEWS
# ============================================

@admin_required
def admin_renewals(request):
    """Manage policy renewals"""
    renewals_list = PolicyRenewal.objects.select_related(
        'original_policy', 'user'
    ).all().order_by('-renewal_date')
    
    # Upcoming renewals (next 30 days)
    upcoming_renewals = renewals_list.filter(
        renewal_date__lte=timezone.now().date() + timezone.timedelta(days=30),
        status='pending'
    )
    
    # Filters
    status = request.GET.get('status')
    if status:
        renewals_list = renewals_list.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        renewals_list = renewals_list.filter(
            Q(renewal_number__icontains=search) |
            Q(original_policy__policy_number__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Stats
    total_renewals = renewals_list.count()
    pending_count = renewals_list.filter(status='pending').count()
    renewed_count = renewals_list.filter(status='renewed').count()
    lapsed_count = renewals_list.filter(status='lapsed').count()
    
    paginator = Paginator(renewals_list, 20)
    page = request.GET.get('page')
    renewals = paginator.get_page(page)
    
    context = {
        'renewals': renewals,
        'upcoming_renewals': upcoming_renewals,
        'total_renewals': total_renewals,
        'pending_count': pending_count,
        'renewed_count': renewed_count,
        'lapsed_count': lapsed_count,
        'status_filter': status,
        'search_query': search,
    }
    
    return render(request, 'core/admin/renewals.html', context)


from django.conf import settings as django_settings
@admin_required
@require_http_methods(["POST"])
def admin_send_renewal_reminder(request, renewal_id):
    """Send renewal reminder to customer with custom message"""
    import json
    from django.core.mail import send_mail, EmailMultiAlternatives
    from django.template.loader import render_to_string
    from apps.core.models import InsuranceSettings
    
    renewal = get_object_or_404(PolicyRenewal, id=renewal_id)
    
    try:
        data = json.loads(request.body)
        custom_message = data.get('message', '').strip()
        subject = data.get('subject', f'Policy Renewal Reminder - {renewal.original_policy.policy_number}')
    except:
        custom_message = ''
        subject = f'Policy Renewal Reminder - {renewal.original_policy.policy_number}'
    
    # Build email body
    if custom_message:
        email_body = custom_message
    else:
        email_body = f"""
Dear {renewal.user.get_full_name() or renewal.user.email},

Your insurance policy #{renewal.original_policy.policy_number} is due for renewal.

Renewal Date: {renewal.renewal_date}
Expiry Date: {renewal.expiry_date}
Renewal Premium: ₦{renewal.renewal_premium:,.2f}

Please login to your account to renew your policy and continue enjoying coverage.

Best regards,
Vehicle Insurance Pro Team
"""
    
    # Get email settings from InsuranceSettings
    try:
        email_settings = InsuranceSettings.get_settings()
        
        # Configure email backend dynamically if needed
        import smtplib
        from django.core.mail import get_connection
        
        if email_settings.email_host and email_settings.email_host_user and email_settings.email_host_password:
            # Use custom SMTP settings
            connection = get_connection(
                host=email_settings.email_host,
                port=email_settings.email_port,
                username=email_settings.email_host_user,
                password=email_settings.email_host_password,
                use_tls=email_settings.email_use_tls,
            )
            
            # Create HTML email
            html_content = render_to_string('core/emails/renewal_reminder.html', {
                'renewal': renewal,
                'user': renewal.user,
                'message': email_body.replace('\n', '<br>'),
                'subject': subject,
            })
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=email_body,
                from_email=email_settings.default_from_email or 'noreply@vehicleinsure.ng',
                to=[renewal.user.email],
                connection=connection,
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
        else:
            # Fallback to default Django email settings
            send_mail(
                subject,
                email_body,
                email_settings.default_from_email or 'noreply@vehicleinsure.ng',
                [renewal.user.email],
                fail_silently=False,
            )
            
    except Exception as e:
        logger.error(f"Email configuration error: {str(e)}")
        
        # Ultimate fallback - just create notification without email
        Notification.objects.create(
            user=renewal.user,
            title='Policy Renewal Reminder',
            message=f'Reminder: Your policy #{renewal.original_policy.policy_number} is due for renewal.',
            notification_type='policy_expiry',
            data={'renewal_id': str(renewal.id), 'policy_id': str(renewal.original_policy.id)}
        )
        
        renewal.reminder_sent = True
        renewal.reminder_sent_date = timezone.now()
        renewal.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Reminder recorded (email configuration pending). Customer will see notification.'
        })
    
    # Create notification for user
    Notification.objects.create(
        user=renewal.user,
        title='Policy Renewal Reminder',
        message=f'Reminder: Your policy #{renewal.original_policy.policy_number} is due for renewal.',
        notification_type='policy_expiry',
        data={'renewal_id': str(renewal.id), 'policy_id': str(renewal.original_policy.id)}
    )
    
    renewal.reminder_sent = True
    renewal.reminder_sent_date = timezone.now()
    renewal.save()
    
    return JsonResponse({'success': True, 'message': 'Reminder sent successfully!'})
    
    
    

# apps/core/admin_views.py - Add this API endpoint

@admin_required
@require_http_methods(["GET"])
def api_renewal_details(request, renewal_id):
    """API endpoint to get renewal details for reminder template"""
    renewal = get_object_or_404(PolicyRenewal, id=renewal_id)
    
    data = {
        'customer_name': renewal.user.get_full_name() or renewal.user.email,
        'customer_email': renewal.user.email,
        'policy_number': renewal.original_policy.policy_number,
        'renewal_date': renewal.renewal_date.strftime('%B %d, %Y'),
        'expiry_date': renewal.expiry_date.strftime('%B %d, %Y'),
        'renewal_premium': f"{renewal.renewal_premium:,.2f}",
    }
    
    return JsonResponse(data)


# ============================================
# INSTALLMENT PLAN ADMIN VIEWS
# ============================================

# apps/core/admin_views.py

@admin_required
def admin_installment_plans(request):
    """Admin view - Manage all installment plans"""
    plans_list = InstallmentPlan.objects.select_related(
        'policy', 'user', 'policy__vehicle'
    ).prefetch_related('installments').all().order_by('-created_at')
    
    # Summary stats
    total_plans = plans_list.count()
    active_plans = plans_list.filter(status='active').count()
    completed_plans = plans_list.filter(status='completed').count()
    defaulted_plans = plans_list.filter(status='defaulted').count()
    
    # Calculate total amounts
    total_premium = plans_list.aggregate(total=Sum('total_premium'))['total'] or Decimal('0')
    total_paid = Payment.objects.filter(
        status='completed',
        payment_details__has_key='installment_plan_id'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Filters
    status = request.GET.get('status')
    if status:
        plans_list = plans_list.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        plans_list = plans_list.filter(
            Q(plan_number__icontains=search) |
            Q(policy__policy_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    
    paginator = Paginator(plans_list, 20)
    page = request.GET.get('page')
    plans = paginator.get_page(page)
    
    context = {
        'plans': plans,
        'total_plans': total_plans,
        'active_plans': active_plans,
        'completed_plans': completed_plans,
        'defaulted_plans': defaulted_plans,
        'total_premium': total_premium,
        'total_paid': total_paid,
        'status_filter': status,
        'search_query': search,
    }
    
    return render(request, 'core/admin/installment_plans.html', context)


@admin_required
def admin_installment_plan_detail(request, plan_id):
    """Admin view - Installment plan details"""
    plan = get_object_or_404(InstallmentPlan.objects.select_related(
        'policy', 'user', 'policy__vehicle'
    ).prefetch_related('installments__payment'), id=plan_id)
    
    installments = plan.installments.all().select_related('payment').order_by('installment_number')
    
    # Calculate progress
    paid_count = installments.filter(status='paid').count()
    total_count = installments.count()
    progress_percentage = (paid_count / total_count * 100) if total_count > 0 else 0
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'mark_defaulted':
            plan.status = 'defaulted'
            plan.save()
            messages.warning(request, f'Plan {plan.plan_number} marked as defaulted.')
            
        elif action == 'mark_completed':
            plan.status = 'completed'
            plan.save()
            messages.success(request, f'Plan {plan.plan_number} marked as completed.')
            
        elif action == 'cancel_plan':
            plan.status = 'cancelled'
            plan.save()
            messages.info(request, f'Plan {plan.plan_number} cancelled.')
            
        elif action == 'reactivate':
            plan.status = 'active'
            plan.save()
            messages.success(request, f'Plan {plan.plan_number} reactivated.')
        
        return redirect('core:admin_installment_plan_detail', plan_id=plan.id)
    
    context = {
        'plan': plan,
        'installments': installments,
        'paid_count': paid_count,
        'total_count': total_count,
        'progress_percentage': progress_percentage,
        'policy': plan.policy,
    }
    
    return render(request, 'core/admin/installment_plan_detail.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_installment_action(request, installment_id):
    """Admin action on individual installment"""
    installment = get_object_or_404(Installment, id=installment_id)
    action = request.POST.get('action')
    
    try:
        if action == 'mark_paid':
            installment.status = 'paid'
            installment.paid_date = timezone.now()
            installment.amount_paid = installment.total_amount
            installment.save()
            
            plan = installment.installment_plan
            
            # Check if all installments are paid
            if not plan.installments.filter(status='pending').exists():
                plan.status = 'completed'
                plan.save()
            
            # Update next due date
            next_installment = plan.installments.filter(status='pending').order_by('due_date').first()
            if next_installment:
                plan.next_due_date = next_installment.due_date
                plan.save()
            
            return JsonResponse({'success': True, 'message': 'Installment marked as paid'})
            
        elif action == 'waive':
            installment.status = 'waived'
            installment.save()
            return JsonResponse({'success': True, 'message': 'Installment waived'})
            
        elif action == 'reset_pending':
            installment.status = 'pending'
            installment.paid_date = None
            installment.amount_paid = 0
            installment.save()
            return JsonResponse({'success': True, 'message': 'Installment reset to pending'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid action'})


@admin_required
@require_http_methods(["POST"])
def admin_installment_plan_action(request, plan_id):
    """Bulk action on installment plan"""
    plan = get_object_or_404(InstallmentPlan, id=plan_id)
    action = request.POST.get('action')
    
    if action == 'mark_defaulted':
        plan.status = 'defaulted'
        plan.save()
        return JsonResponse({'success': True, 'message': 'Plan marked as defaulted'})
    
    elif action == 'cancel':
        plan.status = 'cancelled'
        plan.save()
        return JsonResponse({'success': True, 'message': 'Plan cancelled'})
    
    return JsonResponse({'success': False, 'message': 'Invalid action'})


# ============================================
# CANCELLATION ADMIN VIEWS
# ============================================

@admin_required
def admin_cancellations(request):
    """Manage policy cancellations"""
    cancellations_list = PolicyCancellation.objects.select_related(
        'policy', 'user'
    ).all().order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        cancellations_list = cancellations_list.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        cancellations_list = cancellations_list.filter(
            Q(cancellation_number__icontains=search) |
            Q(policy__policy_number__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Stats
    total_cancellations = cancellations_list.count()
    pending_count = cancellations_list.filter(status='pending').count()
    approved_count = cancellations_list.filter(status='approved').count()
    processed_count = cancellations_list.filter(status='processed').count()
    total_refunds = cancellations_list.filter(status__in=['approved', 'processed', 'refunded']).aggregate(
        Sum('refund_amount')
    )['refund_amount__sum'] or 0
    
    paginator = Paginator(cancellations_list, 20)
    page = request.GET.get('page')
    cancellations = paginator.get_page(page)
    
    context = {
        'cancellations': cancellations,
        'total_cancellations': total_cancellations,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'processed_count': processed_count,
        'total_refunds': total_refunds,
        'status_filter': status,
        'search_query': search,
    }
    
    return render(request, 'core/admin/cancellations.html', context)


@admin_required
def admin_cancellation_detail(request, cancellation_id):
    """View and process cancellation"""
    cancellation = get_object_or_404(PolicyCancellation, id=cancellation_id)
    
    if request.method == 'POST':
        form = CancellationApprovalForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            
            if action == 'approve':
                cancellation.status = 'approved'
                cancellation.cancellation_fee = form.cleaned_data.get('cancellation_fee', 0)
                cancellation.approved_by = request.user
                cancellation.approved_date = timezone.now()
                cancellation.calculate_refund()
                cancellation.save()
                
                messages.success(request, f'Cancellation approved! Refund amount: ₦{cancellation.refund_amount:,.2f}')
            
            elif action == 'reject':
                cancellation.status = 'rejected'
                cancellation.rejection_reason = form.cleaned_data['rejection_reason']
                cancellation.save()
                
                messages.warning(request, 'Cancellation rejected!')
            
            # Send notification
            Notification.objects.create(
                user=cancellation.user,
                title=f'Cancellation Request {cancellation.get_status_display()}',
                message=f'Your cancellation request #{cancellation.cancellation_number} has been {cancellation.status}.',
                notification_type='system_alert',
                data={'cancellation_id': str(cancellation.id)}
            )
            
            return redirect('core:admin_cancellations')
    else:
        form = CancellationApprovalForm()
    
    return render(request, 'core/admin/cancellation_detail.html', {
        'cancellation': cancellation,
        'form': form
    })


@admin_required
@require_http_methods(["POST"])
def admin_process_refund(request, cancellation_id):
    """Process refund for approved cancellation"""
    cancellation = get_object_or_404(PolicyCancellation, id=cancellation_id, status='approved')
    
    refund_method = request.POST.get('refund_method')
    refund_reference = request.POST.get('refund_reference')
    
    # Process the cancellation
    success = cancellation.process_cancellation()
    
    if success:
        cancellation.refund_method = refund_method
        cancellation.refund_reference = refund_reference
        cancellation.refund_date = timezone.now()
        cancellation.status = 'refunded'
        cancellation.save()
        
        return JsonResponse({'success': True, 'message': 'Refund processed successfully!'})
    
    return JsonResponse({'success': False, 'message': 'Failed to process refund'})


# ============================================
# UTILITY FUNCTIONS
# ============================================

def generate_note_document(note):
    """Generate PDF for debit/credit note"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    from django.core.files.base import ContentFile
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"{note.get_note_type_display().upper()}")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, 730, f"Note Number: {note.note_number}")
    p.drawString(100, 710, f"Policy Number: {note.policy.policy_number}")
    p.drawString(100, 690, f"Customer: {note.user.get_full_name() or note.user.email}")
    p.drawString(100, 670, f"Issue Date: {note.issue_date}")
    
    if note.due_date:
        p.drawString(100, 650, f"Due Date: {note.due_date}")
    
    # Amounts
    p.drawString(100, 610, f"Base Amount: ₦{note.base_amount:,.2f}")
    p.drawString(100, 590, f"Tax Amount: ₦{note.tax_amount:,.2f}")
    p.drawString(100, 570, f"Total Amount: ₦{note.total_amount:,.2f}")
    
    # Description
    p.drawString(100, 530, "Description:")
    p.drawString(120, 510, note.description)
    
    p.save()
    
    buffer.seek(0)
    note.note_document.save(
        f"{note.note_number}.pdf",
        ContentFile(buffer.getvalue()),
        save=True
    )











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
    vehicles_list = Vehicle.objects.select_related(
        'user', 'created_by', 'updated_by'
    ).prefetch_related(
        'policies'
    ).all().order_by('-created_at')
    
    # Update insurance status for all vehicles (sync with policies)
    for vehicle in vehicles_list:
        vehicle.update_insurance_status()
    
    # Refresh the queryset after updates
    vehicles_list = Vehicle.objects.select_related(
        'user', 'created_by', 'updated_by'
    ).prefetch_related(
        'policies'
    ).all().order_by('-created_at')
    
    # Summary statistics
    total_vehicles = vehicles_list.count()
    insured_vehicles = vehicles_list.filter(is_insured=True).count()
    uninsured_vehicles = vehicles_list.filter(is_insured=False).count()
    
    # Count by type
    vehicle_types = vehicles_list.values('vehicle_type').annotate(count=Count('id'))
    type_counts = {vt['vehicle_type']: vt['count'] for vt in vehicle_types}
    
    # Filter by vehicle type
    vehicle_type = request.GET.get('vehicle_type')
    vehicle_type_filter = vehicle_type
    if vehicle_type:
        vehicles_list = vehicles_list.filter(vehicle_type=vehicle_type)
    
    # Filter by insurance status
    is_insured = request.GET.get('is_insured')
    is_insured_filter = is_insured
    if is_insured is not None and is_insured != '':
        vehicles_list = vehicles_list.filter(is_insured=is_insured == 'true')
    
    # Filter by user
    user_id = request.GET.get('user_id')
    user_filter = user_id
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
        'vehicle_type_filter': vehicle_type_filter,
        'is_insured_filter': is_insured_filter,
        'user_filter': user_filter,
        'search_query': search,
    }
    
    return render(request, 'core/admin/vehicles.html', context)


@admin_required
def admin_vehicle_detail(request, vehicle_id):
    """Admin view to see vehicle details"""
    vehicle = get_object_or_404(
        Vehicle.objects.select_related('user', 'created_by', 'updated_by').prefetch_related('policies'),
        id=vehicle_id
    )
    
    # Sync insurance status
    vehicle.update_insurance_status()
    
    # Get related policies and claims
    policies = vehicle.policies.all().order_by('-created_at')
    claims = Claim.objects.filter(policy__vehicle=vehicle).order_by('-created_at')
    
    # Get active policy
    active_policy = vehicle.active_policy
    
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
        'active_policy': active_policy,
    }
    
    return render(request, 'core/admin/vehicle_detail.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_vehicle_action(request, vehicle_id, action):
    """Handle vehicle actions"""
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    
    try:
        if action == 'toggle_insured':
            # Check if there's an active policy before allowing manual toggle
            active_policy = vehicle.active_policy
            if active_policy:
                return JsonResponse({
                    'success': False, 
                    'message': f'Cannot manually change insurance status. Vehicle has active policy: {active_policy.policy_number}'
                })
            
            vehicle.is_insured = not vehicle.is_insured
            vehicle.updated_by = request.user
            vehicle.save()
            status = 'insured' if vehicle.is_insured else 'uninsured'
            return JsonResponse({'success': True, 'message': f'Vehicle marked as {status}'})
            
        elif action == 'delete':
            # Check if vehicle has active policies
            if vehicle.policies.filter(status='active').exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'Cannot delete vehicle with active insurance policies.'
                })
            
            reg_number = vehicle.registration_number
            vehicle.delete()
            return JsonResponse({'success': True, 'message': f'Vehicle {reg_number} deleted successfully'})
            
        elif action == 'sync_insurance':
            vehicle.update_insurance_status()
            status = 'insured' if vehicle.is_insured else 'uninsured'
            return JsonResponse({'success': True, 'message': f'Insurance status synced: {status}'})
            
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














# apps/core/admin_views.py - Add these views
from django.db.models import Sum
from .models import (
    User, AgentProfile, AgentReferral, Commission, InsurancePolicy, 
    Payment, Notification, Vehicle
)
from .forms import AgentRegistrationForm, AgentProfileForm

@admin_required
def admin_agents(request):
    """Manage agents"""
    agents = User.objects.filter(role='agent').select_related('agent_profile').order_by('-date_joined')
    
    # Annotate with stats
    for agent in agents:
        agent.customer_count = AgentReferral.objects.filter(agent=agent).count()
        if hasattr(agent, 'agent_profile'):
            agent.total_sales = agent.agent_profile.total_sales
            agent.total_commission = agent.agent_profile.total_commission_earned
        else:
            agent.total_sales = 0
            agent.total_commission = Decimal('0')
    
    # Filters
    is_active = request.GET.get('is_active')
    if is_active:
        agents = agents.filter(is_active=is_active == 'true')
    
    is_verified = request.GET.get('is_verified')
    if is_verified:
        agents = agents.filter(agent_profile__is_verified=(is_verified == 'true'))
    
    # Search
    search = request.GET.get('search')
    if search:
        agents = agents.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(agent_profile__agent_code__icontains=search) |
            Q(agent_profile__business_name__icontains=search)
        )
    
    # Stats
    total_agents = agents.count()
    active_agents = agents.filter(is_active=True).count()
    verified_agents = agents.filter(agent_profile__is_verified=True).count()
    total_commission_paid = Commission.objects.filter(
        agent__in=agents, status='paid'
    ).aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
    
    paginator = Paginator(agents, 20)
    page = request.GET.get('page')
    agents = paginator.get_page(page)
    
    context = {
        'agents': agents,
        'total_agents': total_agents,
        'active_agents': active_agents,
        'verified_agents': verified_agents,
        'total_commission_paid': total_commission_paid,
        'search_query': search,
        'is_active_filter': is_active,
        'is_verified_filter': is_verified,
    }
    
    return render(request, 'core/admin/agents.html', context)


@admin_required
def admin_agent_create(request):
    """Create new agent with commission structure integration"""
    if request.method == 'POST':
        form = AgentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'agent'
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Determine commission rate
            use_custom_rate = form.cleaned_data.get('use_custom_rate', False)
            custom_rate = form.cleaned_data.get('commission_rate')
            
            if use_custom_rate and custom_rate:
                commission_rate = custom_rate
                override_structure = True
            else:
                # Get default rate from active commission structure
                commission_rate = get_default_commission_rate(form.cleaned_data['agent_type'])
                override_structure = False
            
            # Create agent profile
            profile, created = AgentProfile.objects.get_or_create(
                user=user,
                defaults={
                    'agent_type': form.cleaned_data['agent_type'],
                    'commission_rate': commission_rate,
                }
            )
            
            if not created:
                profile.agent_type = form.cleaned_data['agent_type']
                profile.commission_rate = commission_rate
                profile.save()
            
            # If using custom rate, create an override record
            if override_structure:
                AgentCommissionOverride.objects.create(
                    agent=user,
                    policy_type='comprehensive',  # Default for all policy types
                    commission_rate=custom_rate,
                    reason='Custom rate set at agent creation',
                    effective_from=timezone.now().date(),
                    created_by=request.user
                )
                AgentCommissionOverride.objects.create(
                    agent=user,
                    policy_type='third_party',
                    commission_rate=custom_rate,
                    reason='Custom rate set at agent creation',
                    effective_from=timezone.now().date(),
                    created_by=request.user
                )
                AgentCommissionOverride.objects.create(
                    agent=user,
                    policy_type='standalone',
                    commission_rate=custom_rate,
                    reason='Custom rate set at agent creation',
                    effective_from=timezone.now().date(),
                    created_by=request.user
                )
                AgentCommissionOverride.objects.create(
                    agent=user,
                    policy_type='personal_accident',
                    commission_rate=custom_rate,
                    reason='Custom rate set at agent creation',
                    effective_from=timezone.now().date(),
                    created_by=request.user
                )
            
            messages.success(request, 
                f'Agent {user.email} created successfully! '
                f'Commission Rate: {commission_rate}% '
                f'({"Custom" if override_structure else "Structure-based"})'
            )
            return redirect('core:admin_agent_detail', agent_id=user.id)
    else:
        form = AgentRegistrationForm()
    
    # Get active commission structures for display
    active_structures = CommissionStructure.objects.filter(
        is_active=True,
        effective_from__lte=timezone.now().date()
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=timezone.now().date())
    ).order_by('policy_type', 'agent_type')
    
    context = {
        'form': form,
        'active_structures': active_structures,
    }
    
    return render(request, 'core/admin/agent_create.html', context)


def get_default_commission_rate(agent_type='individual', policy_type='comprehensive'):
    """Get default commission rate from active structure"""
    today = timezone.now().date()
    
    structure = CommissionStructure.objects.filter(
        policy_type=policy_type,
        agent_type__in=[agent_type, 'all'],
        is_active=True,
        effective_from__lte=today
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    ).order_by('-priority', '-effective_from').first()
    
    if structure:
        return structure.base_commission_rate
    
    # Default fallback
    return Decimal('10.00')


@admin_required
def admin_agent_detail(request, agent_id):
    """View agent details"""
    agent = get_object_or_404(User, id=agent_id, role='agent')
    profile, created = AgentProfile.objects.get_or_create(user=agent)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            profile.agent_type = request.POST.get('agent_type', profile.agent_type)
            profile.commission_rate = Decimal(request.POST.get('commission_rate', profile.commission_rate))
            profile.bonus_eligible = request.POST.get('bonus_eligible') == 'on'
            profile.business_name = request.POST.get('business_name', '')
            profile.business_address = request.POST.get('business_address', '')
            profile.business_phone = request.POST.get('business_phone', '')
            profile.tax_id = request.POST.get('tax_id', '')
            profile.bank_name = request.POST.get('bank_name', '')
            profile.bank_account_name = request.POST.get('bank_account_name', '')
            profile.bank_account_number = request.POST.get('bank_account_number', '')
            profile.bank_sort_code = request.POST.get('bank_sort_code', '')
            profile.supervisor_id = request.POST.get('supervisor') or None
            profile.save()
            messages.success(request, 'Agent profile updated successfully!')
        
        elif action == 'verify_agent':
            profile.is_verified = True
            profile.save()
            messages.success(request, 'Agent verified successfully!')
        
        elif action == 'toggle_active':
            agent.is_active = not agent.is_active
            agent.save()
            profile.is_active = agent.is_active
            profile.save()
            messages.success(request, f'Agent {"activated" if agent.is_active else "deactivated"} successfully!')
        
        elif action == 'add_bonus':
            bonus_amount = Decimal(request.POST.get('bonus_amount', 0))
            bonus_reason = request.POST.get('bonus_reason', '')
            
            if bonus_amount > 0:
                Commission.objects.create(
                    agent=agent,
                    commission_type='bonus',
                    commission_rate=0,
                    bonus_amount=bonus_amount,
                    bonus_reason=bonus_reason,
                    total_commission=bonus_amount,
                    earned_date=timezone.now().date(),
                    status='approved',
                    approved_by=request.user,
                    approved_date=timezone.now()
                )
                profile.update_performance_metrics()
                messages.success(request, f'Bonus of ₦{bonus_amount:,.2f} added successfully!')
        
        elif action == 'reset_password':
            new_password = request.POST.get('new_password')
            if new_password and len(new_password) >= 8:
                agent.set_password(new_password)
                agent.save()
                messages.success(request, 'Password reset successfully!')
            else:
                messages.error(request, 'Password must be at least 8 characters.')
        
        return redirect('core:admin_agent_detail', agent_id=agent.id)
    
    # Get agent's customers
    customers = AgentReferral.objects.filter(agent=agent).select_related('customer').order_by('-created_at')
    
    # Get policies from customers
    customer_ids = customers.values_list('customer_id', flat=True)
    policies = InsurancePolicy.objects.filter(user_id__in=customer_ids).select_related(
        'user', 'vehicle'
    ).order_by('-created_at')
    
    # Get commissions
    commissions = Commission.objects.filter(agent=agent).order_by('-earned_date')
    
    # Commission summary
    commission_summary = profile.get_commission_summary() if profile else {}
    
    # Supervisors (admin/support users)
    supervisors = User.objects.filter(role__in=['admin', 'support'], is_active=True)
    
    context = {
        'agent': agent,
        'profile': profile,
        'customers': customers,
        'policies': policies,
        'commissions': commissions,
        'commission_summary': commission_summary,
        'supervisors': supervisors,
    }
    
    return render(request, 'core/admin/agent_detail.html', context)


@admin_required
def admin_agent_commissions(request):
    """Manage all agent commissions"""
    commissions_list = Commission.objects.select_related(
        'agent', 'policy', 'policy__user', 'approved_by'
    ).all().order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    status_filter = status
    if status:
        commissions_list = commissions_list.filter(status=status)
    
    agent_id = request.GET.get('agent')
    agent_filter = agent_id
    if agent_id:
        commissions_list = commissions_list.filter(agent_id=agent_id)
    
    commission_type = request.GET.get('type')
    type_filter = commission_type
    if commission_type:
        commissions_list = commissions_list.filter(commission_type=commission_type)
    
    # Date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        commissions_list = commissions_list.filter(earned_date__gte=date_from)
    if date_to:
        commissions_list = commissions_list.filter(earned_date__lte=date_to)
    
    # Search
    search = request.GET.get('search')
    if search:
        commissions_list = commissions_list.filter(
            Q(commission_number__icontains=search) |
            Q(agent__email__icontains=search) |
            Q(agent__first_name__icontains=search) |
            Q(agent__last_name__icontains=search) |
            Q(policy__policy_number__icontains=search)
        )
    
    # Stats
    total_commissions = commissions_list.count()
    total_amount = commissions_list.aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
    pending_amount = commissions_list.filter(status='pending').aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
    approved_amount = commissions_list.filter(status='approved').aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
    paid_amount = commissions_list.filter(status='paid').aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
    
    # Agents for filter
    agents = User.objects.filter(role='agent')
    
    paginator = Paginator(commissions_list, 20)
    page = request.GET.get('page')
    commissions = paginator.get_page(page)
    
    context = {
        'commissions': commissions,
        'agents': agents,
        'total_commissions': total_commissions,
        'total_amount': total_amount,
        'pending_amount': pending_amount,
        'approved_amount': approved_amount,
        'paid_amount': paid_amount,
        'status_filter': status_filter,
        'agent_filter': agent_filter,
        'type_filter': type_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search,
    }
    
    return render(request, 'core/admin/agent_commissions.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_approve_commission(request, commission_id):
    """Approve a single commission"""
    commission = get_object_or_404(Commission, id=commission_id)
    
    if commission.status == 'pending':
        commission.status = 'approved'
        commission.approved_by = request.user
        commission.approved_date = timezone.now()
        commission.save()
        
        # Notify agent
        Notification.objects.create(
            user=commission.agent,
            title='Commission Approved',
            message=f'Your commission of ₦{commission.total_commission:,.2f} has been approved.',
            notification_type='payment_confirmation',
            data={'commission_id': str(commission.id)}
        )
        
        return JsonResponse({'success': True, 'message': 'Commission approved!'})
    
    return JsonResponse({'success': False, 'message': 'Commission cannot be approved'})


@admin_required
@require_http_methods(["POST"])
def admin_mark_commission_paid(request, commission_id):
    """Mark a single commission as paid"""
    commission = get_object_or_404(Commission, id=commission_id)
    
    if commission.status == 'approved':
        data = json.loads(request.body) if request.body else {}
        payment_reference = data.get('payment_reference', '')
        payment_method = data.get('payment_method', 'Bank Transfer')
        
        commission.status = 'paid'
        commission.paid_date = timezone.now()
        commission.payment_reference = payment_reference
        commission.payment_method = payment_method
        commission.save()
        
        # Update agent profile
        if hasattr(commission.agent, 'agent_profile'):
            commission.agent.agent_profile.update_performance_metrics()
        
        # Notify agent
        Notification.objects.create(
            user=commission.agent,
            title='Commission Paid',
            message=f'Your commission of ₦{commission.total_commission:,.2f} has been paid.',
            notification_type='payment_confirmation',
            data={'commission_id': str(commission.id)}
        )
        
        return JsonResponse({'success': True, 'message': 'Commission marked as paid!'})
    
    return JsonResponse({'success': False, 'message': 'Commission cannot be marked as paid'})


@admin_required
@require_http_methods(["POST"])
def admin_bulk_approve_commissions(request):
    """Bulk approve commissions"""
    data = json.loads(request.body)
    commission_ids = data.get('commission_ids', [])
    
    if commission_ids:
        commissions = Commission.objects.filter(id__in=commission_ids, status='pending')
        count = commissions.count()
        
        for commission in commissions:
            commission.status = 'approved'
            commission.approved_by = request.user
            commission.approved_date = timezone.now()
            commission.save()
            
            # Notify agent
            Notification.objects.create(
                user=commission.agent,
                title='Commission Approved',
                message=f'Your commission of ₦{commission.total_commission:,.2f} has been approved.',
                notification_type='payment_confirmation',
                data={'commission_id': str(commission.id)}
            )
        
        return JsonResponse({'success': True, 'message': f'{count} commissions approved!'})
    
    return JsonResponse({'success': False, 'message': 'No commissions selected'})


@admin_required
@require_http_methods(["POST"])
def admin_bulk_pay_commissions(request):
    """Bulk mark commissions as paid"""
    data = json.loads(request.body)
    commission_ids = data.get('commission_ids', [])
    payment_reference = data.get('payment_reference', '')
    payment_method = data.get('payment_method', 'Bank Transfer')
    
    if commission_ids:
        commissions = Commission.objects.filter(id__in=commission_ids, status='approved')
        count = commissions.count()
        total_amount = sum(c.total_commission for c in commissions)
        
        for commission in commissions:
            commission.status = 'paid'
            commission.paid_date = timezone.now()
            commission.payment_reference = payment_reference
            commission.payment_method = payment_method
            commission.save()
            
            # Update agent profile
            if hasattr(commission.agent, 'agent_profile'):
                commission.agent.agent_profile.update_performance_metrics()
            
            # Notify agent
            Notification.objects.create(
                user=commission.agent,
                title='Commission Paid',
                message=f'Your commission of ₦{commission.total_commission:,.2f} has been paid.',
                notification_type='payment_confirmation',
                data={'commission_id': str(commission.id)}
            )
        
        return JsonResponse({
            'success': True, 
            'message': f'{count} commissions marked as paid! Total: ₦{total_amount:,.2f}'
        })
    
    return JsonResponse({'success': False, 'message': 'No commissions selected'})


@admin_required
@require_http_methods(["POST"])
def admin_reject_commission(request, commission_id):
    """Reject a commission"""
    commission = get_object_or_404(Commission, id=commission_id)
    data = json.loads(request.body) if request.body else {}
    reason = data.get('reason', 'Not specified')
    
    if commission.status == 'pending':
        commission.status = 'cancelled'
        commission.notes = f'Rejected: {reason}'
        commission.save()
        
        # Notify agent
        Notification.objects.create(
            user=commission.agent,
            title='Commission Rejected',
            message=f'Your commission of ₦{commission.total_commission:,.2f} was rejected. Reason: {reason}',
            notification_type='payment_confirmation',
            data={'commission_id': str(commission.id)}
        )
        
        return JsonResponse({'success': True, 'message': 'Commission rejected!'})
    
    return JsonResponse({'success': False, 'message': 'Commission cannot be rejected'})









# ============================================
# COMMISSION ADMIN VIEWS
# ============================================

@admin_required
def admin_commissions(request):
    """Manage agent commissions"""
    commissions_list = Commission.objects.select_related(
        'agent', 'policy'
    ).all().order_by('-earned_date')
    
    # Filters
    status = request.GET.get('status')
    if status:
        commissions_list = commissions_list.filter(status=status)
    
    agent_id = request.GET.get('agent')
    if agent_id:
        commissions_list = commissions_list.filter(agent_id=agent_id)
    
    # Search
    search = request.GET.get('search')
    if search:
        commissions_list = commissions_list.filter(
            Q(commission_number__icontains=search) |
            Q(agent__email__icontains=search) |
            Q(policy__policy_number__icontains=search)
        )
    
    # Stats
    total_commissions = commissions_list.count()
    pending_count = commissions_list.filter(status='pending').count()
    approved_count = commissions_list.filter(status='approved').count()
    paid_count = commissions_list.filter(status='paid').count()
    total_amount = commissions_list.aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    paid_amount = commissions_list.filter(status='paid').aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    
    # Agents for filter
    agents = User.objects.filter(role='agent')
    
    paginator = Paginator(commissions_list, 20)
    page = request.GET.get('page')
    commissions = paginator.get_page(page)
    
    context = {
        'commissions': commissions,
        'agents': agents,
        'total_commissions': total_commissions,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'status_filter': status,
        'agent_filter': agent_id,
        'search_query': search,
    }
    
    return render(request, 'core/admin/commissions.html', context)


# apps/core/admin_views.py - Updated Commission Views

@admin_required
def admin_commission_structures(request):
    """Manage dynamic commission structures"""
    structures_list = CommissionStructure.objects.all().order_by('-priority', '-effective_from')
    
    # Stats
    active_structures = structures_list.filter(is_active=True).count()
    comprehensive_structures = structures_list.filter(policy_type='comprehensive', is_active=True).count()
    third_party_structures = structures_list.filter(policy_type='third_party', is_active=True).count()
    
    # Filters
    policy_type = request.GET.get('policy_type')
    if policy_type:
        structures_list = structures_list.filter(policy_type=policy_type)
    
    agent_type = request.GET.get('agent_type')
    if agent_type:
        structures_list = structures_list.filter(agent_type=agent_type)
    
    is_active = request.GET.get('is_active')
    if is_active:
        structures_list = structures_list.filter(is_active=is_active == 'true')
    
    paginator = Paginator(structures_list, 20)
    page = request.GET.get('page')
    structures = paginator.get_page(page)
    
    context = {
        'structures': structures,
        'active_structures': active_structures,
        'comprehensive_structures': comprehensive_structures,
        'third_party_structures': third_party_structures,
        'policy_type_filter': policy_type,
        'agent_type_filter': agent_type,
        'is_active_filter': is_active,
    }
    
    return render(request, 'core/admin/commission_structures.html', context)


@admin_required
def admin_commission_structure_create(request):
    """Create new commission structure"""
    if request.method == 'POST':
        form = CommissionStructureForm(request.POST)
        if form.is_valid():
            structure = form.save(commit=False)
            structure.created_by = request.user
            structure.save()
            messages.success(request, f'Commission structure "{structure.name}" created successfully!')
            return redirect('core:admin_commission_structures')
    else:
        form = CommissionStructureForm()
    
    context = {
        'form': form,
        'title': 'Create Commission Structure',
    }
    
    return render(request, 'core/admin/commission_structure_form.html', context)


@admin_required
def admin_commission_structure_edit(request, structure_id):
    """Edit commission structure"""
    structure = get_object_or_404(CommissionStructure, id=structure_id)
    
    if request.method == 'POST':
        form = CommissionStructureForm(request.POST, instance=structure)
        if form.is_valid():
            structure = form.save(commit=False)
            structure.updated_by = request.user
            structure.save()
            messages.success(request, f'Commission structure "{structure.name}" updated successfully!')
            return redirect('core:admin_commission_structures')
    else:
        form = CommissionStructureForm(instance=structure)
    
    context = {
        'form': form,
        'structure': structure,
        'title': f'Edit: {structure.name}',
    }
    
    return render(request, 'core/admin/commission_structure_form.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_commission_structure_delete(request, structure_id):
    """Delete commission structure"""
    structure = get_object_or_404(CommissionStructure, id=structure_id)
    structure.delete()
    return JsonResponse({'success': True, 'message': 'Commission structure deleted!'})


@admin_required
@require_http_methods(["POST"])
def admin_commission_structure_toggle(request, structure_id):
    """Toggle active status of commission structure"""
    structure = get_object_or_404(CommissionStructure, id=structure_id)
    structure.is_active = not structure.is_active
    structure.save()
    return JsonResponse({
        'success': True, 
        'is_active': structure.is_active,
        'message': f'Structure {"activated" if structure.is_active else "deactivated"}!'
    })


@admin_required
def admin_agent_overrides(request):
    """Manage agent-specific commission overrides"""
    overrides_list = AgentCommissionOverride.objects.select_related('agent', 'created_by').all().order_by('-effective_from')
    
    # Filters
    agent_id = request.GET.get('agent')
    if agent_id:
        overrides_list = overrides_list.filter(agent_id=agent_id)
    
    is_active = request.GET.get('is_active')
    if is_active:
        overrides_list = overrides_list.filter(is_active=is_active == 'true')
    
    # Stats
    active_overrides = overrides_list.filter(is_active=True).count()
    
    # Agents for filter
    agents = User.objects.filter(role='agent', is_active=True)
    
    paginator = Paginator(overrides_list, 20)
    page = request.GET.get('page')
    overrides = paginator.get_page(page)
    
    context = {
        'overrides': overrides,
        'agents': agents,
        'active_overrides': active_overrides,
        'agent_filter': agent_id,
        'is_active_filter': is_active,
    }
    
    return render(request, 'core/admin/agent_overrides.html', context)


@admin_required
def admin_agent_override_create(request):
    """Create agent commission override"""
    if request.method == 'POST':
        form = AgentCommissionOverrideForm(request.POST)
        if form.is_valid():
            override = form.save(commit=False)
            override.created_by = request.user
            override.save()
            messages.success(request, f'Commission override created successfully!')
            return redirect('core:admin_agent_overrides')
    else:
        form = AgentCommissionOverrideForm()
    
    context = {
        'form': form,
        'title': 'Create Agent Commission Override',
    }
    
    return render(request, 'core/admin/agent_override_form.html', context)


@admin_required
def admin_agent_override_edit(request, override_id):
    """Edit agent commission override"""
    override = get_object_or_404(AgentCommissionOverride, id=override_id)
    
    if request.method == 'POST':
        form = AgentCommissionOverrideForm(request.POST, instance=override)
        if form.is_valid():
            override = form.save()
            messages.success(request, f'Commission override updated successfully!')
            return redirect('core:admin_agent_overrides')
    else:
        form = AgentCommissionOverrideForm(instance=override)
    
    context = {
        'form': form,
        'override': override,
        'title': 'Edit Commission Override',
    }
    
    return render(request, 'core/admin/agent_override_form.html', context)


@admin_required
@require_http_methods(["POST"])
def admin_agent_override_delete(request, override_id):
    """Delete agent commission override"""
    override = get_object_or_404(AgentCommissionOverride, id=override_id)
    override.delete()
    return JsonResponse({'success': True, 'message': 'Commission override deleted!'})


@admin_required
@require_http_methods(["POST"])
def admin_agent_override_toggle(request, override_id):
    """Toggle active status of agent override"""
    override = get_object_or_404(AgentCommissionOverride, id=override_id)
    override.is_active = not override.is_active
    override.save()
    return JsonResponse({
        'success': True, 
        'is_active': override.is_active,
        'message': f'Override {"activated" if override.is_active else "deactivated"}!'
    })


@admin_required
@require_http_methods(["POST"])
def admin_approve_commission(request, commission_id):
    """Approve commission for payment"""
    commission = get_object_or_404(Commission, id=commission_id)
    
    commission.status = 'approved'
    commission.approved_by = request.user
    commission.approved_date = timezone.now()
    commission.save()
    
    return JsonResponse({'success': True, 'message': 'Commission approved!'})


@admin_required
@require_http_methods(["POST"])
def admin_mark_commission_paid(request, commission_id):
    """Mark commission as paid"""
    commission = get_object_or_404(Commission, id=commission_id)
    
    payment_reference = request.POST.get('payment_reference', '')
    
    commission.status = 'paid'
    commission.paid_date = timezone.now()
    commission.payment_reference = payment_reference
    commission.save()
    
    # Notify agent
    Notification.objects.create(
        user=commission.agent,
        title='Commission Paid',
        message=f'Your commission of ₦{commission.total_commission:,.2f} has been paid.',
        notification_type='payment_confirmation',
        data={'commission_id': str(commission.id)}
    )
    
    return JsonResponse({'success': True, 'message': 'Commission marked as paid!'})
