"""
Enterprise Security Views - SOC Dashboard, Threat Intelligence, Security Events
"""
import json
import requests
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q, Sum
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from ipware import get_client_ip
from django.db import models
from django.db.models.functions import TruncHour

from apps.core.decorators import admin_required
from apps.core.models import (
    User, SecurityEvent, ThreatIntel, AuditLog, 
    InsuranceSettings, APIKey
)
from apps.core.forms import (
    ThreatIntelForm, APIKeyForm, SecuritySettingsForm
)


@admin_required
def security_dashboard(request):
    """Enterprise Security Dashboard - SOC Overview"""
    
    # Time ranges
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    
    # Security statistics
    total_events_24h = SecurityEvent.objects.filter(created_at__gte=last_24h).count()
    blocked_attacks = SecurityEvent.objects.filter(
        created_at__gte=last_24h,
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT', 'XSS_ATTEMPT']
    ).count()
    malware_detected = SecurityEvent.objects.filter(
        created_at__gte=last_24h,
        event_type='MALWARE_DETECTED'
    ).count()
    rate_limited = SecurityEvent.objects.filter(
        created_at__gte=last_24h,
        event_type='RATE_LIMIT'
    ).count()
    failed_logins = SecurityEvent.objects.filter(
        created_at__gte=last_24h,
        event_type='LOGIN_FAILED'
    ).count()
    blocked_ips = cache.keys('blocked_ip:*')
    
    # Threat intelligence stats
    active_threats = ThreatIntel.objects.filter(is_active=True).count()
    high_severity_threats = ThreatIntel.objects.filter(is_active=True, threat_score__gte=70).count()
    
    # Threat level calculation
    threat_score = min(100, (blocked_attacks * 2) + (malware_detected * 10) + (high_severity_threats * 5))
    if threat_score >= 70:
        threat_level = 'HIGH'
        threat_color = 'danger'
    elif threat_score >= 40:
        threat_level = 'MEDIUM'
        threat_color = 'warning'
    else:
        threat_level = 'LOW'
        threat_color = 'success'
    
    # Recent security events
    recent_events = SecurityEvent.objects.select_related('user').order_by('-created_at')[:50]
    
    # Attack timeline data (last 7 days by hour)
    attack_timeline = SecurityEvent.objects.filter(
        created_at__gte=last_7d,
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT', 'XSS_ATTEMPT']
    ).extra({
        'hour': "strftime('%%Y-%%m-%%d %%H:00:00', created_at)"
    }).values('hour').annotate(count=Count('id')).order_by('hour')
    
    attack_labels = [item['hour'] for item in attack_timeline]
    attack_data = [item['count'] for item in attack_timeline]
    
    # Top attacking IPs
    top_ips = SecurityEvent.objects.filter(
        created_at__gte=last_24h,
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL']
    ).values('ip_address').annotate(count=Count('id')).order_by('-count')[:10]
    
    ip_labels = [item['ip_address'] for item in top_ips]
    ip_data = [item['count'] for item in top_ips]
    
    # Event type distribution
    event_types = SecurityEvent.objects.filter(
        created_at__gte=last_24h
    ).values('event_type').annotate(count=Count('id')).order_by('-count')
    
    event_type_labels = [dict(SecurityEvent.EVENT_TYPE_CHOICES).get(item['event_type'], item['event_type']) for item in event_types]
    event_type_data = [item['count'] for item in event_types]
    
    # Active threat intelligence
    threat_intel = ThreatIntel.objects.filter(is_active=True).order_by('-threat_score', '-last_seen')[:20]
    
    # API Status checks
    api_status = check_api_status()
    
    context = {
        'threat_level': threat_level,
        'threat_color': threat_color,
        'threat_percentage': threat_score,
        'blocked_attacks': blocked_attacks,
        'malware_detected': malware_detected,
        'rate_limited': rate_limited,
        'blocked_ips': len(blocked_ips),
        'failed_logins': failed_logins,
        'threat_intel_count': active_threats,
        'high_severity_threats': high_severity_threats,
        'recent_events': recent_events[:20],
        'threat_intel': threat_intel,
        'attack_labels': json.dumps(attack_labels),
        'attack_data': json.dumps(attack_data),
        'ip_labels': json.dumps(ip_labels),
        'ip_data': json.dumps(ip_data),
        'event_type_labels': json.dumps(event_type_labels),
        'event_type_data': json.dumps(event_type_data),
        'api_status': api_status,
        'total_events_24h': total_events_24h,
    }
    
    return render(request, 'core/admin/security/dashboard.html', context)


