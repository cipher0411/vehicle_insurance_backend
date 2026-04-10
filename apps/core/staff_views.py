from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.text import slugify
from .models import (
    User, InsurancePolicy, Claim, Payment, 
    SupportTicket, TicketReply, Notification, ContactInquiry, JobApplication, BlogPost, BlogComment, PublicDocument, PromoCode, NewsletterSubscriber, JobPosting
)
from .forms import (
    StaffClaimForm, StaffPolicyForm, StaffTicketReplyForm
)
from .decorators import staff_required
@staff_required
def staff_dashboard(request):
    """Enhanced staff dashboard with all management features"""
    user = request.user
    now = timezone.now()
    
    # Get statistics based on role
    if user.role == 'agent':
        policies_managed = InsurancePolicy.objects.filter(user__isnull=False).count()
        claims_managed = Claim.objects.filter(status='pending').count()
        tickets_assigned = SupportTicket.objects.filter(assigned_to=user).count()
    elif user.role == 'underwriter':
        policies_managed = InsurancePolicy.objects.filter(status='pending').count()
        claims_managed = Claim.objects.filter(status='under_review').count()
        tickets_assigned = 0
    elif user.role == 'claims_adjuster':
        policies_managed = 0
        claims_managed = Claim.objects.filter(status__in=['pending', 'under_review']).count()
        tickets_assigned = SupportTicket.objects.filter(assigned_to=user).count()
    elif user.role == 'support':
        policies_managed = 0
        claims_managed = 0
        tickets_assigned = SupportTicket.objects.filter(status='open').count()
    else:  # admin
        policies_managed = InsurancePolicy.objects.count()
        claims_managed = Claim.objects.filter(status__in=['pending', 'under_review']).count()
        tickets_assigned = SupportTicket.objects.filter(status='open').count()
    
    # Overall statistics
    total_users = User.objects.filter(is_active=True).count()
    total_blog_posts = BlogPost.objects.count()
    total_jobs = JobPosting.objects.filter(status='published').count()
    total_documents = PublicDocument.objects.count()
    total_subscribers = NewsletterSubscriber.objects.filter(is_active=True).count()
    
    # Pending counts
    pending_comments = BlogComment.objects.filter(is_approved=False).count()
    pending_applications = JobApplication.objects.filter(status='pending').count()
    pending_inquiries = ContactInquiry.objects.filter(status='pending').count()
    active_promos = PromoCode.objects.filter(is_active=True, valid_from__lte=now, valid_to__gte=now).count()
    
    # Calculate pending tasks for welcome message
    pending_tasks_count = (
        (policies_managed if user.role in ['underwriter'] else 0) +
        (claims_managed if user.role in ['claims_adjuster', 'underwriter'] else 0) +
        (tickets_assigned if user.role == 'support' else 0)
    )
    
    # Recent items
    recent_claims = Claim.objects.order_by('-created_at')[:5]
    recent_policies = InsurancePolicy.objects.order_by('-created_at')[:5]
    recent_inquiries = ContactInquiry.objects.order_by('-created_at')[:5]
    recent_applications = JobApplication.objects.order_by('-created_at')[:5]
    
    context = {
        'user_role': user.role,
        'policies_managed': policies_managed,
        'claims_managed': claims_managed,
        'tickets_assigned': tickets_assigned,
        'total_users': total_users,
        'total_blog_posts': total_blog_posts,
        'total_jobs': total_jobs,
        'total_documents': total_documents,
        'total_subscribers': total_subscribers,
        'pending_comments': pending_comments,
        'pending_applications': pending_applications,
        'pending_inquiries': pending_inquiries,
        'active_promos': active_promos,
        'pending_tasks_count': pending_tasks_count,
        'recent_claims': recent_claims,
        'recent_policies': recent_policies,
        'recent_inquiries': recent_inquiries,
        'recent_applications': recent_applications,
        'current_date': now,
        'current_hour': now.hour,
    }
    
    return render(request, 'core/staff/dashboard.html', context)

@staff_required
def staff_claims(request):
    """View and manage claims"""
    claims_list = Claim.objects.all().order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        claims_list = claims_list.filter(status=status)
    
    # Filter by claim type
    claim_type = request.GET.get('claim_type')
    if claim_type:
        claims_list = claims_list.filter(claim_type=claim_type)
    
    paginator = Paginator(claims_list, 20)
    page = request.GET.get('page')
    claims = paginator.get_page(page)
    
    return render(request, 'core/staff/claims.html', {'claims': claims})

@staff_required
def staff_claim_detail(request, claim_id):
    """View and process claim detail"""
    claim = get_object_or_404(Claim, id=claim_id)
    
    if request.method == 'POST':
        form = StaffClaimForm(request.POST, request.FILES, instance=claim)
        if form.is_valid():
            action = request.POST.get('action')
            
            if action == 'review':
                claim.status = 'under_review'
                claim.surveyor_notes = form.cleaned_data.get('surveyor_notes', '')
                
                if request.FILES.get('surveyor_report'):
                    claim.surveyor_report = request.FILES['surveyor_report']
                
                messages.success(request, f'Claim {claim.claim_number} is under review')
                
            elif action == 'approve':
                claim.status = 'approved'
                claim.approved_amount = form.cleaned_data.get('approved_amount', claim.claimed_amount)
                claim.approved_by = request.user
                claim.approval_date = timezone.now()
                
                messages.success(request, f'Claim {claim.claim_number} approved!')
                
            elif action == 'reject':
                claim.status = 'rejected'
                claim.rejection_reason = form.cleaned_data.get('rejection_reason', '')
                messages.warning(request, f'Claim {claim.claim_number} rejected')
            
            claim.save()
            
            # Send notification to customer
            Notification.objects.create(
                user=claim.user,
                title=f'Claim Update - {claim.claim_number}',
                message=f'Your claim status has been updated to {claim.status}',
                notification_type='claim_update'
            )
            
            return redirect('core:staff_claim_detail', claim_id=claim.id)
    else:
        form = StaffClaimForm(instance=claim)
    
    return render(request, 'core/staff/claim_detail.html', {
        'claim': claim,
        'form': form
    })

