from rest_framework import generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import *
from .permissions import *
from .throttling import *
from apps.core.models import *
from apps.core.utils import generate_otp, send_otp_email, send_otp_sms
from apps.core.flutterwave import flutterwave_service
import uuid
import json
import logging

logger = logging.getLogger(__name__)

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterThrottle]
    
    def perform_create(self, serializer):
        user = serializer.save()
        # Send welcome email
        send_mail(
            'Welcome to Vehicle Insurance Pro',
            f'Hi {user.first_name},\n\nWelcome to Vehicle Insurance Pro! Get started with your first quote today.',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginThrottle]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(email=serializer.validated_data['email'], 
                           password=serializer.validated_data['password'])
        
        if not user:
            return Response({'error': 'Invalid credentials'}, 
                          status=status.HTTP_401_UNAUTHORIZED)
        
        refresh = RefreshToken.for_user(user)
        
        # Log user activity
        UserActivityLog.objects.create(
            user=user,
            action='login',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={}
        )
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Log user activity
            UserActivityLog.objects.create(
                user=request.user,
                action='logout',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={}
            )
            
            return Response({'message': 'Successfully logged out'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'error': 'Old password is incorrect'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({'message': 'Password changed successfully'})

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ForgotPasswordThrottle]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        
        if user:
            otp = generate_otp()
            # Store OTP in cache or database
            # Send OTP via email and SMS
            send_otp_email(user.email, otp)
            if user.phone_number:
                send_otp_sms(str(user.phone_number), otp)
        
        return Response({'message': 'If the email exists, an OTP has been sent'})

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verify token and reset password
        # Implementation depends on your OTP/Token storage
        
        return Response({'message': 'Password reset successful'})

class VehicleListCreateView(generics.ListCreateAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['registration_number', 'make', 'model']
    ordering_fields = ['year', 'created_at']
    
    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class VehicleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user)

class PolicyListView(generics.ListAPIView):
    serializer_class = InsurancePolicySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['policy_number']
    ordering_fields = ['created_at', 'premium_amount', 'start_date', 'end_date']
    
    def get_queryset(self):
        queryset = InsurancePolicy.objects.filter(user=self.request.user)
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by policy type
        policy_type = self.request.query_params.get('policy_type')
        if policy_type:
            queryset = queryset.filter(policy_type=policy_type)
        
        return queryset

class PolicyDetailView(generics.RetrieveAPIView):
    serializer_class = InsurancePolicySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        return InsurancePolicy.objects.filter(user=self.request.user)

class ClaimListView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['claim_number']
    ordering_fields = ['created_at', 'claimed_amount']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClaimCreateSerializer
        return ClaimSerializer
    
    def get_queryset(self):
        queryset = Claim.objects.filter(user=self.request.user)
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by claim type
        claim_type = self.request.query_params.get('claim_type')
        if claim_type:
            queryset = queryset.filter(claim_type=claim_type)
        
        return queryset
    
    def perform_create(self, serializer):
        claim = serializer.save(user=self.request.user)
        # Send notification to user
        Notification.objects.create(
            user=self.request.user,
            title='Claim Submitted',
            message=f'Your claim #{claim.claim_number} has been submitted successfully',
            notification_type='claim_update',
            data={'claim_id': str(claim.id)}
        )

class ClaimDetailView(generics.RetrieveAPIView):
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        return Claim.objects.filter(user=self.request.user)

class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['-created_at']
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

class QuoteGenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = QuoteGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        vehicle = get_object_or_404(Vehicle, id=serializer.validated_data['vehicle_id'], 
                                    user=request.user)
        
        # Calculate premium based on vehicle and coverage
        base_premium = self.calculate_base_premium(vehicle)
        coverage_amount = serializer.validated_data['coverage_amount']
        coverage_type = serializer.validated_data['coverage_type']
        add_ons = serializer.validated_data.get('add_ons', [])
        
        # Calculate total premium
        coverage_factor = coverage_amount / 5000000
        type_factor = 1.2 if coverage_type == 'premium' else 1.0 if coverage_type == 'standard' else 0.8
        add_on_cost = len(add_ons) * 5000
        
        total_premium = base_premium * coverage_factor * type_factor + add_on_cost
        
        quote = InsuranceQuote.objects.create(
            user=request.user,
            vehicle=vehicle,
            coverage_type=coverage_type,
            base_premium=base_premium,
            total_premium=total_premium,
            coverage_amount=coverage_amount,
            add_ons=add_ons,
            valid_until=timezone.now() + timezone.timedelta(days=30)
        )
        
        return Response(InsuranceQuoteSerializer(quote).data)
    
    def calculate_base_premium(self, vehicle):
        # Premium calculation logic
        base_rate = 5000
        age_factor = vehicle.vehicle_age * 0.05
        return base_rate * (1 + age_factor)

class QuoteListView(generics.ListAPIView):
    serializer_class = InsuranceQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return InsuranceQuote.objects.filter(user=self.request.user).order_by('-created_at')

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Mark as read when fetching
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return response

class MarkNotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({'message': 'Marked as read'})

class SupportTicketCreateView(generics.CreateAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class SupportTicketListView(generics.ListAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user).order_by('-created_at')

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        stats = {
            'active_policies': InsurancePolicy.objects.filter(
                user=user, status='active'
            ).count(),
            'total_claims': Claim.objects.filter(user=user).count(),
            'pending_claims': Claim.objects.filter(
                user=user, status='pending'
            ).count(),
            'total_premium_paid': Payment.objects.filter(
                user=user, status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'active_vehicles': Vehicle.objects.filter(user=user).count(),
            'recent_activities': UserActivityLog.objects.filter(
                user=user
            )[:10].values('action', 'created_at')
        }
        
        return Response(stats)

class UploadDocumentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        document_type = request.data.get('document_type')
        document_file = request.FILES.get('document_file')
        
        if not document_type or not document_file:
            return Response({'error': 'document_type and document_file required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        document = Document.objects.create(
            user=request.user,
            document_type=document_type,
            document_file=document_file,
            document_number=request.data.get('document_number', '')
        )
        
        return Response({
            'message': 'Document uploaded successfully',
            'document_id': str(document.id)
        })

class ValidatePromoCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        code = request.data.get('code')
        try:
            promo = PromoCode.objects.get(code=code, is_active=True)
            if promo.is_valid:
                return Response({
                    'valid': True,
                    'discount_type': promo.discount_type,
                    'discount_value': promo.discount_value
                })
        except PromoCode.DoesNotExist:
            pass
        
        return Response({'valid': False}, status=status.HTTP_404_NOT_FOUND)

class InitiatePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        policy_id = request.data.get('policy_id')
        payment_method = request.data.get('payment_method')
        promo_code = request.data.get('promo_code')
        
        policy = get_object_or_404(InsurancePolicy, id=policy_id, user=request.user)
        
        amount = policy.premium_amount
        
        # Apply promo code if provided
        if promo_code:
            try:
                promo = PromoCode.objects.get(code=promo_code, is_active=True)
                if promo.is_valid:
                    if promo.discount_type == 'percentage':
                        amount -= amount * (promo.discount_value / 100)
                    else:
                        amount -= promo.discount_value
                    promo.used_count += 1
                    promo.save()
            except PromoCode.DoesNotExist:
                pass
        
        # Create payment record
        payment = Payment.objects.create(
            policy=policy,
            user=request.user,
            amount=amount,
            payment_method=payment_method,
            payment_reference=f"REF-{uuid.uuid4().hex[:12].upper()}"
        )
        
        # Initialize payment with gateway
        if payment_method == 'card':
            # Initialize Stripe/Paystack payment
            pass
        
        return Response({
            'payment_id': str(payment.id),
            'amount': amount,
            'reference': payment.payment_reference
        })

class PaymentCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        reference = request.data.get('reference')
        status = request.data.get('status')
        
        try:
            payment = Payment.objects.get(payment_reference=reference)
            if status == 'success':
                payment.status = 'completed'
                payment.paid_at = timezone.now()
                payment.save()
                
                # Activate policy
                policy = payment.policy
                policy.status = 'active'
                policy.save()
                
                # Send notification
                Notification.objects.create(
                    user=payment.user,
                    title='Payment Successful',
                    message=f'Your payment of ₦{payment.amount:,.2f} for policy {policy.policy_number} was successful',
                    notification_type='payment_confirmation',
                    data={'payment_id': str(payment.id)}
                )
            else:
                payment.status = 'failed'
                payment.save()
            
            return Response({'status': 'success'})
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        
        
        
        
        
# ... (keep all existing views from before, only updating payment-related views)

class InitiatePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        policy_id = request.data.get('policy_id')
        payment_method = request.data.get('payment_method', 'card')
        promo_code = request.data.get('promo_code')
        
        policy = get_object_or_404(InsurancePolicy, id=policy_id, user=request.user)
        
        amount = float(policy.premium_amount)
        
        # Apply promo code if provided
        if promo_code:
            try:
                promo = PromoCode.objects.get(code=promo_code, is_active=True)
                if promo.is_valid:
                    if promo.discount_type == 'percentage':
                        amount -= amount * (float(promo.discount_value) / 100)
                    else:
                        amount -= float(promo.discount_value)
                    promo.used_count += 1
                    promo.save()
            except PromoCode.DoesNotExist:
                pass
        
        # Generate unique transaction reference
        tx_ref = f"INS-{uuid.uuid4().hex[:12].upper()}"
        
        # Create payment record
        payment = Payment.objects.create(
            policy=policy,
            user=request.user,
            amount=amount,
            payment_method=payment_method,
            payment_reference=tx_ref,
            status='pending'
        )
        
        # Initialize Flutterwave payment
        flutterwave_response = flutterwave_service.initialize_payment(
            amount=amount,
            email=request.user.email,
            tx_ref=tx_ref,
            customer_name=request.user.get_full_name(),
            phone_number=str(request.user.phone_number) if request.user.phone_number else None
        )
        
        if flutterwave_response['success']:
            return Response({
                'success': True,
                'payment_id': str(payment.id),
                'amount': amount,
                'reference': tx_ref,
                'payment_link': flutterwave_response['link'],
                'flutterwave_data': flutterwave_response['data']
            })
        else:
            payment.status = 'failed'
            payment.save()
            return Response({
                'success': False,
                'error': flutterwave_response.get('error', 'Payment initialization failed')
            }, status=status.HTTP_400_BAD_REQUEST)

class PaymentVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        transaction_id = request.query_params.get('transaction_id')
        tx_ref = request.query_params.get('tx_ref')
        
        if not transaction_id or not tx_ref:
            return Response({'error': 'Missing parameters'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify payment with Flutterwave
        verification = flutterwave_service.verify_payment(transaction_id)
        
        if verification['success'] and verification['status'] == 'successful':
            try:
                payment = Payment.objects.get(payment_reference=tx_ref)
                
                if payment.status != 'completed':
                    payment.status = 'completed'
                    payment.transaction_id = str(verification['transaction_id'])
                    payment.paid_at = timezone.now()
                    payment.save()
                    
                    # Activate policy
                    policy = payment.policy
                    policy.status = 'active'
                    policy.save()
                    
                    # Send notification
                    Notification.objects.create(
                        user=payment.user,
                        title='Payment Successful',
                        message=f'Your payment of ₦{payment.amount:,.2f} for policy {policy.policy_number} was successful',
                        notification_type='payment_confirmation',
                        data={'payment_id': str(payment.id)}
                    )
                    
                    # Send email confirmation
                    send_mail(
                        'Payment Confirmation - Vehicle Insurance Pro',
                        f"""
                        Dear {payment.user.get_full_name()},
                        
                        Your payment has been successfully processed!
                        
                        Payment Details:
                        • Transaction ID: {payment.transaction_id}
                        • Amount: ₦{payment.amount:,.2f}
                        • Policy Number: {policy.policy_number}
                        • Date: {payment.paid_at}
                        
                        Your policy is now active. You can download your policy document from your dashboard.
                        
                        Thank you for choosing Vehicle Insurance Pro.
                        
                        Best regards,
                        Vehicle Insurance Pro Team
                        """,
                        settings.DEFAULT_FROM_EMAIL,
                        [payment.user.email],
                        fail_silently=True,
                    )
                
                return Response({
                    'success': True,
                    'message': 'Payment verified successfully',
                    'payment_status': 'completed'
                })
                
            except Payment.DoesNotExist:
                return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'success': False,
                'error': verification.get('error', 'Payment verification failed'),
                'payment_status': 'failed'
            }, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class FlutterwaveWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        # Verify webhook signature
        if not flutterwave_service.webhook_verification(request):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            payload = json.loads(request.body)
            event = payload.get('event')
            
            if event == 'charge.completed':
                data = payload.get('data', {})
                tx_ref = data.get('tx_ref')
                transaction_id = data.get('id')
                status = data.get('status')
                
                if status == 'successful':
                    try:
                        payment = Payment.objects.get(payment_reference=tx_ref)
                        
                        if payment.status != 'completed':
                            payment.status = 'completed'
                            payment.transaction_id = str(transaction_id)
                            payment.paid_at = timezone.now()
                            payment.save()
                            
                            # Activate policy
                            policy = payment.policy
                            policy.status = 'active'
                            policy.save()
                            
                            # Send notification
                            Notification.objects.create(
                                user=payment.user,
                                title='Payment Successful',
                                message=f'Your payment of ₦{payment.amount:,.2f} for policy {policy.policy_number} was successful',
                                notification_type='payment_confirmation',
                                data={'payment_id': str(payment.id)}
                            )
                            
                    except Payment.DoesNotExist:
                        logger.error(f"Payment not found for tx_ref: {tx_ref}")
            
            return Response({'status': 'ok'})
            
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class GetBanksView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        country = request.query_params.get('country', 'NG')
        banks = flutterwave_service.get_banks(country)
        
        if banks['success']:
            return Response({'banks': banks['banks']})
        else:
            return Response({'error': banks.get('error', 'Failed to fetch banks')}, 
                          status=status.HTTP_400_BAD_REQUEST)

class VerifyAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        account_number = request.data.get('account_number')
        bank_code = request.data.get('bank_code')
        
        if not account_number or not bank_code:
            return Response({'error': 'Account number and bank code required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        verification = flutterwave_service.verify_account_number(account_number, bank_code)
        
        if verification['success']:
            return Response({
                'account_name': verification['account_name'],
                'account_number': account_number
            })
        else:
            return Response({'error': verification.get('error', 'Account verification failed')}, 
                          status=status.HTTP_400_BAD_REQUEST)

class InitiateTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        Initiate bank transfer for payout (for claims settlement)
        """
        if not (request.user.is_staff or request.user.role == 'claims_adjuster'):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        claim_id = request.data.get('claim_id')
        account_bank = request.data.get('account_bank')
        account_number = request.data.get('account_number')
        amount = request.data.get('amount')
        
        claim = get_object_or_404(Claim, id=claim_id)
        
        # Verify account
        verification = flutterwave_service.verify_account_number(account_number, account_bank)
        if not verification['success']:
            return Response({'error': verification.get('error')}, status=status.HTTP_400_BAD_REQUEST)
        
        # Initiate transfer
        tx_ref = f"PAYOUT-{uuid.uuid4().hex[:12].upper()}"
        
        try:
            payload = {
                "account_bank": account_bank,
                "account_number": account_number,
                "amount": amount,
                "narration": f"Claim settlement for {claim.claim_number}",
                "currency": "NGN",
                "reference": tx_ref,
                "callback_url": f"{settings.SITE_URL}/api/payments/transfer-callback/",
                "debit_currency": "NGN"
            }
            
            headers = {
                'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{settings.FLUTTERWAVE_BASE_URL}/transfers",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return Response({
                        'success': True,
                        'transfer_id': data['data']['id'],
                        'reference': tx_ref
                    })
                else:
                    return Response({'error': data.get('message', 'Transfer failed')}, 
                                  status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'error': f"HTTP {response.status_code}"}, 
                              status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Transfer initiation error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        
        
        


