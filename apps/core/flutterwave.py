import requests
import hashlib
import hmac
import json
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class FlutterwaveService:
    """Flutterwave payment gateway integration"""
    
    def __init__(self):
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY
        self.public_key = settings.FLUTTERWAVE_PUBLIC_KEY
        self.encryption_key = settings.FLUTTERWAVE_ENCRYPTION_KEY
        self.base_url = settings.FLUTTERWAVE_BASE_URL
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    def initialize_payment(self, amount, email, tx_ref, customer_name, phone_number=None):
        """
        Initialize payment with Flutterwave
        """
        try:
            payload = {
                "tx_ref": tx_ref,
                "amount": str(amount),
                "currency": "NGN",
                "redirect_url": f"{settings.SITE_URL}/api/payments/verify/",
                "payment_options": "card,banktransfer,ussd",
                "customer": {
                    "email": email,
                    "name": customer_name,
                    "phonenumber": phone_number or ""
                },
                "customizations": {
                    "title": "Vehicle Insurance Pro",
                    "description": "Insurance Premium Payment",
                    "logo": f"{settings.SITE_URL}/static/images/logo.png"
                },
                "meta": {
                    "consumer_id": tx_ref,
                    "consumer_mac": hashlib.md5(email.encode()).hexdigest()
                }
            }
            
            response = requests.post(
                f"{self.base_url}/payments",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return {
                        'success': True,
                        'data': data['data'],
                        'link': data['data']['link']
                    }
                else:
                    return {'success': False, 'error': data.get('message', 'Payment initialization failed')}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Flutterwave initialization error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def verify_payment(self, transaction_id):
        """
        Verify payment with Flutterwave
        """
        try:
            response = requests.get(
                f"{self.base_url}/transactions/{transaction_id}/verify",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    transaction = data['data']
                    return {
                        'success': True,
                        'status': transaction['status'],
                        'amount': transaction['amount'],
                        'currency': transaction['currency'],
                        'tx_ref': transaction['tx_ref'],
                        'transaction_id': transaction['id']
                    }
                else:
                    return {'success': False, 'error': data.get('message', 'Verification failed')}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Flutterwave verification error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_subaccount(self, account_bank, account_number, business_name, split_type='percentage', split_value=5):
        """
        Create subaccount for merchants (for marketplace functionality)
        """
        try:
            payload = {
                "account_bank": account_bank,
                "account_number": account_number,
                "business_name": business_name,
                "business_mobile": "",
                "business_email": "",
                "country": "NG",
                "split_type": split_type,
                "split_value": split_value
            }
            
            response = requests.post(
                f"{self.base_url}/subaccounts",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return {'success': True, 'subaccount_id': data['data']['id']}
                else:
                    return {'success': False, 'error': data.get('message', 'Subaccount creation failed')}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Flutterwave subaccount creation error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def refund_payment(self, transaction_id, amount=None):
        """
        Process refund for a payment
        """
        try:
            payload = {}
            if amount:
                payload['amount'] = str(amount)
            
            response = requests.post(
                f"{self.base_url}/transactions/{transaction_id}/refund",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return {'success': True, 'refund_id': data['data']['id']}
                else:
                    return {'success': False, 'error': data.get('message', 'Refund failed')}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Flutterwave refund error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_banks(self, country='NG'):
        """
        Get list of banks for a country
        """
        cache_key = f'flutterwave_banks_{country}'
        banks = cache.get(cache_key)
        
        if not banks:
            try:
                response = requests.get(
                    f"{self.base_url}/banks/{country}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'success':
                        banks = data['data']
                        cache.set(cache_key, banks, 3600)  # Cache for 1 hour
                        return {'success': True, 'banks': banks}
                    else:
                        return {'success': False, 'error': data.get('message', 'Failed to fetch banks')}
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                logger.error(f"Flutterwave get banks error: {str(e)}")
                return {'success': False, 'error': str(e)}
        
        return {'success': True, 'banks': banks}
    
    def verify_account_number(self, account_number, bank_code):
        """
        Verify bank account number
        """
        try:
            payload = {
                "account_number": account_number,
                "account_bank": bank_code
            }
            
            response = requests.post(
                f"{self.base_url}/accounts/resolve",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return {
                        'success': True,
                        'account_name': data['data']['account_name']
                    }
                else:
                    return {'success': False, 'error': data.get('message', 'Account verification failed')}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Flutterwave account verification error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def webhook_verification(self, request):
        """
        Verify Flutterwave webhook signature
        """
        signature = request.headers.get('verif-hash')
        if not signature:
            return False
        
        return signature == settings.FLUTTERWAVE_WEBHOOK_SECRET

# Initialize Flutterwave service
flutterwave_service = FlutterwaveService()