# apps/core/agent_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from datetime import timedelta
import json
from django.db.models import Sum

from .models import (
    User, AgentProfile, AgentReferral, Commission, InsurancePolicy, 
    Payment, Notification, Vehicle, Claim
)
from .forms import AgentProfileForm, AgentCustomerForm
from .decorators import agent_required


def is_agent(user):
    return user.is_authenticated and user.role == 'agent'


@login_required
@agent_required
def agent_dashboard(request):
    """Agent dashboard view"""
    agent = request.user
    profile, created = AgentProfile.objects.get_or_create(user=agent)
    
    # Get downline customers through AgentReferral
    referrals = AgentReferral.objects.filter(agent=agent).select_related('customer')
    customer_count = referrals.count()
    customer_ids = referrals.values_list('customer_id', flat=True)
    
    # Get policies from downline customers
    policies = InsurancePolicy.objects.filter(user_id__in=customer_ids).select_related('user', 'vehicle')
    active_policies = policies.filter(status='active')
    
    # Recent policies
    recent_policies = policies.order_by('-created_at')[:10]
    
    # Commission summary
    commissions = Commission.objects.filter(agent=agent)
    total_earned = commissions.filter(status__in=['approved', 'paid']).aggregate(
        total=Sum('total_commission')
    )['total'] or Decimal('0')
    total_paid = commissions.filter(status='paid').aggregate(
        total=Sum('total_commission')
    )['total'] or Decimal('0')
    pending_commission = commissions.filter(status='pending').aggregate(
        total=Sum('total_commission')
    )['total'] or Decimal('0')
    
    # Monthly stats
    today = timezone.now().date()
    month_start = today.replace(day=1)
    monthly_sales = policies.filter(created_at__date__gte=month_start).count()
    monthly_premium = policies.filter(created_at__date__gte=month_start).aggregate(
        total=Sum('premium_amount')
    )['total'] or Decimal('0')
    
    # Recent commissions
    recent_commissions = commissions.select_related('policy', 'policy__user').order_by('-created_at')[:10]
    
    # Referral link
    referral_link = f"{request.build_absolute_uri('/')}register/?ref={profile.agent_code}"
    
    context = {
        'profile': profile,
        'customer_count': customer_count,
        'total_policies': policies.count(),
        'active_policies': active_policies.count(),
        'total_earned': total_earned,
        'total_paid': total_paid,
        'pending_commission': pending_commission,
        'monthly_sales': monthly_sales,
        'monthly_premium': monthly_premium,
        'recent_policies': recent_policies,
        'recent_commissions': recent_commissions,
        'referral_link': referral_link,
    }
    
    return render(request, 'core/agent/dashboard.html', context)


@login_required
@agent_required
def agent_customers(request):
    """View customers registered under this agent"""
    agent = request.user
    
    # Get downline customers
    referrals = AgentReferral.objects.filter(agent=agent).select_related('customer')
    customer_ids = referrals.values_list('customer_id', flat=True)
    customers = User.objects.filter(id__in=customer_ids).order_by('-date_joined')
    
    # Search
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone_number__icontains=search)
        )
    
    # Annotate with policy counts
    for customer in customers:
        customer.policy_count = InsurancePolicy.objects.filter(user=customer).count()
        customer.active_count = InsurancePolicy.objects.filter(user=customer, status='active').count()
        customer.total_premium = InsurancePolicy.objects.filter(user=customer).aggregate(
            total=Sum('premium_amount')
        )['total'] or Decimal('0')
        customer.referral = referrals.get(customer=customer)
    
    # Add customer form
    form = AgentCustomerForm()
    
    if request.method == 'POST' and request.POST.get('action') == 'add_customer':
        form = AgentCustomerForm(request.POST)
        if form.is_valid():
            # Create customer account
            customer = User.objects.create(
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                phone_number=form.cleaned_data['phone_number'],
                role='customer',
                referred_by=agent,
                is_active=True
            )
            customer.set_password(User.objects.make_random_password())
            customer.save()
            
            # Create referral record
            profile = AgentProfile.objects.get(user=agent)
            AgentReferral.objects.create(
                agent=agent,
                customer=customer,
                referral_code=profile.agent_code,
                notes=form.cleaned_data['notes']
            )
            
            messages.success(request, f'Customer {customer.email} added successfully!')
            return redirect('core:agent_customers')
    
    paginator = Paginator(customers, 20)
    page = request.GET.get('page')
    customers = paginator.get_page(page)
    
    context = {
        'customers': customers,
        'total_customers': referrals.count(),
        'search_query': search,
        'form': form,
    }
    
    return render(request, 'core/agent/customers.html', context)


