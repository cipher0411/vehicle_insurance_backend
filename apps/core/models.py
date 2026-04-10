import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from ckeditor.fields import RichTextField
from django.utils import timezone
from django.utils.text import slugify
import os


class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('agent', 'Insurance Agent'),
        ('underwriter', 'Underwriter'),
        ('claims_adjuster', 'Claims Adjuster'),
        ('admin', 'Administrator'),
        ('support', 'Support Staff'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = CountryField(default='NG')
    postal_code = models.CharField(max_length=20, blank=True)
    kyc_documents_submitted = models.BooleanField(default=False)
    gender = models.CharField(max_length=10, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    is_kyc_completed = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    device_token = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.email}"
    
    @property
    def is_customer(self):
        return self.role == 'customer'
    
    @property
    def is_staff_member(self):
        return self.role in ['agent', 'underwriter', 'claims_adjuster', 'admin', 'support']

class UserActivityLog(models.Model):
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view_policy', 'View Policy'),
        ('purchase_policy', 'Purchase Policy'),
        ('file_claim', 'File Claim'),
        ('update_profile', 'Update Profile'),
        ('change_password', 'Change Password'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_activity_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
        ]

class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = (
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('truck', 'Truck'),
        ('bus', 'Bus'),
        ('rickshaw', 'Rickshaw'),
    )
    
    FUEL_TYPE_CHOICES = (
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('cng', 'CNG'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
    )
    
    OWNERSHIP_CHOICES = (
        ('single', 'Single Owner'),
        ('joint', 'Joint Owner'),
        ('corporate', 'Corporate'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles')
    registration_number = models.CharField(max_length=20, unique=True)
    engine_number = models.CharField(max_length=50, unique=True)
    chassis_number = models.CharField(max_length=50, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.IntegerField(validators=[MinValueValidator(1900), MaxValueValidator(2025)])
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES)
    engine_capacity = models.IntegerField(help_text="Engine capacity in CC")
    color = models.CharField(max_length=50)
    ownership_type = models.CharField(max_length=20, choices=OWNERSHIP_CHOICES)
    registration_certificate = models.FileField(upload_to='vehicles/rc/', null=True, blank=True)
    insurance_history = models.FileField(upload_to='vehicles/history/', null=True, blank=True)
    current_mileage = models.IntegerField(default=0)
    is_insured = models.BooleanField(default=False)
    
    # Tracking fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_vehicles')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_vehicles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vehicles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['registration_number']),
            models.Index(fields=['vehicle_type']),
        ]
    
    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model}"
    
    @property
    def vehicle_age(self):
        return timezone.now().year - self.year
    
    

class InsurancePolicy(models.Model):
    POLICY_TYPE_CHOICES = (
        ('comprehensive', 'Comprehensive'),
        ('third_party', 'Third Party'),
        ('standalone', 'Standalone'),
        ('personal_accident', 'Personal Accident'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('claimed', 'Claimed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='policies')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='policies', null=True, blank=True)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    premium_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deductible = models.DecimalField(max_digits=12, decimal_places=2, default=5000)
    start_date = models.DateField()
    end_date = models.DateField()
    additional_benefits = models.JSONField(default=list)
    custom_coverage = models.JSONField(default=dict)
    policy_document = models.FileField(upload_to='policies/documents/', null=True, blank=True)
    terms_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'insurance_policies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['policy_number']),
            models.Index(fields=['status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.policy_number} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.policy_number:
            self.policy_number = f"POL-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        return self.status == 'active' and self.end_date >= timezone.now().date()
    
    @property
    def days_remaining(self):
        if self.is_active:
            return (self.end_date - timezone.now().date()).days
        return 0
    
    @property
    def coverage_percentage(self):
        return (self.coverage_amount / 10000000) * 100

class Claim(models.Model):
    CLAIM_TYPE_CHOICES = (
        ('accident', 'Accident'),
        ('theft', 'Theft'),
        ('natural_disaster', 'Natural Disaster'),
        ('fire', 'Fire'),
        ('vandalism', 'Vandalism'),
        ('third_party', 'Third Party'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('settled', 'Settled'),
        ('withdrawn', 'Withdrawn'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim_number = models.CharField(max_length=50, unique=True)
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name='claims')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='claims')
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    incident_date = models.DateTimeField()
    incident_location = models.TextField()
    incident_description = models.TextField()
    claimed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    documents = models.JSONField(default=list)
    photos = models.JSONField(default=list)
    surveyor_report = models.FileField(upload_to='claims/surveyor_reports/', null=True, blank=True)
    police_report = models.FileField(upload_to='claims/police_reports/', null=True, blank=True)
    surveyor_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_claims')
    approval_date = models.DateTimeField(null=True, blank=True)
    settlement_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'claims'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['claim_number']),
            models.Index(fields=['status']),
            models.Index(fields=['claim_type']),
        ]
    
    def __str__(self):
        return f"{self.claim_number} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_wallet', 'Mobile Wallet'),
        ('cash', 'Cash'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, unique=True)
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, unique=True)
    payment_details = models.JSONField(default=dict)
    receipt_url = models.URLField(max_length=500, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')
    verified_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='refunded_payments')
    failure_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.amount}"

class InsuranceQuote(models.Model):
    COVERAGE_TYPE_CHOICES = (
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('custom', 'Custom'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='quotes')
    coverage_type = models.CharField(max_length=20, choices=COVERAGE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    base_premium = models.DecimalField(max_digits=12, decimal_places=2)
    total_premium = models.DecimalField(max_digits=12, decimal_places=2)
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deductible = models.DecimalField(max_digits=12, decimal_places=2, default=5000)
    coverage_details = models.JSONField(default=dict)
    add_ons = models.JSONField(default=list)
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'insurance_quotes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    @property
    def is_valid(self):
        return self.status == 'approved' and self.valid_until >= timezone.now()
    
    

class InsuranceSettings(models.Model):
    """Dynamic insurance settings configurable by admin"""
    
    # Coverage Type Multipliers
    comprehensive_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.8,
        help_text="Multiplier for comprehensive coverage (e.g., 1.8 = 180% of base premium)"
    )
    third_party_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.0,
        help_text="Multiplier for third party coverage"
    )
    standalone_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.3,
        help_text="Multiplier for standalone coverage"
    )
    personal_accident_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.6,
        help_text="Multiplier for personal accident coverage"
    )
    
    # Base Premium Settings (in Naira)
    base_premium_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=50000.00,
        help_text="Base premium amount in Naira before multipliers"
    )
    base_coverage_reference = models.DecimalField(
        max_digits=12, decimal_places=2, default=1000000.00,
        help_text="Reference coverage amount (1,000,000 Naira) for premium calculation"
    )
    
    # Minimum Premium Settings
    min_premium_comprehensive = models.DecimalField(
        max_digits=12, decimal_places=2, default=75000.00
    )
    min_premium_third_party = models.DecimalField(
        max_digits=12, decimal_places=2, default=15000.00
    )
    min_premium_standalone = models.DecimalField(
        max_digits=12, decimal_places=2, default=35000.00
    )
    min_premium_personal_accident = models.DecimalField(
        max_digits=12, decimal_places=2, default=10000.00
    )
    
    # Vehicle Age Multipliers
    age_0_1_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=0.9)
    age_2_3_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    age_4_5_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.2)
    age_6_10_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    age_10_plus_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)
    
    # Vehicle Type Multipliers
    car_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    motorcycle_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=0.7)
    truck_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    bus_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.6)
    rickshaw_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=0.8)
    
    # Engine Capacity Multipliers
    engine_above_3000_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.3)
    engine_2000_3000_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.15)
    engine_1000_2000_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    engine_below_1000_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=0.9)
    
    # Deductible Settings
    deductible_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Deductible as percentage of total premium"
    )
    min_deductible = models.DecimalField(max_digits=12, decimal_places=2, default=5000.00)
    max_deductible = models.DecimalField(max_digits=12, decimal_places=2, default=100000.00)
    
    # Add-on Costs
    roadside_assistance_cost = models.DecimalField(max_digits=12, decimal_places=2, default=15000.00)
    zero_depreciation_cost = models.DecimalField(max_digits=12, decimal_places=2, default=25000.00)
    engine_protection_cost = models.DecimalField(max_digits=12, decimal_places=2, default=20000.00)
    personal_accident_cover_cost = models.DecimalField(max_digits=12, decimal_places=2, default=10000.00)
    
    # Promo Code Default Settings (can be overridden per promo code)
    default_promo_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Default discount percentage for new promo codes"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Flutterwave Settings
    flutterwave_public_key = models.CharField(max_length=200, blank=True, default='FLWPUBK_TEST-xxxxxxxxxxxxx')
    flutterwave_secret_key = models.CharField(max_length=200, blank=True, default='FLWSECK_TEST-xxxxxxxxxxxxx')
    flutterwave_encryption_key = models.CharField(max_length=200, blank=True, default='xxxxxxxxxxxxx')
    flutterwave_is_live = models.BooleanField(default=False, help_text="Switch to live mode")
    
    # Bank Transfer Settings
    bank_name = models.CharField(max_length=100, default='GTBank')
    bank_account_name = models.CharField(max_length=200, default='Vehicle Insurance Ltd')
    bank_account_number = models.CharField(max_length=20, default='0123456789')
    bank_sort_code = models.CharField(max_length=20, blank=True, default='058123456')
    
    class Meta:
        db_table = 'insurance_settings'
        verbose_name = 'Insurance Settings'
        verbose_name_plural = 'Insurance Settings'
    
    def __str__(self):
        return f"Insurance Settings (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"
    
    def save(self, *args, **kwargs):
        # Ensure only one settings record exists
        if not self.pk and InsuranceSettings.objects.exists():
            return InsuranceSettings.objects.first()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
    

