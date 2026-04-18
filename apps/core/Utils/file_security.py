"""
Enterprise File Security - Virus Scanning and Malware Detection
"""
import os
import hashlib
import logging
import requests
import magic
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError

logger = logging.getLogger('security')


class FileSecurityScanner:
    """Enterprise file security scanner with multiple engines"""
    
    # File type restrictions
    ALLOWED_MIME_TYPES = {
        'image': ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
        'document': ['application/pdf', 'application/msword', 
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.ms-excel',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        'archive': ['application/zip', 'application/x-rar-compressed'],
    }
    
    # Dangerous file extensions
    BLOCKED_EXTENSIONS = [
        '.exe', '.dll', '.so', '.sh', '.bash', '.bat', '.cmd', '.ps1',
        '.vbs', '.js', '.php', '.asp', '.aspx', '.jsp', '.py', '.pl',
        '.rb', '.elf', '.deb', '.rpm', '.msi', '.scr', '.cpl'
    ]
    
    # Maximum file sizes (bytes)
    MAX_FILE_SIZES = {
        'image': 5 * 1024 * 1024,      # 5MB
        'document': 10 * 1024 * 1024,   # 10MB
        'default': 20 * 1024 * 1024     # 20MB
    }
    
    def __init__(self):
        self.vt_api_key = getattr(settings, 'VIRUSTOTAL_API_KEY', None)
        self.metadefender_api_key = getattr(settings, 'METADEFENDER_API_KEY', None)
    
    def scan_file(self, file: UploadedFile, file_type: str = 'document') -> dict:
        """
        Comprehensive file scanning
        Returns: {'safe': bool, 'threats': list, 'score': int}
        """
        threats = []
        score = 0
        
        # 1. Extension check
        ext = os.path.splitext(file.name)[1].lower()
        if ext in self.BLOCKED_EXTENSIONS:
            threats.append(f"Blocked extension: {ext}")
            score = 100
        
        # 2. MIME type validation
        mime = magic.from_buffer(file.read(1024), mime=True)
        file.seek(0)
        
        if mime not in self.ALLOWED_MIME_TYPES.get(file_type, []):
            threats.append(f"Suspicious MIME type: {mime}")
            score += 30
        
        # 3. File size check
        max_size = self.MAX_FILE_SIZES.get(file_type, self.MAX_FILE_SIZES['default'])
        if file.size > max_size:
            threats.append(f"File too large: {file.size} bytes")
            score += 10
        
        # 4. Magic bytes validation
        if not self.validate_magic_bytes(file):
            threats.append("Invalid file signature")
            score += 40
        
        # 5. VirusTotal scan (if API key available)
        if self.vt_api_key:
            vt_result = self.scan_virustotal(file)
            if vt_result['malicious']:
                threats.extend(vt_result['threats'])
                score = max(score, vt_result['score'])
        
        # 6. MetaDefender scan (if API key available)
        if self.metadefender_api_key:
            md_result = self.scan_metadefender(file)
            if md_result['malicious']:
                threats.extend(md_result['threats'])
                score = max(score, md_result['score'])
        
        # 7. YARA rules scan
        yara_threats = self.scan_yara(file)
        if yara_threats:
            threats.extend(yara_threats)
            score = max(score, 60)
        
        # 8. Content analysis for macros/scripts
        if self.contains_malicious_content(file, mime):
            threats.append("Suspicious content detected")
            score = max(score, 50)
        
        # Calculate file hash
        file_hash = self.calculate_hash(file)
        
        # Check against local threat database
        if self.is_known_malicious(file_hash):
            threats.append("Known malicious file hash")
            score = 100
        
        return {
            'safe': score < 30 and len(threats) == 0,
            'threats': threats,
            'score': score,
            'hash': file_hash,
            'mime_type': mime,
            'size': file.size
        }
    
    def validate_magic_bytes(self, file: UploadedFile) -> bool:
        """Validate file magic bytes/signature"""
        file.seek(0)
        header = file.read(8)
        file.seek(0)
        
        # Common file signatures
        signatures = {
            b'\x89PNG\r\n\x1a\n': 'PNG',
            b'\xff\xd8\xff': 'JPEG',
            b'GIF87a': 'GIF',
            b'GIF89a': 'GIF',
            b'%PDF': 'PDF',
            b'PK\x03\x04': 'ZIP/DOCX/XLSX',
            b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': 'DOC/XLS',
        }
        
        for sig, name in signatures.items():
            if header.startswith(sig):
                return True
        
        return False
    
    def scan_virustotal(self, file: UploadedFile) -> dict:
        """Scan file with VirusTotal API"""
        if not self.vt_api_key:
            return {'malicious': False, 'threats': [], 'score': 0}
        
        try:
            # Upload file
            url = "https://www.virustotal.com/api/v3/files"
            headers = {"x-apikey": self.vt_api_key}
            
            file.seek(0)
            files = {"file": (file.name, file.read())}
            response = requests.post(url, headers=headers, files=files, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                analysis_id = data['data']['id']
                
                # Get analysis results
                analysis_url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
                analysis_response = requests.get(analysis_url, headers=headers, timeout=30)
                
                if analysis_response.status_code == 200:
                    analysis = analysis_response.json()
                    stats = analysis['data']['attributes']['stats']
                    
                    threats = []
                    if stats['malicious'] > 0:
                        results = analysis['data']['attributes']['results']
                        for engine, result in results.items():
                            if result['category'] == 'malicious':
                                threats.append(f"VT/{engine}: {result['result']}")
                    
                    return {
                        'malicious': stats['malicious'] > 0,
                        'threats': threats,
                        'score': stats['malicious'] * 10
                    }
        except Exception as e:
            logger.error(f"VirusTotal scan failed: {e}")
        
        return {'malicious': False, 'threats': [], 'score': 0}
    
    def scan_metadefender(self, file: UploadedFile) -> dict:
        """Scan file with MetaDefender Cloud API"""
        if not self.metadefender_api_key:
            return {'malicious': False, 'threats': [], 'score': 0}
        
        try:
            url = "https://api.metadefender.com/v4/file"
            headers = {
                "apikey": self.metadefender_api_key,
                "filename": file.name
            }
            
            file.seek(0)
            response = requests.post(url, headers=headers, data=file.read(), timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                scan_results = data.get('scan_results', {})
                
                threats = []
                total_detections = scan_results.get('total_detected_avs', 0)
                
                if total_detections > 0:
                    for engine, result in scan_results.get('scan_details', {}).items():
                        if result.get('threat_found'):
                            threats.append(f"MD/{engine}: {result['threat_found']}")
                
                return {
                    'malicious': total_detections > 0,
                    'threats': threats,
                    'score': total_detections * 10
                }
        except Exception as e:
            logger.error(f"MetaDefender scan failed: {e}")
        
        return {'malicious': False, 'threats': [], 'score': 0}
    
    def scan_yara(self, file: UploadedFile) -> list:
        """Scan file with YARA rules"""
        threats = []
        
        try:
            import yara
            
            # Load compiled rules
            rules_path = os.path.join(settings.BASE_DIR, 'security', 'yara_rules.yar')
            if os.path.exists(rules_path):
                rules = yara.compile(rules_path)
                
                file.seek(0)
                matches = rules.match(data=file.read())
                
                for match in matches:
                    threats.append(f"YARA/{match.rule}: {match.meta.get('description', 'Suspicious pattern')}")
        except ImportError:
            pass  # yara-python not installed
        except Exception as e:
            logger.error(f"YARA scan failed: {e}")
        
        return threats
    
    def contains_malicious_content(self, file: UploadedFile, mime_type: str) -> bool:
        """Check for malicious content like macros, scripts"""
        file.seek(0)
        content = file.read(10240).decode('utf-8', errors='ignore')
        file.seek(0)
        
        # Patterns to detect
        patterns = [
            r'<script', r'javascript:', r'eval\(', r'exec\(',
            r'AutoOpen', r'Auto_Open', r'Workbook_Open',  # Excel macros
            r'Document_Open',  # Word macros
            r'Shell\(', r'WScript\.Shell', r'CreateObject',
            r'powershell', r'cmd\.exe', r'bitsadmin',
        ]
        
        import re
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def calculate_hash(self, file: UploadedFile) -> str:
        """Calculate SHA-256 hash of file"""
        file.seek(0)
        sha256 = hashlib.sha256()
        for chunk in file.chunks():
            sha256.update(chunk)
        file.seek(0)
        return sha256.hexdigest()
    
    def is_known_malicious(self, file_hash: str) -> bool:
        """Check if file hash is in local threat database"""
        try:
            from apps.core.models import ThreatIntel
            return ThreatIntel.objects.filter(
                intel_type='hash',
                value=file_hash,
                is_active=True
            ).exists()
        except:
            return False


class ThreatIntelligenceService:
    """Integrate with external threat intelligence APIs"""
    
    def __init__(self):
        self.vt_api_key = getattr(settings, 'VIRUSTOTAL_API_KEY', None)
        self.abuseipdb_api_key = getattr(settings, 'ABUSEIPDB_API_KEY', None)
        self.shodan_api_key = getattr(settings, 'SHODAN_API_KEY', None)
        self.alienvault_api_key = getattr(settings, 'ALIENVAULT_API_KEY', None)
    
    def check_ip_reputation(self, ip_address: str) -> dict:
        """Check IP reputation across multiple sources"""
        reputation = {
            'score': 0,
            'malicious': False,
            'reports': [],
            'categories': []
        }
        
        # VirusTotal
        if self.vt_api_key:
            vt_result = self.check_virustotal_ip(ip_address)
            reputation['score'] += vt_result['score']
            reputation['reports'].extend(vt_result['reports'])
            reputation['categories'].extend(vt_result['categories'])
        
        # AbuseIPDB
        if self.abuseipdb_api_key:
            abuse_result = self.check_abuseipdb(ip_address)
            reputation['score'] += abuse_result['score']
            reputation['reports'].extend(abuse_result['reports'])
            reputation['categories'].extend(abuse_result['categories'])
        
        # Shodan
        if self.shodan_api_key:
            shodan_result = self.check_shodan(ip_address)
            reputation['score'] += shodan_result['score']
            reputation['reports'].extend(shodan_result['reports'])
        
        reputation['malicious'] = reputation['score'] >= 30
        
        # Save to local threat intel if malicious
        if reputation['malicious']:
            self.save_threat_intel(ip_address, 'ip', reputation)
        
        return reputation
    
    def check_virustotal_ip(self, ip: str) -> dict:
        """Check IP on VirusTotal"""
        try:
            url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
            headers = {"x-apikey": self.vt_api_key}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                attrs = data['data']['attributes']
                stats = attrs['last_analysis_stats']
                
                score = stats['malicious'] * 10 + stats['suspicious'] * 5
                
                return {
                    'score': min(score, 100),
                    'reports': [f"VirusTotal: {stats['malicious']} malicious, {stats['suspicious']} suspicious"],
                    'categories': list(attrs.get('categories', {}).keys())
                }
        except Exception as e:
            logger.error(f"VirusTotal IP check failed: {e}")
        
        return {'score': 0, 'reports': [], 'categories': []}
    
    def check_abuseipdb(self, ip: str) -> dict:
        """Check IP on AbuseIPDB"""
        try:
            url = "https://api.abuseipdb.com/api/v2/check"
            headers = {"Key": self.abuseipdb_api_key, "Accept": "application/json"}
            params = {"ipAddress": ip, "maxAgeInDays": 90}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()['data']
                score = min(data['abuseConfidenceScore'], 100)
                
                return {
                    'score': score,
                    'reports': [f"AbuseIPDB: {data['totalReports']} reports, {score}% confidence"],
                    'categories': []
                }
        except Exception as e:
            logger.error(f"AbuseIPDB check failed: {e}")
        
        return {'score': 0, 'reports': [], 'categories': []}
    
    def check_shodan(self, ip: str) -> dict:
        """Check IP on Shodan"""
        try:
            url = f"https://api.shodan.io/shodan/host/{ip}"
            params = {"key": self.shodan_api_key}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                ports = len(data.get('ports', []))
                vulns = data.get('vulns', [])
                
                score = min(ports * 2 + len(vulns) * 10, 100)
                
                return {
                    'score': score,
                    'reports': [f"Shodan: {ports} open ports, {len(vulns)} vulnerabilities"],
                    'categories': []
                }
        except Exception as e:
            logger.error(f"Shodan check failed: {e}")
        
        return {'score': 0, 'reports': [], 'categories': []}
    
    def save_threat_intel(self, value: str, intel_type: str, reputation: dict):
        """Save threat intelligence to database"""
        try:
            from apps.core.models import ThreatIntel
            
            ThreatIntel.objects.update_or_create(
                intel_type=intel_type,
                value=value,
                defaults={
                    'threat_score': reputation['score'],
                    'description': '; '.join(reputation['reports']),
                    'source': 'api',
                    'last_seen': timezone.now(),
                    'is_active': True
                }
            )
        except Exception as e:
            logger.error(f"Failed to save threat intel: {e}")
    
    def check_domain_reputation(self, domain: str) -> dict:
        """Check domain reputation"""
        reputation = {'score': 0, 'malicious': False, 'reports': []}
        
        if self.vt_api_key:
            try:
                url = f"https://www.virustotal.com/api/v3/domains/{domain}"
                headers = {"x-apikey": self.vt_api_key}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    stats = data['data']['attributes']['last_analysis_stats']
                    score = stats['malicious'] * 10 + stats['suspicious'] * 5
                    
                    reputation['score'] = min(score, 100)
                    reputation['reports'].append(f"VirusTotal: {stats['malicious']} malicious")
                    reputation['malicious'] = reputation['score'] >= 30
            except Exception as e:
                logger.error(f"Domain reputation check failed: {e}")
        
        return reputation