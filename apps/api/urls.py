from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

urlpatterns = [
    # Authentication (keep all existing)
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    # User Profile
    path('profile/', ProfileView.as_view(), name='profile'),
    
    # Vehicles
    path('vehicles/', VehicleListCreateView.as_view(), name='vehicle-list'),
    path('vehicles/<uuid:pk>/', VehicleDetailView.as_view(), name='vehicle-detail'),
    
    # Policies
    path('policies/', PolicyListView.as_view(), name='policy-list'),
    path('policies/<uuid:pk>/', PolicyDetailView.as_view(), name='policy-detail'),
    
    # Claims
    path('claims/', ClaimListView.as_view(), name='claim-list'),
    path('claims/<uuid:pk>/', ClaimDetailView.as_view(), name='claim-detail'),
    
    # Payments - Flutterwave Integration
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('payments/verify/', PaymentVerificationView.as_view(), name='verify-payment'),
    path('payments/webhook/flutterwave/', FlutterwaveWebhookView.as_view(), name='flutterwave-webhook'),
    path('payments/banks/', GetBanksView.as_view(), name='get-banks'),
    path('payments/verify-account/', VerifyAccountView.as_view(), name='verify-account'),
    path('payments/initiate-transfer/', InitiateTransferView.as_view(), name='initiate-transfer'),
    
    # Quotes
    path('quotes/', QuoteListView.as_view(), name='quote-list'),
    path('quotes/generate/', QuoteGenerateView.as_view(), name='generate-quote'),
    
    # Notifications
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<uuid:notification_id>/read/', MarkNotificationReadView.as_view(), name='mark-read'),
    
    # Support
    path('support/tickets/', SupportTicketListView.as_view(), name='ticket-list'),
    path('support/tickets/create/', SupportTicketCreateView.as_view(), name='ticket-create'),
    
    # Documents
    path('documents/upload/', UploadDocumentView.as_view(), name='upload-document'),
    
    # Promo Codes
    path('promo/validate/', ValidatePromoCodeView.as_view(), name='validate-promo'),
    
    # Dashboard
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
]