class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = (
        ('claim_update', 'Claim Update'),
        ('policy_expiry', 'Policy Expiry'),
        ('payment_confirmation', 'Payment Confirmation'),
        ('quote_generated', 'Quote Generated'),
        ('system_alert', 'System Alert'),
        ('promotion', 'Promotion'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES)
    is_read = models.BooleanField(default=False)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

class Document(models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('driving_license', 'Driving License'),
        ('rc', 'Registration Certificate'),
        ('insurance', 'Insurance Document'),
        ('claim', 'Claim Document'),
        ('other', 'Other'),
    )
    
    VERIFICATION_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255, blank=True)  # Add this field
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    document_file = models.FileField(upload_to='documents/')
    document_number = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending')  # Add this
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_documents')
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)  # Add this
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Add this
    
    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.document_type}"
    
    def get_verification_status_display(self):
        return dict(self.VERIFICATION_STATUS_CHOICES).get(self.verification_status, 'Pending')

class SupportTicket(models.Model):
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'support_tickets'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class TicketReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to='tickets/attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ticket_replies'
        ordering = ['created_at']
        
        

class PromoCode(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    APPLICABLE_TO_CHOICES = (
        ('all', 'All Users'),
        ('new', 'New Customers Only'),
        ('existing', 'Existing Customers Only'),
    )
    
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    max_uses = models.IntegerField(default=1)
    used_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=200, blank=True, help_text="Description of this promo")
    min_purchase_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    applicable_to = models.CharField(max_length=50, choices=APPLICABLE_TO_CHOICES, default='all')
    max_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_promos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'promo_codes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.discount_value}{'%' if self.discount_type == 'percentage' else '₦'}"
    
    @property
    def is_valid(self):
        now = timezone.now()
        return (self.is_active and 
                self.valid_from <= now <= self.valid_to and 
                self.used_count < self.max_uses)
    
    def is_valid_for_user(self, user):
        """Check if promo is valid for a specific user"""
        if not self.is_valid:
            return False
        
        if self.applicable_to == 'new':
            # User has no previous purchases
            return not InsurancePolicy.objects.filter(user=user).exists()
        elif self.applicable_to == 'existing':
            # User has at least one purchase
            return InsurancePolicy.objects.filter(user=user).exists()
        
        # 'all' users
        return True
    
    def get_discount_display(self):
        if self.discount_type == 'percentage':
            return f"{self.discount_value}% OFF"
        return f"₦{self.discount_value:,.2f} OFF"
    
    
    
    
    

