@staff_required
def staff_policies(request):
    """View policies"""
    policies_list = InsurancePolicy.objects.all().order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        policies_list = policies_list.filter(status=status)
    
    # Filter by policy type
    policy_type = request.GET.get('policy_type')
    if policy_type:
        policies_list = policies_list.filter(policy_type=policy_type)
    
    paginator = Paginator(policies_list, 20)
    page = request.GET.get('page')
    policies = paginator.get_page(page)
    
    return render(request, 'core/staff/policies.html', {'policies': policies})

@staff_required
def staff_policy_detail(request, policy_id):
    """View policy details"""
    policy = get_object_or_404(InsurancePolicy, id=policy_id)
    
    if request.method == 'POST' and request.user.role == 'underwriter':
        form = StaffPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, f'Policy {policy.policy_number} updated!')
            return redirect('core:staff_policy_detail', policy_id=policy.id)
    else:
        form = StaffPolicyForm(instance=policy) if request.user.role == 'underwriter' else None
    
    payments = policy.payments.all()
    claims = policy.claims.all()
    
    return render(request, 'core/staff/policy_detail.html', {
        'policy': policy,
        'form': form,
        'payments': payments,
        'claims': claims
    })

@staff_required
def staff_tickets(request):
    """View support tickets"""
    tickets_list = SupportTicket.objects.all().order_by('-created_at')
    
    # Filter assigned tickets for support staff
    if request.user.role == 'support':
        tickets_list = tickets_list.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        tickets_list = tickets_list.filter(status=status)
    
    # Filter by priority
    priority = request.GET.get('priority')
    if priority:
        tickets_list = tickets_list.filter(priority=priority)
    
    paginator = Paginator(tickets_list, 20)
    page = request.GET.get('page')
    tickets = paginator.get_page(page)
    
    return render(request, 'core/staff/tickets.html', {'tickets': tickets})


@staff_required
@require_http_methods(["POST"])
def staff_assign_ticket(request, ticket_id):
    """Assign ticket to current staff member"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    if ticket.assigned_to:
        return JsonResponse({'success': False, 'message': 'Ticket already assigned'})
    
    ticket.assigned_to = request.user
    ticket.save()
    
    return JsonResponse({'success': True, 'message': 'Ticket assigned successfully'})


@staff_required
@require_http_methods(["POST"])
def staff_start_ticket(request, ticket_id):
    """Mark ticket as in progress"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    if ticket.assigned_to != request.user:
        return JsonResponse({'success': False, 'message': 'You must be assigned to this ticket'})
    
    if ticket.status != 'open':
        return JsonResponse({'success': False, 'message': 'Ticket is not open'})
    
    ticket.status = 'in_progress'
    ticket.save()
    
    return JsonResponse({'success': True, 'message': 'Ticket marked as in progress'})


@staff_required
def staff_ticket_detail(request, ticket_id):
    """View and reply to ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    if request.method == 'POST':
        form = StaffTicketReplyForm(request.POST, request.FILES)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.ticket = ticket
            reply.user = request.user
            reply.save()
            
            # Update ticket status
            if form.cleaned_data.get('change_status'):
                ticket.status = form.cleaned_data['new_status']
                ticket.save()
            
            # Assign ticket to staff if not assigned
            if not ticket.assigned_to:
                ticket.assigned_to = request.user
                ticket.save()
            
            # Send notification to customer
            Notification.objects.create(
                user=ticket.user,
                title=f'Ticket Update - {ticket.ticket_number}',
                message=f'New reply on your support ticket',
                notification_type='system_alert'
            )
            
            messages.success(request, 'Reply added successfully!')
            return redirect('core:staff_ticket_detail', ticket_id=ticket.id)
    else:
        form = StaffTicketReplyForm()
    
    return render(request, 'core/staff/ticket_detail.html', {
        'ticket': ticket,
        'form': form
    })

@staff_required
def staff_customers(request):
    """View customers"""
    customers = User.objects.filter(role='customer').order_by('-date_joined')
    
    # Search
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    paginator = Paginator(customers, 20)
    page = request.GET.get('page')
    customers = paginator.get_page(page)
    
    return render(request, 'core/staff/customers.html', {'customers': customers})

@staff_required
def staff_customer_detail(request, user_id):
    """View customer details"""
    customer = get_object_or_404(User, id=user_id, role='customer')
    policies = customer.policies.all()
    claims = customer.claims.all()
    vehicles = customer.vehicles.all()
    
    return render(request, 'core/staff/customer_detail.html', {
        'customer': customer,
        'policies': policies,
        'claims': claims,
        'vehicles': vehicles
    })