@admin_required
def security_events(request):
    """View all security events"""
    events = SecurityEvent.objects.select_related('user').order_by('-created_at')
    
    # Filters
    event_type = request.GET.get('event_type')
    if event_type:
        events = events.filter(event_type=event_type)
    
    severity = request.GET.get('severity')
    if severity:
        events = events.filter(severity=severity)
    
    ip = request.GET.get('ip')
    if ip:
        events = events.filter(ip_address=ip)
    
    # Search
    search = request.GET.get('search')
    if search:
        events = events.filter(
            Q(path__icontains=search) |
            Q(ip_address__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    from django.core.paginator import Paginator
    paginator = Paginator(events, 50)
    page = request.GET.get('page')
    events = paginator.get_page(page)
    
    # Statistics
    total_events = SecurityEvent.objects.count()
    critical_events = SecurityEvent.objects.filter(severity='CRITICAL').count()
    high_events = SecurityEvent.objects.filter(severity='HIGH').count()
    
    # Event types for filter dropdown
    event_types = SecurityEvent.EVENT_TYPE_CHOICES
    
    context = {
        'events': events,
        'event_types': event_types,
        'total_events': total_events,
        'critical_events': critical_events,
        'high_events': high_events,
        'event_type_filter': event_type,
        'severity_filter': severity,
        'ip_filter': ip,
        'search_query': search,
    }
    
    return render(request, 'core/admin/security/events.html', context)


@admin_required
def security_event_detail(request, event_id):
    """View security event details"""
    event = get_object_or_404(SecurityEvent, id=event_id)
    
    # Get related events from same IP
    related_events = SecurityEvent.objects.filter(
        ip_address=event.ip_address
    ).exclude(id=event.id).order_by('-created_at')[:20]
    
    context = {
        'event': event,
        'related_events': related_events,
    }
    
    return render(request, 'core/admin/security/event_detail.html', context)


@admin_required
def threat_intelligence(request):
    """Manage threat intelligence"""
    threats = ThreatIntel.objects.all().order_by('-threat_score', '-last_seen')
    
    # Filters
    intel_type = request.GET.get('intel_type')
    if intel_type:
        threats = threats.filter(intel_type=intel_type)
    
    source = request.GET.get('source')
    if source:
        threats = threats.filter(source=source)
    
    is_active = request.GET.get('is_active')
    if is_active:
        threats = threats.filter(is_active=is_active == 'true')
    
    from django.core.paginator import Paginator
    paginator = Paginator(threats, 50)
    page = request.GET.get('page')
    threats = paginator.get_page(page)
    
    # Statistics
    total_threats = ThreatIntel.objects.count()
    active_threats = ThreatIntel.objects.filter(is_active=True).count()
    high_score_threats = ThreatIntel.objects.filter(threat_score__gte=70, is_active=True).count()
    
    context = {
        'threats': threats,
        'total_threats': total_threats,
        'active_threats': active_threats,
        'high_score_threats': high_score_threats,
        'intel_type_filter': intel_type,
        'source_filter': source,
        'is_active_filter': is_active,
    }
    
    return render(request, 'core/admin/security/threat_intel.html', context)


@admin_required
def add_threat_intel(request):
    """Add threat intelligence entry"""
    if request.method == 'POST':
        form = ThreatIntelForm(request.POST)
        if form.is_valid():
            threat = form.save(commit=False)
            threat.created_by = request.user
            threat.source = 'manual'
            threat.save()
            messages.success(request, 'Threat intelligence added successfully!')
            return redirect('core:threat_intelligence')
    else:
        form = ThreatIntelForm()
    
    return render(request, 'core/admin/security/add_threat.html', {'form': form})


@admin_required
@require_http_methods(["POST"])
def toggle_threat_intel(request, threat_id):
    """Toggle threat intelligence active status"""
    threat = get_object_or_404(ThreatIntel, id=threat_id)
    threat.is_active = not threat.is_active
    threat.save()
    return JsonResponse({'success': True, 'is_active': threat.is_active})


@admin_required
@require_http_methods(["POST"])
def delete_threat_intel(request, threat_id):
    """Delete threat intelligence"""
    threat = get_object_or_404(ThreatIntel, id=threat_id)
    threat.delete()
    return JsonResponse({'success': True})


@admin_required
def audit_logs(request):
    """Enhanced enterprise audit logs view"""
    logs = AuditLog.objects.select_related('user').order_by('-created_at')
    
    # Calculate statistics
    total_logs = logs.count()
    create_count = logs.filter(action='CREATE').count()
    update_count = logs.filter(action='UPDATE').count()
    delete_count = logs.filter(action='DELETE').count()
    approve_count = logs.filter(action='APPROVE').count()
    reject_count = logs.filter(action='REJECT').count()
    export_count = logs.filter(action='EXPORT').count()
    
    # Today's activity
    today = timezone.now().date()
    today_logs = logs.filter(created_at__date=today).count()
    
    # Top users by activity
    top_users = logs.values('user__email').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Action distribution for chart
    action_distribution = logs.values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    action_labels = [dict(AuditLog.ACTION_CHOICES).get(item['action'], item['action']) for item in action_distribution]
    action_data = [item['count'] for item in action_distribution]
    
    # Hourly activity pattern
    hourly_activity = logs.annotate(
        hour=TruncHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    hourly_labels = [item['hour'].strftime('%H:%M') for item in hourly_activity]
    hourly_data = [item['count'] for item in hourly_activity]
    
    # Filters
    action = request.GET.get('action')
    action_filter = action
    if action:
        logs = logs.filter(action=action)
    
    resource_type = request.GET.get('resource_type')
    resource_filter = resource_type
    if resource_type:
        logs = logs.filter(resource_type=resource_type)
    
    user_id = request.GET.get('user')
    user_filter = user_id
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    # Date range filter
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    
    # IP filter
    ip_filter = request.GET.get('ip')
    if ip_filter:
        logs = logs.filter(ip_address__icontains=ip_filter)
    
    # Search
    search = request.GET.get('search')
    if search:
        logs = logs.filter(
            Q(resource_id__icontains=search) |
            Q(resource_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(ip_address__icontains=search)
        )
    
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    logs = paginator.get_page(page)
    
    # Get unique users and resource types for filters
    users = User.objects.filter(auditlog__isnull=False).distinct()
    resource_types = AuditLog.objects.values_list('resource_type', flat=True).distinct()
    
    context = {
        'logs': logs,
        'users': users,
        'resource_types': resource_types,
        'total_logs': total_logs,
        'create_count': create_count,
        'update_count': update_count,
        'delete_count': delete_count,
        'approve_count': approve_count,
        'reject_count': reject_count,
        'export_count': export_count,
        'today_logs': today_logs,
        'top_users': top_users,
        'action_labels': json.dumps(action_labels),
        'action_data': json.dumps(action_data),
        'hourly_labels': json.dumps(hourly_labels),
        'hourly_data': json.dumps(hourly_data),
        'action_filter': action_filter,
        'resource_filter': resource_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'ip_filter': ip_filter,
        'search_query': search,
        'actions': AuditLog.ACTION_CHOICES,
    }
    
    return render(request, 'core/admin/security/audit_logs.html', context)


@admin_required
def audit_log_detail(request, log_id):
    """Detailed view of a single audit log"""
    log = get_object_or_404(AuditLog.objects.select_related('user'), id=log_id)
    
    # Get related logs from same user
    user_logs = AuditLog.objects.filter(user=log.user).exclude(id=log.id).order_by('-created_at')[:20]
    
    # Get related logs from same IP
    ip_logs = AuditLog.objects.filter(ip_address=log.ip_address).exclude(id=log.id).order_by('-created_at')[:20]
    
    # Get logs on same resource
    resource_logs = AuditLog.objects.filter(
        resource_type=log.resource_type,
        resource_id=log.resource_id
    ).exclude(id=log.id).order_by('-created_at')[:20]
    
    # User activity summary
    if log.user:
        user_activity_summary = {
            'total_actions': AuditLog.objects.filter(user=log.user).count(),
            'creates': AuditLog.objects.filter(user=log.user, action='CREATE').count(),
            'updates': AuditLog.objects.filter(user=log.user, action='UPDATE').count(),
            'deletes': AuditLog.objects.filter(user=log.user, action='DELETE').count(),
            'first_seen': AuditLog.objects.filter(user=log.user).order_by('created_at').first().created_at,
            'last_seen': AuditLog.objects.filter(user=log.user).order_by('-created_at').first().created_at,
            'unique_ips': AuditLog.objects.filter(user=log.user).values('ip_address').distinct().count(),
        }
    else:
        user_activity_summary = None
    
    # IP activity summary
    ip_activity_summary = {
        'total_requests': AuditLog.objects.filter(ip_address=log.ip_address).count(),
        'unique_users': AuditLog.objects.filter(ip_address=log.ip_address).values('user').distinct().count(),
        'first_seen': AuditLog.objects.filter(ip_address=log.ip_address).order_by('created_at').first().created_at,
        'last_seen': AuditLog.objects.filter(ip_address=log.ip_address).order_by('-created_at').first().created_at,
        'actions': AuditLog.objects.filter(ip_address=log.ip_address).values('action').annotate(count=Count('id')),
    }
    
    context = {
        'log': log,
        'user_logs': user_logs,
        'ip_logs': ip_logs,
        'resource_logs': resource_logs,
        'user_activity_summary': user_activity_summary,
        'ip_activity_summary': ip_activity_summary,
    }
    
    return render(request, 'core/admin/security/audit_log_detail.html', context)


@admin_required
def export_audit_logs(request):
    """Export audit logs to CSV"""
    from django.http import HttpResponse
    import csv
    
    # Apply same filters as the list view
    logs = AuditLog.objects.select_related('user').order_by('-created_at')
    
    action = request.GET.get('action')
    if action:
        logs = logs.filter(action=action)
    
    resource_type = request.GET.get('resource_type')
    if resource_type:
        logs = logs.filter(resource_type=resource_type)
    
    user_id = request.GET.get('user')
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'User', 'Action', 'Resource Type', 'Resource ID', 
        'Resource Name', 'IP Address', 'User Agent', 'Session ID', 'Changes', 'Status Code'
    ])
    
    for log in logs[:10000]:  # Limit to 10000 records
        writer.writerow([
            log.created_at.isoformat(),
            log.user.email if log.user else 'System',
            log.action,
            log.resource_type,
            log.resource_id,
            log.resource_name,
            log.ip_address,
            log.user_agent,
            log.session_id,
            json.dumps(log.changes) if log.changes else '',
            log.metadata.get('status_code', '')
        ])
    
    return response


@admin_required
def api_keys(request):
    """Manage API keys"""
    keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        form = APIKeyForm(request.POST)
        if form.is_valid():
            api_key = form.save(commit=False)
            api_key.user = request.user
            api_key.save()
            messages.success(request, f'API Key created! Your key: {api_key.key}')
            return redirect('core:api_keys')
    else:
        form = APIKeyForm()
    
    context = {
        'keys': keys,
        'form': form,
    }
    
    return render(request, 'core/admin/security/api_keys.html', context)


@admin_required
@require_http_methods(["POST"])
def revoke_api_key(request, key_id):
    """Revoke API key"""
    api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
    api_key.is_active = False
    api_key.save()
    return JsonResponse({'success': True})


@admin_required
def security_settings(request):
    """Configure security settings"""
    settings_obj = InsuranceSettings.get_settings()
    
    if request.method == 'POST':
        form = SecuritySettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Security settings updated successfully!')
            return redirect('core:security_settings')
    else:
        form = SecuritySettingsForm(instance=settings_obj)
    
    # Test API connections
    api_status = check_api_status()
    
    context = {
        'form': form,
        'api_status': api_status,
        'settings': settings_obj,
    }
    
    return render(request, 'core/admin/security/settings.html', context)


@admin_required
@require_http_methods(["POST"])
def test_api_connection(request, api_name):
    """Test individual API connection"""
    result = test_single_api(api_name)
    return JsonResponse(result)


@admin_required
def live_monitoring(request):
    """Live security monitoring (WebSocket/SSE ready)"""
    # Get real-time stats
    stats = {
        'requests_last_minute': cache.get('requests_last_minute', 0),
        'blocked_last_minute': cache.get('blocked_last_minute', 0),
        'active_sessions': cache.get('active_sessions', 0),
        'threats_detected': SecurityEvent.objects.filter(
            created_at__gte=timezone.now() - timedelta(minutes=5),
            event_type__in=['ATTACK_DETECTED', 'MALWARE_DETECTED']
        ).count(),
    }
    
    # Recent activity stream
    recent_activity = SecurityEvent.objects.filter(
        created_at__gte=timezone.now() - timedelta(minutes=30)
    ).order_by('-created_at')[:50]
    
    context = {
        'stats': stats,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'core/admin/security/live_monitoring.html', context)


@admin_required
def block_ip(request):
    """Manually block an IP address"""
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        reason = request.POST.get('reason', 'Manual block')
        duration = int(request.POST.get('duration', 86400))
        
        if ip_address:
            cache.set(f"blocked_ip:{ip_address}", {
                'reason': reason,
                'blocked_at': timezone.now().isoformat(),
                'blocked_by': request.user.email
            }, duration)
            
            # Log to threat intel
            ThreatIntel.objects.update_or_create(
                intel_type='ip',
                value=ip_address,
                defaults={
                    'threat_score': 100,
                    'description': f'Manually blocked: {reason}',
                    'source': 'manual',
                    'created_by': request.user,
                    'is_active': True
                }
            )
            
            messages.success(request, f'IP {ip_address} blocked for {duration} seconds')
        else:
            messages.error(request, 'Please provide an IP address')
    
    return redirect('core:security_dashboard')


@admin_required
def unblock_ip(request, ip_address):
    """Unblock an IP address"""
    cache.delete(f"blocked_ip:{ip_address}")
    messages.success(request, f'IP {ip_address} unblocked')
    return redirect('core:security_dashboard')


@admin_required
def get_security_stats(request):
    """AJAX endpoint for live stats"""
    now = timezone.now()
    stats = {
        'total_events_24h': SecurityEvent.objects.filter(created_at__gte=now - timedelta(hours=24)).count(),
        'blocked_attacks_24h': SecurityEvent.objects.filter(
            created_at__gte=now - timedelta(hours=24),
            event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL']
        ).count(),
        'active_threats': ThreatIntel.objects.filter(is_active=True).count(),
        'blocked_ips': len(cache.keys('blocked_ip:*')),
        'timestamp': now.isoformat(),
    }
    return JsonResponse(stats)


# Helper functions
def check_api_status():
    """Check status of all integrated APIs"""
    apis = {
        'virustotal': {'name': 'VirusTotal', 'key': settings.VIRUSTOTAL_API_KEY},
        'abuseipdb': {'name': 'AbuseIPDB', 'key': settings.ABUSEIPDB_API_KEY},
        'shodan': {'name': 'Shodan', 'key': settings.SHODAN_API_KEY},
        'metadefender': {'name': 'MetaDefender', 'key': settings.METADEFENDER_API_KEY},
    }
    
    status = {}
    for key, api in apis.items():
        if api['key']:
            # Check cache first
            cached = cache.get(f'api_status:{key}')
            if cached:
                status[key] = cached
            else:
                result = test_single_api(key)
                cache.set(f'api_status:{key}', result, 300)  # Cache for 5 minutes
                status[key] = result
        else:
            status[key] = {'name': api['name'], 'status': 'not_configured', 'message': 'API key not set'}
    
    return status


def test_single_api(api_name):
    """Test a single API connection"""
    if api_name == 'virustotal':
        return test_virustotal()
    elif api_name == 'abuseipdb':
        return test_abuseipdb()
    elif api_name == 'shodan':
        return test_shodan()
    elif api_name == 'metadefender':
        return test_metadefender()
    return {'status': 'error', 'message': 'Unknown API'}


def test_virustotal():
    """Test VirusTotal API"""
    try:
        url = "https://www.virustotal.com/api/v3/ip_addresses/8.8.8.8"
        headers = {"x-apikey": settings.VIRUSTOTAL_API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return {'name': 'VirusTotal', 'status': 'online', 'message': 'Connected successfully'}
        return {'name': 'VirusTotal', 'status': 'error', 'message': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'name': 'VirusTotal', 'status': 'error', 'message': str(e)[:50]}


def test_abuseipdb():
    """Test AbuseIPDB API"""
    try:
        url = "https://api.abuseipdb.com/api/v2/check"
        headers = {"Key": settings.ABUSEIPDB_API_KEY, "Accept": "application/json"}
        params = {"ipAddress": "8.8.8.8", "maxAgeInDays": 1}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return {'name': 'AbuseIPDB', 'status': 'online', 'message': 'Connected successfully'}
        return {'name': 'AbuseIPDB', 'status': 'error', 'message': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'name': 'AbuseIPDB', 'status': 'error', 'message': str(e)[:50]}


def test_shodan():
    """Test Shodan API"""
    try:
        url = "https://api.shodan.io/api-info"
        params = {"key": settings.SHODAN_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {'name': 'Shodan', 'status': 'online', 'message': f"Credits: {data.get('credits', 'N/A')}"}
        return {'name': 'Shodan', 'status': 'error', 'message': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'name': 'Shodan', 'status': 'error', 'message': str(e)[:50]}


def test_metadefender():
    """Test MetaDefender API"""
    try:
        url = "https://api.metadefender.com/v4/version"
        headers = {"apikey": settings.METADEFENDER_API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return {'name': 'MetaDefender', 'status': 'online', 'message': 'Connected successfully'}
        return {'name': 'MetaDefender', 'status': 'error', 'message': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'name': 'MetaDefender', 'status': 'error', 'message': str(e)[:50]}
    
    
      
    
# apps/core/views_security.py - Add these view functions
# apps/core/views_security.py - Updated with scheduled reports
from .models import SecurityEvent, ThreatIntel, AuditLog, InsuranceSettings, APIKey, ScheduledReport

@admin_required
def security_reports(request):
    """Dynamic security reports page"""
    from datetime import datetime, timedelta
    from django.db.models import Count, Q, Sum, Avg
    from django.db.models.functions import TruncDay, TruncHour
    
    now = timezone.now()
    
    # Get date range from request
    date_range = request.GET.get('date_range', 'last7days')
    report_type = request.GET.get('report_type', 'daily')
    
    # Calculate date range
    if date_range == 'today':
        start_date = now.replace(hour=0, minute=0, second=0)
    elif date_range == 'yesterday':
        start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
        end_date = start_date + timedelta(days=1)
    elif date_range == 'last7days':
        start_date = now - timedelta(days=7)
    elif date_range == 'last30days':
        start_date = now - timedelta(days=30)
    elif date_range == 'this_month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0)
    else:
        start_date = now - timedelta(days=7)
    
    # Base queryset
    events = SecurityEvent.objects.filter(created_at__gte=start_date)
    
    # Summary statistics
    total_events = events.count()
    blocked_attacks = events.filter(
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT', 'XSS_ATTEMPT']
    ).count()
    
    unique_attackers = events.filter(
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL']
    ).values('ip_address').distinct().count()
    
    # Get top attackers
    top_attackers = events.filter(
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT']
    ).values('ip_address').annotate(
        count=Count('id'),
        last_seen=models.Max('created_at')
    ).order_by('-count')[:10]
    
    # Enrich with country info
    for attacker in top_attackers:
        attacker['country'] = get_country_from_ip(attacker['ip_address'])
        attacker['status'] = 'Blocked' if cache.get(f"blocked_ip:{attacker['ip_address']}") else 'Monitoring'
    
    # Attack trend data (by day)
    attack_trend = events.filter(
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT', 'XSS_ATTEMPT']
    ).annotate(
        date=TruncDay('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    trend_labels = []
    trend_data = []
    for item in attack_trend:
        trend_labels.append(item['date'].strftime('%b %d' if date_range == 'last30days' else '%a'))
        trend_data.append(item['count'])
    
    # Threat distribution
    threat_distribution = events.values('event_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    dist_labels = []
    dist_data = []
    dist_colors = []
    
    color_map = {
        'ATTACK_DETECTED': '#ef4444',
        'SQLI_ATTEMPT': '#dc2626',
        'XSS_ATTEMPT': '#f59e0b',
        'PATH_TRAVERSAL': '#3b82f6',
        'RATE_LIMIT': '#10b981',
        'LOGIN_FAILED': '#f97316',
        'MALWARE_DETECTED': '#8b5cf6',
        'BLOCKED_IP': '#64748b',
    }
    
    for item in threat_distribution:
        event_type_display = dict(SecurityEvent.EVENT_TYPE_CHOICES).get(item['event_type'], item['event_type'])
        dist_labels.append(event_type_display)
        dist_data.append(item['count'])
        dist_colors.append(color_map.get(item['event_type'], '#64748b'))
    
    # Severity distribution
    severity_dist = events.values('severity').annotate(
        count=Count('id')
    ).order_by('severity')
    
    severity_data = {item['severity']: item['count'] for item in severity_dist}
    
    # Hourly attack pattern
    hourly_attacks = events.filter(
        event_type__in=['ATTACK_DETECTED', 'PATH_TRAVERSAL', 'SQLI_ATTEMPT']
    ).annotate(
        hour=TruncHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    hourly_labels = []
    hourly_data = []
    for item in hourly_attacks:
        hourly_labels.append(item['hour'].strftime('%H:%M'))
        hourly_data.append(item['count'])
    
    # Top targeted paths
    top_paths = events.values('path').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Recommendations based on data
    recommendations = []
    
    # Check for SQL injection attempts
    sqli_count = events.filter(event_type='SQLI_ATTEMPT').count()
    if sqli_count > 10:
        recommendations.append({
            'priority': 'high',
            'message': f'{sqli_count} SQL injection attempts detected. Review WAF rules and consider additional input validation.'
        })
    
    # Check for failed logins
    failed_logins = events.filter(event_type='LOGIN_FAILED').count()
    if failed_logins > 50:
        recommendations.append({
            'priority': 'medium',
            'message': f'{failed_logins} failed login attempts detected. Consider enabling additional rate limiting on login endpoints.'
        })
    
    # Check top attacker
    if top_attackers and top_attackers[0]['count'] > 20:
        recommendations.append({
            'priority': 'high',
            'message': f"IP {top_attackers[0]['ip_address']} has made {top_attackers[0]['count']} attacks. Consider permanent blocking."
        })
    
    # Check for path traversal
    path_traversal = events.filter(event_type='PATH_TRAVERSAL').count()
    if path_traversal > 5:
        recommendations.append({
            'priority': 'high',
            'message': f'{path_traversal} path traversal attempts detected. Review file access controls.'
        })
    
    # Default recommendation if none
    if not recommendations:
        recommendations.append({
            'priority': 'low',
            'message': 'No critical threats detected. Continue monitoring.'
        })
    
    # Get scheduled reports from database
    scheduled_reports = ScheduledReport.objects.filter(
        created_by=request.user,
        status='active'
    ).order_by('-created_at')
    
    context = {
        'report_type': report_type,
        'date_range': date_range,
        'total_events': total_events,
        'blocked_attacks': blocked_attacks,
        'unique_attackers': unique_attackers,
        'avg_response_time': 12,
        'top_attackers': top_attackers,
        'trend_labels': json.dumps(trend_labels),
        'trend_data': json.dumps(trend_data),
        'dist_labels': json.dumps(dist_labels),
        'dist_data': json.dumps(dist_data),
        'dist_colors': json.dumps(dist_colors),
        'severity_critical': severity_data.get('CRITICAL', 0),
        'severity_high': severity_data.get('HIGH', 0),
        'severity_medium': severity_data.get('MEDIUM', 0),
        'severity_low': severity_data.get('LOW', 0),
        'hourly_labels': json.dumps(hourly_labels),
        'hourly_data': json.dumps(hourly_data),
        'top_paths': top_paths,
        'recommendations': recommendations,
        'scheduled_reports': scheduled_reports,
    }
    
    return render(request, 'core/admin/security/reports.html', context)


def get_country_from_ip(ip_address):
    """Get country from IP address"""
    if ip_address.startswith('185.220.'):
        return 'Germany'
    elif ip_address.startswith('45.142.'):
        return 'Netherlands'
    elif ip_address.startswith('103.145.'):
        return 'China'
    elif ip_address.startswith('198.51.'):
        return 'United States'
    elif ip_address.startswith('203.0.'):
        return 'Russia'
    return 'Unknown'


@admin_required
def scheduled_reports_list(request):
    """List all scheduled reports"""
    reports = ScheduledReport.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'reports': reports,
    }
    return render(request, 'core/admin/security/scheduled_reports.html', context)


@admin_required
def create_scheduled_report(request):
    """Create a new scheduled report"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            report_type = request.POST.get('report_type')
            frequency = request.POST.get('frequency')
            report_format = request.POST.get('format', 'pdf')
            time_of_day = request.POST.get('time_of_day', '08:00')
            recipients = request.POST.get('recipients')
            day_of_week = request.POST.get('day_of_week')
            day_of_month = request.POST.get('day_of_month')
            date_range_days = int(request.POST.get('date_range_days', 7))
            include_charts = request.POST.get('include_charts') == 'on'
            include_tables = request.POST.get('include_tables') == 'on'
            include_recommendations = request.POST.get('include_recommendations') == 'on'
            cc_recipients = request.POST.get('cc_recipients', '')
            bcc_recipients = request.POST.get('bcc_recipients', '')
            
            report = ScheduledReport.objects.create(
                name=name,
                report_type=report_type,
                frequency=frequency,
                format=report_format,
                time_of_day=datetime.strptime(time_of_day, '%H:%M').time(),
                recipients=recipients,
                cc_recipients=cc_recipients,
                bcc_recipients=bcc_recipients,
                day_of_week=int(day_of_week) if day_of_week else None,
                day_of_month=int(day_of_month) if day_of_month else None,
                date_range_days=date_range_days,
                include_charts=include_charts,
                include_tables=include_tables,
                include_recommendations=include_recommendations,
                created_by=request.user,
                status='active'
            )
            
            messages.success(request, f'Report "{name}" scheduled successfully!')
            return JsonResponse({'success': True, 'report_id': str(report.id)})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@admin_required
def update_scheduled_report(request, report_id):
    """Update a scheduled report"""
    report = get_object_or_404(ScheduledReport, id=report_id, created_by=request.user)
    
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            
            if action == 'toggle':
                report.status = 'paused' if report.status == 'active' else 'active'
                report.next_run = report.calculate_next_run() if report.status == 'active' else None
                report.save()
                return JsonResponse({'success': True, 'status': report.status})
            
            elif action == 'delete':
                report.delete()
                return JsonResponse({'success': True})
            
            elif action == 'run_now':
                from apps.core.tasks import generate_security_report
                task = generate_security_report.delay(str(report.id))
                return JsonResponse({'success': True, 'task_id': task.id})
            
            else:
                report.name = request.POST.get('name', report.name)
                report.recipients = request.POST.get('recipients', report.recipients)
                if request.POST.get('time_of_day'):
                    report.time_of_day = datetime.strptime(request.POST.get('time_of_day'), '%H:%M').time()
                report.date_range_days = int(request.POST.get('date_range_days', report.date_range_days))
                report.include_charts = request.POST.get('include_charts') == 'on'
                report.include_tables = request.POST.get('include_tables') == 'on'
                report.include_recommendations = request.POST.get('include_recommendations') == 'on'
                report.save()
                
                messages.success(request, f'Report "{report.name}" updated successfully!')
                return JsonResponse({'success': True})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@admin_required
def report_run_history(request, report_id):
    """View run history for a report"""
    report = get_object_or_404(ScheduledReport, id=report_id, created_by=request.user)
    history = report.run_history.all()
    
    context = {
        'report': report,
        'history': history,
    }
    return render(request, 'core/admin/security/report_history.html', context)


@admin_required
def export_security_report(request):
    """Export security report as CSV"""
    from django.http import HttpResponse
    import csv
    
    report_type = request.GET.get('type', 'daily')
    date_range = request.GET.get('date_range', 'last7days')
    export_format = request.GET.get('format', 'csv')
    
    now = timezone.now()
    if date_range == 'last7days':
        start_date = now - timedelta(days=7)
    elif date_range == 'last30days':
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=7)
    
    events = SecurityEvent.objects.filter(created_at__gte=start_date)
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="security_report_{date_range}_{now.date()}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'Event Type', 'Severity', 'IP Address', 'Path', 'Method', 'Details'])
        
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
        
        return response
    
    return HttpResponse("PDF export coming soon")



def get_country_from_ip(ip_address):
    """Get country from IP address (mock function)"""
    # In production, use MaxMind GeoIP or similar
    country_map = {
        '185.220.101': 'Germany',
        '45.142.120': 'Netherlands',
        '103.145.12': 'China',
        '198.51.100': 'United States',
        '203.0.113': 'Russia',
        '192.168': 'Local Network',
        '10.0': 'Private Network',
        '172.16': 'Private Network',
    }
    
    for prefix, country in country_map.items():
        if ip_address.startswith(prefix):
            return country
    
    # Random assignment for demo
    countries = ['United States', 'China', 'Russia', 'Germany', 'Netherlands', 'Brazil', 'India', 'Vietnam']
    import hashlib
    hash_val = int(hashlib.md5(ip_address.encode()).hexdigest(), 16)
    return countries[hash_val % len(countries)]


@admin_required
def ip_lookup(request):
    """IP reputation lookup"""
    context = {}
    if request.method == 'POST':
        ip_address = request.POST.get('ip_address')
        # You can implement actual IP lookup here
        context['ip_address'] = ip_address
        context['reputation'] = {
            'score': 75,
            'risk_level': 'HIGH',
            'malicious_count': 12,
            'suspicious_count': 5,
            'clean_count': 45,
            'country': 'Germany',
            'city': 'Berlin',
            'isp': 'Example ISP',
            'org': 'Example Organization',
            'detections': [
                {'engine': 'VirusTotal', 'category': 'malicious', 'result': 'Tor Exit Node'},
                {'engine': 'AbuseIPDB', 'category': 'malicious', 'result': 'SSH Brute Force'},
                {'engine': 'AlienVault', 'category': 'suspicious', 'result': 'Scanner'},
            ]
        }
    return render(request, 'core/admin/security/ip_lookup.html', context)