# Add to your existing models.py

class BlogCategory(models.Model):
    """Blog post categories"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon name (e.g., 'fa-car')")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'blog_categories'
        verbose_name_plural = 'Blog Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_post_count(self):
        return self.posts.filter(status='published').count()


class BlogTag(models.Model):
    """Blog post tags"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'blog_tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class BlogPost(models.Model):
    """Blog posts"""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True)
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts')
    tags = models.ManyToManyField(BlogTag, blank=True, related_name='posts')
    featured_image = models.ImageField(upload_to='blog/featured/', null=True, blank=True)
    excerpt = models.TextField(max_length=500, help_text="Short summary for blog listing")
    content = RichTextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    reading_time = models.PositiveIntegerField(default=5, help_text="Estimated reading time in minutes")
    meta_title = models.CharField(max_length=200, blank=True, help_text="SEO meta title (optional)")
    meta_description = models.TextField(max_length=300, blank=True, help_text="SEO meta description (optional)")
    meta_keywords = models.CharField(max_length=300, blank=True, help_text="SEO keywords (comma separated)")
    
    # Author tracking
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='blog_posts')
    
    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'blog_posts'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['category']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        
        # Calculate reading time based on content length
        if self.content:
            word_count = len(self.content.split())
            self.reading_time = max(1, round(word_count / 200))
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('core:blog_detail', kwargs={'slug': self.slug})
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    @property
    def is_published(self):
        return self.status == 'published' and self.published_at and self.published_at <= timezone.now()
    
    @classmethod
    def get_popular_posts(cls, limit=5):
        return cls.objects.filter(status='published').order_by('-views_count')[:limit]
    
    @classmethod
    def get_related_posts(cls, post, limit=3):
        """Get related posts based on category and tags"""
        related = cls.objects.filter(
            status='published',
            category=post.category
        ).exclude(id=post.id)[:limit]
        
        if related.count() < limit:
            tag_related = cls.objects.filter(
                status='published',
                tags__in=post.tags.all()
            ).exclude(id=post.id).exclude(id__in=related)[:limit - related.count()]
            related = list(related) + list(tag_related)
        
        return related[:limit]


