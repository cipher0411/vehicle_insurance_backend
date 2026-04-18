"""
Enterprise Security Middleware
Includes: WAF, Rate Limiting, Bot Detection, SQL Injection Prevention
"""
import re
import time
import logging
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden, JsonResponse
from django.utils.deprecation import MiddlewareMixin

# Try to import optional dependencies with fallbacks
try:
    from ipware import get_client_ip
except ImportError:
    # Fallback function if django-ipware is not installed
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

try:
    import user_agents
    HAS_USER_AGENTS = True
except ImportError:
    HAS_USER_AGENTS = False
    user_agents = None

logger = logging.getLogger('security')


class WebApplicationFirewallMiddleware(MiddlewareMixin):
    """Enterprise WAF with SQLi, XSS, and attack pattern detection"""
    
    SQLI_PATTERNS = [
        r"(?i)(\bUNION\b.*\bSELECT\b)",
        r"(?i)(\bSELECT\b.*\bFROM\b.*\bWHERE\b)",
        r"(?i)(\bDROP\b.*\bTABLE\b)",
        r"(?i)(\bINSERT\b.*\bINTO\b)",
        r"(?i)(\bDELETE\b.*\bFROM\b)",
        r"(?i)(\bUPDATE\b.*\bSET\b)",
        r"(?i)(--|\#|/\*|\*/)",
    ]
    
    XSS_PATTERNS = [
        r"(?i)<script.*?>.*?</script>",
        r"(?i)javascript:",
        r"(?i)onload\s*=",
        r"(?i)onerror\s*=",
    ]
    
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
    ]
    
    def process_request(self, request):
        if request.path.startswith(('/static/', '/media/')):
            return None
        
        client_ip = get_client_ip(request)
        
        if cache.get(f"blocked_ip:{client_ip}"):
            return HttpResponseForbidden("Access Denied")
        
        if self.is_rate_limited(client_ip, request.path):
            return JsonResponse({'error': 'Too many requests'}, status=429)
        
        # Inspect GET parameters
        if request.GET:
            for key, value in request.GET.items():
                if self.detect_attack_patterns(str(value)):
                    logger.warning(f"Attack detected from {client_ip}")
                    cache.set(f"blocked_ip:{client_ip}", True, 3600)
                    return HttpResponseForbidden("Access Denied")
        
        # Inspect POST data
        if request.method == 'POST' and request.POST:
            for key, value in request.POST.items():
                if key == 'csrfmiddlewaretoken':
                    continue
                if self.detect_attack_patterns(str(value)):
                    logger.warning(f"Attack detected from {client_ip}")
                    cache.set(f"blocked_ip:{client_ip}", True, 3600)
                    return HttpResponseForbidden("Access Denied")
        
        return None
    
    def detect_attack_patterns(self, value):
        if not value:
            return False
        for pattern in self.SQLI_PATTERNS + self.XSS_PATTERNS:
            if re.search(pattern, value):
                return True
        return False
    
    def is_rate_limited(self, ip, path):
        limits = {'/api/': (100, 60), '/login/': (5, 60), '/register/': (3, 60), 'default': (200, 60)}
        limit, window = limits.get(path, limits['default'])
        for pattern, (l, w) in limits.items():
            if pattern in path:
                limit, window = l, w
                break
        
        key = f"rate_limit:{ip}:{path}"
        count = cache.get(key, 0)
        if count >= limit:
            return True
        cache.set(key, count + 1, window)
        return False


class ThreatIntelligenceMiddleware(MiddlewareMixin):
    """Integrate with threat intelligence feeds"""
    
    def process_request(self, request):
        if request.path.startswith(('/static/', '/media/')):
            return None
        
        client_ip = get_client_ip(request)
        
        try:
            from apps.core.models import ThreatIntel
            if ThreatIntel.objects.filter(intel_type='ip', value=client_ip, is_active=True).exists():
                logger.warning(f"Blocked known malicious IP: {client_ip}")
                return HttpResponseForbidden("Access Denied")
        except:
            pass
        
        return None


class BotDetectionMiddleware(MiddlewareMixin):
    """Advanced bot detection using multiple signals"""
    
    def process_request(self, request):
        if request.path.startswith(('/static/', '/media/')):
            return None
        
        client_ip = get_client_ip(request)
        ua_string = request.META.get('HTTP_USER_AGENT', '')
        
        signals = []
        
        if not ua_string:
            signals.append('missing_ua')
        
        bot_patterns = ['bot', 'crawler', 'spider', 'scraper', 'scan']
        if any(pattern in ua_string.lower() for pattern in bot_patterns):
            if 'googlebot' not in ua_string.lower() and 'bingbot' not in ua_string.lower():
                signals.append('bot_ua')
        
        if not request.META.get('HTTP_ACCEPT'):
            signals.append('no_accept')
        
        if len(signals) >= 2:
            cache_key = f"bot_detected:{client_ip}"
            count = cache.get(cache_key, 0)
            cache.set(cache_key, count + 1, 86400)
            
            if count > 5:
                logger.warning(f"Blocked bot from IP: {client_ip}")
                return HttpResponseForbidden("Access Denied")
        
        return None