@login_required
@agent_required
def agent_customer_detail(request, customer_id):
    """View customer details"""
    agent = request.user
    from django.db.models import Sum
    from decimal import Decimal
    
    # Verify customer belongs to this agent
    referral = get_object_or_404(AgentReferral, agent=agent, customer_id=customer_id)
    customer = referral.customer
    
    # Get customer's policies
    policies = InsurancePolicy.objects.filter(user=customer).select_related('vehicle').order_by('-created_at')
    
    # Get customer's payments
    payments = Payment.objects.filter(user=customer).select_related('policy').order_by('-created_at')
    
    # Get customer's vehicles
    vehicles = Vehicle.objects.filter(user=customer).order_by('-created_at')
    
    # Get commissions earned from this customer
    commissions = Commission.objects.filter(agent=agent, policy__user=customer).order_by('-earned_date')
    
    # Calculate summary stats
    total_policies = policies.count()
    active_policies = policies.filter(status='active').count()
    total_premium = policies.aggregate(total=Sum('premium_amount'))['total'] or Decimal('0')
    total_commission = commissions.filter(status__in=['approved', 'paid']).aggregate(
        total=Sum('total_commission')
    )['total'] or Decimal('0')
    
    context = {
        'customer': customer,
        'policies': policies,
        'payments': payments,
        'vehicles': vehicles,
        'commissions': commissions,
        'referral': referral,
        'total_policies': total_policies,
        'active_policies': active_policies,
        'total_premium': total_premium,
        'total_commission': total_commission,
    }
    
    return render(request, 'core/agent/customer_detail.html', context)


@login_required
@agent_required
def agent_commissions(request):
    """View agent's commissions"""
    agent = request.user
    profile, created = AgentProfile.objects.get_or_create(user=agent)
    
    commissions = Commission.objects.filter(agent=agent).select_related(
        'policy', 'policy__user', 'policy__vehicle'
    ).order_by('-earned_date')
    
    # Filters
    status = request.GET.get('status')
    if status:
        commissions = commissions.filter(status=status)
    
    # Summary
    summary = {
        'total_earned': profile.total_commission_earned,
        'total_paid': profile.total_commission_paid,
        'pending': commissions.filter(status='pending').aggregate(total=Sum('total_commission'))['total'] or Decimal('0'),
        'approved': commissions.filter(status='approved').aggregate(total=Sum('total_commission'))['total'] or Decimal('0'),
        'current_month': profile.current_month_commission,
    }
    
    paginator = Paginator(commissions, 20)
    page = request.GET.get('page')
    commissions = paginator.get_page(page)
    
    context = {
        'commissions': commissions,
        'summary': summary,
        'profile': profile,
        'status_filter': status,
    }
    
    return render(request, 'core/agent/commissions.html', context)


@login_required
@agent_required
def agent_commission_detail(request, commission_id):
    """View commission details"""
    commission = get_object_or_404(Commission, id=commission_id, agent=request.user)
    
    context = {
        'commission': commission,
        'policy': commission.policy,
    }
    
    return render(request, 'core/agent/commission_detail.html', context)


@login_required
@agent_required
def agent_profile(request):
    """View and update agent profile"""
    agent = request.user
    profile, created = AgentProfile.objects.get_or_create(user=agent)
    
    if request.method == 'POST':
        form = AgentProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('core:agent_profile')
    else:
        form = AgentProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile': profile,
        'agent': agent,
    }
    
    return render(request, 'core/agent/profile.html', context)


@login_required
@agent_required
def agent_referral_link(request):
    """Generate and share referral link"""
    agent = request.user
    profile, created = AgentProfile.objects.get_or_create(user=agent)
    
    referral_link = f"{request.build_absolute_uri('/')}register/?ref={profile.agent_code}"
    
    # Copy to clipboard functionality is handled in template
    
    context = {
        'profile': profile,
        'referral_link': referral_link,
    }
    
    return render(request, 'core/agent/referral_link.html', context)