class BlogComment(models.Model):
    """Blog post comments"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_comments', null=True, blank=True)
    name = models.CharField(max_length=100, help_text="Name for guest comments")
    email = models.EmailField(help_text="Email for guest comments")
    website = models.URLField(blank=True)
    content = models.TextField()
    is_approved = models.BooleanField(default=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'blog_comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['is_approved']),
        ]
    
    def __str__(self):
        return f"Comment by {self.name} on {self.post.title}"
    
    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.name
    
    def get_replies(self):
        return self.replies.filter(is_approved=True)


class NewsletterSubscriber(models.Model):
    """Newsletter subscribers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token = models.CharField(max_length=100, blank=True)
    is_confirmed = models.BooleanField(default=False)
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    source = models.CharField(max_length=50, blank=True, help_text="Where they subscribed from")
    
    class Meta:
        db_table = 'newsletter_subscribers'
        ordering = ['-subscribed_at']
    
    def __str__(self):
        return self.email
    
    def unsubscribe(self):
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save()
        
        
        
        

# Add to your existing models.py

class PressCategory(models.Model):
    """Press release categories"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'press_categories'
        verbose_name_plural = 'Press Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_release_count(self):
        return self.releases.filter(status='published').count()


class PressRelease(models.Model):
    """Press releases and news"""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True)
    category = models.ForeignKey(PressCategory, on_delete=models.SET_NULL, null=True, related_name='releases')
    featured_image = models.ImageField(upload_to='press/featured/', null=True, blank=True)
    excerpt = models.TextField(max_length=500, help_text="Short summary for press listing")
    content = RichTextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    
    # Media attachments
    attachments = models.JSONField(default=list, blank=True, help_text="List of file URLs for attachments")
    gallery_images = models.JSONField(default=list, blank=True, help_text="List of image URLs for gallery")
    
    # Location and date
    location = models.CharField(max_length=200, blank=True, help_text="Where the news/event took place")
    press_date = models.DateField(null=True, blank=True, help_text="Date of the press release/event")
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=300, blank=True)
    
    # Contact for media
    media_contact_name = models.CharField(max_length=100, blank=True)
    media_contact_email = models.EmailField(blank=True)
    media_contact_phone = models.CharField(max_length=20, blank=True)
    
    # Author tracking
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='press_releases')
    
    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'press_releases'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['category']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('core:press_detail', kwargs={'slug': self.slug})
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    @property
    def is_published(self):
        return self.status == 'published' and self.published_at and self.published_at <= timezone.now()
    
    @classmethod
    def get_featured_releases(cls, limit=3):
        return cls.objects.filter(status='published', is_featured=True).order_by('-published_at')[:limit]
    
    @classmethod
    def get_recent_releases(cls, limit=5):
        return cls.objects.filter(status='published').order_by('-published_at')[:limit]


class MediaCoverage(models.Model):
    """External media coverage/mentions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    publication = models.CharField(max_length=200, help_text="Name of the media outlet")
    publication_logo = models.ImageField(upload_to='press/publications/', null=True, blank=True)
    url = models.URLField(max_length=500, help_text="Link to the article")
    excerpt = models.TextField(max_length=500)
    coverage_date = models.DateField()
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'media_coverage'
        ordering = ['-coverage_date']
        verbose_name_plural = 'Media Coverage'
    
    def __str__(self):
        return f"{self.publication}: {self.title}"


class MediaKit(models.Model):
    """Media kit resources for journalists"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    file = models.FileField(upload_to='press/media_kit/')
    file_type = models.CharField(max_length=50, choices=(
        ('pdf', 'PDF Document'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    ))
    file_size = models.CharField(max_length=50, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'media_kit'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def increment_downloads(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])
    
    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            size = self.file.size
            if size < 1024:
                self.file_size = f"{size} B"
            elif size < 1024 * 1024:
                self.file_size = f"{size / 1024:.1f} KB"
            else:
                self.file_size = f"{size / (1024 * 1024):.1f} MB"
        super().save(*args, **kwargs)
        
        
        
        
        
# Add to your existing models.py
from django.db.models import Q


class JobCategory(models.Model):
    """Job/Department categories"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon name (e.g., 'fa-code')")
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_categories'
        verbose_name_plural = 'Job Categories'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_job_count(self):
        return self.jobs.filter(status='published', is_active=True).count()


class JobLocation(models.Model):
    """Job locations"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = CountryField(default='NG')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_locations'
        ordering = ['city', 'name']
    
    def __str__(self):
        return f"{self.name}, {self.city}"


class JobType(models.Model):
    """Job types (Full-time, Part-time, Contract, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'job_types'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class JobPosting(models.Model):
    """Job postings/career opportunities"""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    )
    
    EXPERIENCE_CHOICES = (
        ('entry', 'Entry Level (0-2 years)'),
        ('mid', 'Mid Level (3-5 years)'),
        ('senior', 'Senior Level (6-10 years)'),
        ('lead', 'Lead/Manager (10+ years)'),
        ('executive', 'Executive'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True)
    category = models.ForeignKey(JobCategory, on_delete=models.SET_NULL, null=True, related_name='jobs')
    location = models.ForeignKey(JobLocation, on_delete=models.SET_NULL, null=True, related_name='jobs')
    job_type = models.ForeignKey(JobType, on_delete=models.SET_NULL, null=True, related_name='jobs')
    
    short_description = models.TextField(max_length=300, help_text="Brief summary for listing")
    description = RichTextField(help_text="Full job description")
    requirements = RichTextField(help_text="Job requirements and qualifications")
    responsibilities = RichTextField(help_text="Key responsibilities")
    benefits = RichTextField(blank=True, help_text="Benefits and perks")
    
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, default='mid')
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default='NGN')
    salary_is_visible = models.BooleanField(default=True)
    
    application_email = models.EmailField(help_text="Email where applications should be sent")
    application_url = models.URLField(blank=True, help_text="External application URL (optional)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_remote = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    applications_count = models.PositiveIntegerField(default=0)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=300, blank=True)
    
    # Dates
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True, help_text="Application deadline")
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_jobs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_postings'
        ordering = ['-is_featured', '-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['category']),
            models.Index(fields=['location']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('core:job_detail', kwargs={'slug': self.slug})
    
    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def increment_applications(self):
        self.applications_count += 1
        self.save(update_fields=['applications_count'])
    
    @property
    def is_open(self):
        if not self.is_active or self.status != 'published':
            return False
        if self.expires_at and self.expires_at < timezone.now().date():
            return False
        return True
    
    @property
    def salary_display(self):
        if not self.salary_is_visible or not self.salary_min:
            return "Competitive"
        if self.salary_min and self.salary_max:
            return f"₦{self.salary_min:,.0f} - ₦{self.salary_max:,.0f}"
        elif self.salary_min:
            return f"₦{self.salary_min:,.0f}+"
        return "Competitive"
    
    @classmethod
    def get_featured_jobs(cls, limit=3):
        return cls.objects.filter(
            status='published', 
            is_active=True, 
            is_featured=True
        ).select_related('category', 'location', 'job_type')[:limit]
    
    @classmethod
    def get_open_jobs(cls):
        return cls.objects.filter(
            status='published', 
            is_active=True
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now().date())
        )


class JobApplication(models.Model):
    """Job applications submitted by candidates"""
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('interviewed', 'Interviewed'),
        ('offered', 'Offered'),
        ('hired', 'Hired'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=200, blank=True)
    
    resume = models.FileField(upload_to='applications/resumes/')
    cover_letter = models.TextField(blank=True)
    portfolio_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    
    current_company = models.CharField(max_length=200, blank=True)
    current_role = models.CharField(max_length=200, blank=True)
    years_experience = models.IntegerField(null=True, blank=True)
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    available_from = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, help_text="Internal notes about the candidate")
    rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_applications')
    
    class Meta:
        db_table = 'job_applications'
        ordering = ['-created_at']
        unique_together = ['job', 'email']
    
    def __str__(self):
        return f"{self.full_name} - {self.job.title}"
    
    def get_status_color(self):
        colors = {
            'pending': 'warning',
            'reviewed': 'info',
            'shortlisted': 'primary',
            'interviewed': 'success',
            'offered': 'success',
            'hired': 'success',
            'rejected': 'danger',
            'withdrawn': 'secondary',
        }
        return colors.get(self.status, 'secondary')
    
    
    
    
    