@login_required
@agent_required
def agent_policies(request):
    """View policies from downline customers"""
    agent = request.user
    
    # Get customer IDs
    customer_ids = AgentReferral.objects.filter(agent=agent).values_list('customer_id', flat=True)
    
    policies = InsurancePolicy.objects.filter(user_id__in=customer_ids).select_related(
        'user', 'vehicle'
    ).order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        policies = policies.filter(status=status)
    
    # Search
    search = request.GET.get('search')
    if search:
        policies = policies.filter(
            Q(policy_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(vehicle__registration_number__icontains=search)
        )
    
    # Stats
    total_policies = policies.count()
    active_count = policies.filter(status='active').count()
    total_premium = policies.aggregate(total=Sum('premium_amount'))['total'] or Decimal('0')
    
    paginator = Paginator(policies, 20)
    page = request.GET.get('page')
    policies = paginator.get_page(page)
    
    context = {
        'policies': policies,
        'total_policies': total_policies,
        'active_count': active_count,
        'total_premium': total_premium,
        'status_filter': status,
        'search_query': search,
    }
    
    return render(request, 'core/agent/policies.html', context)


@login_required
@agent_required
def agent_policy_detail(request, policy_id):
    """View policy details (only if from downline customer)"""
    agent = request.user
    
    # Verify policy belongs to downline customer
    customer_ids = AgentReferral.objects.filter(agent=agent).values_list('customer_id', flat=True)
    policy = get_object_or_404(InsurancePolicy, id=policy_id, user_id__in=customer_ids)
    
    payments = policy.payments.all().order_by('-created_at')
    claims = policy.claims.all().order_by('-created_at')
    
    # Get commission from this policy
    commission = Commission.objects.filter(agent=agent, policy=policy).first()
    
    context = {
        'policy': policy,
        'payments': payments,
        'claims': claims,
        'commission': commission,
    }
    
    return render(request, 'core/agent/policy_detail.html', context)





@login_required
@agent_required
def agent_claims(request):
    """View claims from downline customers"""
    agent = request.user
    
    # Get customer IDs from referrals
    customer_ids = AgentReferral.objects.filter(agent=agent).values_list('customer_id', flat=True)
    
    # Get claims from these customers
    claims_list = Claim.objects.filter(user_id__in=customer_ids).select_related(
        'user', 'policy', 'policy__vehicle'
    ).order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    status_filter = status
    if status:
        claims_list = claims_list.filter(status=status)
    
    claim_type = request.GET.get('type')
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
    
    # Stats
    total_claims = claims_list.count()
    pending_claims = claims_list.filter(status='pending').count()
    under_review_claims = claims_list.filter(status='under_review').count()
    approved_claims = claims_list.filter(status='approved').count()
    settled_claims = claims_list.filter(status='settled').count()
    rejected_claims = claims_list.filter(status='rejected').count()
    
    total_claimed = claims_list.aggregate(total=Sum('claimed_amount'))['total'] or Decimal('0')
    total_approved = claims_list.filter(status__in=['approved', 'settled']).aggregate(
        total=Sum('approved_amount')
    )['total'] or Decimal('0')
    
    paginator = Paginator(claims_list, 20)
    page = request.GET.get('page')
    claims = paginator.get_page(page)
    
    context = {
        'claims': claims,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'under_review_claims': under_review_claims,
        'approved_claims': approved_claims,
        'settled_claims': settled_claims,
        'rejected_claims': rejected_claims,
        'total_claimed': total_claimed,
        'total_approved': total_approved,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search_query': search,
    }
    
    return render(request, 'core/agent/claims.html', context)



@login_required
@agent_required
def agent_claim_detail(request, claim_id):
    """View claim details (only if from downline customer)"""
    agent = request.user
    from decimal import Decimal
    
    # Verify claim belongs to downline customer
    customer_ids = AgentReferral.objects.filter(agent=agent).values_list('customer_id', flat=True)
    claim = get_object_or_404(Claim, id=claim_id, user_id__in=customer_ids)
    
    # Get policy details
    policy = claim.policy
    
    # Get customer details
    customer = claim.user
    
    # Get documents and photos
    documents = claim.documents if isinstance(claim.documents, list) else []
    photos = claim.photos if isinstance(claim.photos, list) else []
    
    # Calculate coverage percentage if claim is approved
    coverage_percentage = None
    if claim.approved_amount and policy.coverage_amount > 0:
        coverage_percentage = (claim.approved_amount / policy.coverage_amount) * Decimal('100')
    
    context = {
        'claim': claim,
        'policy': policy,
        'customer': customer,
        'documents': documents,
        'photos': photos,
        'coverage_percentage': coverage_percentage,
    }
    
    return render(request, 'core/agent/claim_detail.html', context)