# Add to your existing models.py
# In models.py - Update DocumentCategory to use standard AutoField
class DocumentCategory(models.Model):
    """Document categories for organization"""
    # Use standard auto-increment ID instead of UUID
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, default='fa-file')
    color = models.CharField(max_length=20, blank=True, default='#4169E1')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'document_categories'
        verbose_name_plural = 'Document Categories'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_document_count(self):
        return self.public_documents.filter(is_active=True).count()


class PublicDocument(models.Model):
    """Public digital documents accessible to users"""
    DOCUMENT_TYPE_CHOICES = (
        ('certificate', 'Insurance Certificate'),
        ('policy', 'Policy Document'),
        ('receipt', 'Payment Receipt'),
        ('claim_doc', 'Claim Document'),
        ('invoice', 'Invoice'),
        ('renewal', 'Renewal Notice'),
        ('endorsement', 'Policy Endorsement'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True)
    document_number = models.CharField(max_length=100, blank=True, help_text="Reference number")
    
    # Relationships - using unique related_names to avoid conflicts
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='public_documents', null=True, blank=True)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.SET_NULL, null=True, blank=True, related_name='public_documents')
    claim = models.ForeignKey('Claim', on_delete=models.SET_NULL, null=True, blank=True, related_name='public_documents')
    payment = models.ForeignKey('Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='public_documents')
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='public_documents')
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    document_file = models.FileField(upload_to='public_documents/')
    file_size = models.CharField(max_length=50, blank=True)
    file_extension = models.CharField(max_length=20, blank=True)
    
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=300, blank=True, help_text="Comma-separated tags")
    
    # Dates
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True, help_text="Visible to user in their portal")
    is_verified = models.BooleanField(default=False)
    download_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    
    # Verification
    verification_hash = models.CharField(max_length=64, blank=True, help_text="SHA256 hash for document verification")
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_public_documents')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_public_documents')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_public_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'public_documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['document_type']),
            models.Index(fields=['status']),
            models.Index(fields=['policy']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_document_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.title}-{uuid.uuid4().hex[:6]}")
        
        if self.document_file and not self.file_size:
            size = self.document_file.size
            if size < 1024:
                self.file_size = f"{size} B"
            elif size < 1024 * 1024:
                self.file_size = f"{size / 1024:.1f} KB"
            else:
                self.file_size = f"{size / (1024 * 1024):.1f} MB"
        
        if self.document_file and not self.file_extension:
            ext = os.path.splitext(self.document_file.name)[1].lower()
            self.file_extension = ext.replace('.', '').upper()
        
        # Generate verification hash if not exists
        if not self.verification_hash and self.document_file:
            import hashlib
            self.document_file.seek(0)
            file_hash = hashlib.sha256(self.document_file.read()).hexdigest()
            self.verification_hash = file_hash
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('core:public_document_detail', kwargs={'slug': self.slug})
    
    def increment_downloads(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])
    
    def increment_views(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    @property
    def is_valid(self):
        if self.valid_until:
            return self.valid_until >= timezone.now().date()
        return True
    
    @property
    def file_icon(self):
        if self.file_extension in ['PDF']:
            return 'fa-file-pdf'
        elif self.file_extension in ['DOC', 'DOCX']:
            return 'fa-file-word'
        elif self.file_extension in ['XLS', 'XLSX']:
            return 'fa-file-excel'
        elif self.file_extension in ['JPG', 'JPEG', 'PNG', 'GIF']:
            return 'fa-file-image'
        else:
            return 'fa-file'
    
    @property
    def file_icon_color(self):
        if self.file_extension in ['PDF']:
            return '#dc2626'
        elif self.file_extension in ['DOC', 'DOCX']:
            return '#2563eb'
        elif self.file_extension in ['XLS', 'XLSX']:
            return '#10b981'
        elif self.file_extension in ['JPG', 'JPEG', 'PNG', 'GIF']:
            return '#8b5cf6'
        else:
            return '#64748b'
    
    @classmethod
    def get_user_documents(cls, user, document_type=None):
        """Get all public documents for a user"""
        docs = cls.objects.filter(user=user, is_active=True, is_public=True, status='published')
        if document_type:
            docs = docs.filter(document_type=document_type)
        return docs
    
    @classmethod
    def get_document_stats(cls, user):
        """Get document statistics for a user"""
        docs = cls.objects.filter(user=user, is_active=True, is_public=True, status='published')
        return {
            'total': docs.count(),
            'certificates': docs.filter(document_type='certificate').count(),
            'policies': docs.filter(document_type='policy').count(),
            'receipts': docs.filter(document_type='receipt').count(),
            'claims': docs.filter(document_type='claim_doc').count(),
        }


class DocumentAccessLog(models.Model):
    """Track document access"""
    document = models.ForeignKey(PublicDocument, on_delete=models.CASCADE, related_name='access_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=(
        ('view', 'View'),
        ('download', 'Download'),
        ('share', 'Share'),
        ('print', 'Print'),
    ))
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'document_access_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.document.title} - {self.action} at {self.created_at}"
    
    
        
        

# Add to your existing models.py

class ContactInquiry(models.Model):
    """Contact form inquiries"""
    INQUIRY_TYPE_CHOICES = (
        ('general', 'General Inquiry'),
        ('quote', 'Quote Request'),
        ('claim', 'Claim Support'),
        ('policy', 'Policy Question'),
        ('complaint', 'Complaint'),
        ('partnership', 'Partnership'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('spam', 'Spam'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry_number = models.CharField(max_length=50, unique=True, blank=True)
    
    # Contact Information
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    policy_number = models.CharField(max_length=100, blank=True)
    
    # Inquiry Details
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPE_CHOICES, default='general')
    subject = models.CharField(max_length=300)
    message = models.TextField()
    
    # Status and Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_inquiries')
    
    # Response tracking
    response = models.TextField(blank=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='responded_inquiries')
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contact_inquiries')
    
    # Bot detection
    is_suspicious = models.BooleanField(default=False)
    spam_score = models.IntegerField(default=0)
    
    # Notes
    internal_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contact_inquiries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['email']),
            models.Index(fields=['inquiry_type']),
        ]
    
    def __str__(self):
        return f"{self.inquiry_number} - {self.full_name}"
    
    def save(self, *args, **kwargs):
        if not self.inquiry_number:
            self.inquiry_number = f"INQ-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    def get_priority_color(self):
        colors = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'urgent': 'danger',
        }
        return colors.get(self.priority, 'secondary')
    
    def get_status_color(self):
        colors = {
            'pending': 'warning',
            'in_progress': 'info',
            'resolved': 'success',
            'closed': 'secondary',
            'spam': 'danger',
        }
        return colors.get(self.status, 'secondary')


class OfficeLocation(models.Model):
    """Office locations"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = CountryField(default='NG')
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    working_hours = models.CharField(max_length=200, help_text="e.g., Mon-Fri: 8AM - 6PM")
    is_headquarters = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'office_locations'
        ordering = ['order', 'city', 'name']
    
    def __str__(self):
        return f"{self.name}, {self.city}"
    
    def get_map_embed_url(self):
        if self.latitude and self.longitude:
            return f"https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3964!2d{self.longitude}!3d{self.latitude}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1"
        return None
    
    
    
    
    
    
    


