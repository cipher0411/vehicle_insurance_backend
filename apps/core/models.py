from decimal import Decimal
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from ckeditor.fields import RichTextField
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
import random
import string
from django.utils import timezone
from django.utils.text import slugify
import os



from django.contrib.auth.base_user import BaseUserManager

# ============================================
# CUSTOM USER MANAGER
# ============================================

class CustomUserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    """
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


# ============================================
# USER MODEL - MUST BE DEFINED FIRST
# ============================================

class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('agent', 'Insurance Agent'),
        ('underwriter', 'Underwriter'),
        ('claims_adjuster', 'Claims Adjuster'),
        ('admin', 'Administrator'),
        ('support', 'Support Staff'),
    )
    
    referred_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='referrals',
        limit_choices_to={'role__in': ['agent', 'admin']}
    )
    referral_code = models.CharField(max_length=20, blank=True, help_text="Referral code used during registration")
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True, null=True, blank=True, region=None)
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
    
    # Remove username requirement and use email as username
    username = models.CharField(
        max_length=150, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Optional. Auto-generated if not provided."
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name() or self.email}"
    
    def save(self, *args, **kwargs):
        if not self.username:
            base_username = self.email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exclude(pk=self.pk).exists():
                username = f"{base_username}{counter}"
                counter += 1
            self.username = username
        super().save(*args, **kwargs)
    
    @property
    def is_customer(self):
        return self.role == 'customer'
    
    @property
    def is_staff_member(self):
        return self.role in ['agent', 'underwriter', 'claims_adjuster', 'admin', 'support']


# ============================================
# AGENT MODELS - NOW USER IS DEFINED
# ============================================


class AgentProfile(models.Model):
    """Extended profile for agents"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='agent_profile')
    agent_code = models.CharField(max_length=20, unique=True)
    agent_type = models.CharField(max_length=20, choices=(
        ('individual', 'Individual Agent'),
        ('corporate', 'Corporate Agent'),
        ('broker', 'Broker'),
    ), default='individual')
    
    # Business Information
    business_name = models.CharField(max_length=200, blank=True)
    business_address = models.TextField(blank=True)
    business_phone = models.CharField(max_length=20, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Banking Information
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_name = models.CharField(max_length=200, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_sort_code = models.CharField(max_length=20, blank=True)
    
    # Commission Settings
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    bonus_eligible = models.BooleanField(default=True)
    
    # Performance Metrics
    total_sales = models.IntegerField(default=0)
    total_commission_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_commission_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_month_sales = models.IntegerField(default=0)
    current_month_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verification_documents = models.JSONField(default=list)
    
    # Manager/Supervisor
    supervisor = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='supervised_agents')
    
    # Dates
    joined_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'agent_profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent_code']),
            models.Index(fields=['user']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.agent_code}"
    
    def save(self, *args, **kwargs):
        if not self.agent_code:
            self.agent_code = f"AGT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def update_performance_metrics(self):
        """Update agent performance metrics"""
        from django.db.models import Sum
        from django.utils import timezone
        from decimal import Decimal
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Total sales (policies sold by this agent)
        # Use the direct agent field on InsurancePolicy
        self.total_sales = InsurancePolicy.objects.filter(
            agent=self.user
        ).count()
        
        # Also count policies from referred customers (if agent didn't directly sell)
        referred_customer_ids = AgentReferral.objects.filter(
            agent=self.user
        ).values_list('customer_id', flat=True)
        
        referred_policies = InsurancePolicy.objects.filter(
            user_id__in=referred_customer_ids
        ).count()
        
        # Total sales = direct sales + referred customer policies
        self.total_sales = self.total_sales + referred_policies
        
        # Total commission earned
        self.total_commission_earned = Commission.objects.filter(
            agent=self.user,
            status__in=['approved', 'paid']
        ).aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
        
        # Total commission paid
        self.total_commission_paid = Commission.objects.filter(
            agent=self.user,
            status='paid'
        ).aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
        
        # Current month metrics - direct sales
        current_month_direct = InsurancePolicy.objects.filter(
            agent=self.user,
            created_at__date__gte=month_start
        ).count()
        
        # Current month metrics - referred sales
        current_month_referred = InsurancePolicy.objects.filter(
            user_id__in=referred_customer_ids,
            created_at__date__gte=month_start
        ).count()
        
        self.current_month_sales = current_month_direct + current_month_referred
        
        self.current_month_commission = Commission.objects.filter(
            agent=self.user,
            status__in=['approved', 'paid'],
            earned_date__gte=month_start
        ).aggregate(total=Sum('total_commission'))['total'] or Decimal('0')
        
        self.save(update_fields=[
            'total_sales', 'total_commission_earned', 'total_commission_paid',
            'current_month_sales', 'current_month_commission'
        ])
    
    def get_downline_customers(self):
        """Get all customers registered under this agent"""
        return User.objects.filter(
            referred_by=self.user,
            role='customer'
        )
    
    def get_downline_policies(self):
        """Get all policies from downline customers"""
        return InsurancePolicy.objects.filter(
            user__in=self.get_downline_customers()
        )
    
    def get_commission_summary(self):
        """Get commission summary for agent"""
        commissions = Commission.objects.filter(agent=self.user)
        
        return {
            'total_earned': self.total_commission_earned,
            'total_paid': self.total_commission_paid,
            'pending': commissions.filter(status='pending').aggregate(total=Sum('total_commission'))['total'] or 0,
            'approved': commissions.filter(status='approved').aggregate(total=Sum('total_commission'))['total'] or 0,
            'current_month': self.current_month_commission,
        }


class AgentReferral(models.Model):
    """Track agent referrals and customer relationships"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_referrals')
    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agent_reference')
    referral_code = models.CharField(max_length=50, blank=True)
    referral_source = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'agent_referrals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent']),
            models.Index(fields=['customer']),
        ]
    
    def __str__(self):
        return f"{self.agent.email} -> {self.customer.email}"


class AgentCommissionRate(models.Model):
    """Commission rates specific to agents"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commission_rates')
    policy_type = models.CharField(max_length=20, choices=[
        ('comprehensive', 'Comprehensive'),
        ('third_party', 'Third Party'),
        ('standalone', 'Standalone'),
        ('personal_accident', 'Personal Accident'),
    ])
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_commission_rates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'agent_commission_rates'
        unique_together = ['agent', 'policy_type', 'effective_from']
        ordering = ['-effective_from']
    
    def __str__(self):
        return f"{self.agent.email} - {self.get_policy_type_display()} - {self.commission_rate}%"


class AgentPayout(models.Model):
    """Payout records for agents"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout_number = models.CharField(max_length=50, unique=True)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    payment_reference = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_name = models.CharField(max_length=200, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    commissions = models.ManyToManyField('Commission', related_name='payouts')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payouts')
    processed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'agent_payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['payout_number']),
        ]
    
    def __str__(self):
        return f"{self.payout_number} - {self.agent.email} - ₦{self.amount:,.2f}"
    
    def save(self, *args, **kwargs):
        if not self.payout_number:
            self.payout_number = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class AgentTarget(models.Model):
    """Monthly/Quarterly targets for agents"""
    PERIOD_CHOICES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='targets')
    period = models.CharField(max_length=15, choices=PERIOD_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    target_premium = models.DecimalField(max_digits=12, decimal_places=2)
    target_policies = models.IntegerField(default=0)
    achieved_premium = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    achieved_policies = models.IntegerField(default=0)
    bonus_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_achieved = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_targets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'agent_targets'
        unique_together = ['agent', 'period', 'period_start']
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.agent.email} - {self.period} Target ({self.period_start})"
    
    def calculate_achievement(self):
        """Calculate achievement progress"""
        policies = InsurancePolicy.objects.filter(
            agent=self.agent,
            created_at__date__gte=self.period_start,
            created_at__date__lte=self.period_end,
            status='active'
        )
        self.achieved_policies = policies.count()
        self.achieved_premium = policies.aggregate(total=Sum('premium_amount'))['total'] or Decimal('0')
        self.is_achieved = (self.achieved_premium >= self.target_premium)
        self.save()
        return self.is_achieved



# ============================================
# COMMISSION MODEL (for agents)
# ============================================

class Commission(models.Model):
    """Agent commission tracking"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('calculated', 'Calculated'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )
    
    COMMISSION_TYPE_CHOICES = (
        ('new_policy', 'New Policy'),
        ('renewal', 'Policy Renewal'),
        ('bonus', 'Performance Bonus'),
        ('override', 'Override Commission'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commission_number = models.CharField(max_length=50, unique=True)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commissions_earned')
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='commissions', null=True, blank=True)
    
    # Commission details
    commission_type = models.CharField(max_length=20, choices=COMMISSION_TYPE_CHOICES, default='new_policy')
    premium_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Bonus
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_reason = models.CharField(max_length=200, blank=True)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    earned_date = models.DateField()
    paid_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Approvals
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_commissions')
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Payment reference
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'commissions'
        ordering = ['-earned_date']
        indexes = [
            models.Index(fields=['agent', '-earned_date']),
            models.Index(fields=['policy']),
            models.Index(fields=['status']),
            models.Index(fields=['commission_number']),
            models.Index(fields=['commission_type']),
        ]
    
    def __str__(self):
        return f"{self.commission_number} - {self.agent.email}"
    
    def save(self, *args, **kwargs):
        if not self.commission_number:
            self.commission_number = f"COM-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate commission
        self.commission_amount = self.premium_amount * (self.commission_rate / Decimal('100'))
        self.total_commission = self.commission_amount + self.bonus_amount
        
        super().save(*args, **kwargs)
        
        # Update agent profile metrics - check if agent has profile
        if hasattr(self.agent, 'agent_profile'):
            try:
                self.agent.agent_profile.update_performance_metrics()
            except Exception as e:
                # Log error but don't prevent save
                print(f"Error updating agent metrics: {e}")




class CommissionStructure(models.Model):
    """Dynamic commission rate structure for different policy types and agent types"""
    POLICY_TYPE_CHOICES = [
        ('comprehensive', 'Comprehensive'),
        ('third_party', 'Third Party'),
        ('standalone', 'Standalone'),
        ('personal_accident', 'Personal Accident'),
    ]
    
    AGENT_TYPE_CHOICES = [
        ('individual', 'Individual Agent'),
        ('corporate', 'Corporate Agent'),
        ('broker', 'Broker'),
        ('all', 'All Agent Types'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, null=True, blank=True, help_text="Structure name for reference")
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES)
    agent_type = models.CharField(max_length=20, choices=AGENT_TYPE_CHOICES, default='all')
    
    # Commission rates
    base_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Base commission percentage")
    
    # Tiered commission based on premium amount
    enable_tiered_commission = models.BooleanField(default=False)
    tier_1_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Premium threshold for tier 1")
    tier_1_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Commission rate for tier 1")
    tier_2_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Premium threshold for tier 2")
    tier_2_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Commission rate for tier 2")
    tier_3_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Premium threshold for tier 3")
    tier_3_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Commission rate for tier 3")
    
    # Bonus settings
    enable_bonus = models.BooleanField(default=False)
    bonus_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Minimum premium to qualify for bonus")
    bonus_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Additional bonus percentage")
    bonus_cap = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Maximum bonus amount (0 for unlimited)")
    
    # Validity
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True, help_text="Leave blank for indefinite")
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Higher priority structures are applied first")
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_commission_structures')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_commission_structures')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'commission_structures'
        ordering = ['-priority', '-effective_from']
        indexes = [
            models.Index(fields=['policy_type', 'agent_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.get_policy_type_display()} ({self.base_commission_rate}%)"
    
    def is_valid_for_date(self, date):
        """Check if structure is valid for a given date"""
        if not self.is_active:
            return False
        if date < self.effective_from:
            return False
        if self.effective_to and date > self.effective_to:
            return False
        return True
    
    def calculate_commission_rate(self, premium_amount):
        """Calculate applicable commission rate based on premium amount"""
        if self.enable_tiered_commission:
            if premium_amount >= self.tier_3_threshold and self.tier_3_rate > 0:
                return self.tier_3_rate
            elif premium_amount >= self.tier_2_threshold and self.tier_2_rate > 0:
                return self.tier_2_rate
            elif premium_amount >= self.tier_1_threshold and self.tier_1_rate > 0:
                return self.tier_1_rate
        return self.base_commission_rate
    
    def calculate_bonus(self, premium_amount):
        """Calculate bonus amount for a given premium"""
        if not self.enable_bonus:
            return Decimal('0')
        if premium_amount < self.bonus_threshold:
            return Decimal('0')
        bonus = premium_amount * (self.bonus_rate / Decimal('100'))
        if self.bonus_cap > 0:
            bonus = min(bonus, self.bonus_cap)
        return bonus
    
    @classmethod
    def get_applicable_structure(cls, policy_type, agent_type, date=None):
        """Get the most applicable commission structure for given parameters"""
        if date is None:
            date = timezone.now().date()
        
        # Try exact match first
        structure = cls.objects.filter(
            policy_type=policy_type,
            agent_type=agent_type,
            is_active=True,
            effective_from__lte=date
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=date)
        ).order_by('-priority', '-effective_from').first()
        
        if structure:
            return structure
        
        # Try 'all' agent types
        structure = cls.objects.filter(
            policy_type=policy_type,
            agent_type='all',
            is_active=True,
            effective_from__lte=date
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=date)
        ).order_by('-priority', '-effective_from').first()
        
        return structure


class AgentCommissionOverride(models.Model):
    """Override commission rates for specific agents"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commission_overrides')
    policy_type = models.CharField(max_length=20, choices=CommissionStructure.POLICY_TYPE_CHOICES)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField(blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_overrides')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'agent_commission_overrides'
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['agent', 'policy_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.agent.email} - {self.get_policy_type_display()} - {self.commission_rate}%"
    
    def is_valid_for_date(self, date):
        if not self.is_active:
            return False
        if date < self.effective_from:
            return False
        if self.effective_to and date > self.effective_to:
            return False
        return True

# ============================================
# REST OF YOUR MODELS (UserActivityLog, Vehicle, etc.)
# ============================================

class UserActivityLog(models.Model):
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view_policy', 'View Policy'),
        ('purchase_policy', 'Purchase Policy'),
        ('file_claim', 'File Claim'),
        ('update_profile', 'Update Profile'),
        ('change_password', 'Change Password'),
        ('register', 'Register'),
        ('upload_kyc', 'Upload KYC'),
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
    
    def update_insurance_status(self):
        """Update is_insured based on active policies"""
        active_policy_exists = self.policies.filter(status='active').exists()
        if self.is_insured != active_policy_exists:
            self.is_insured = active_policy_exists
            self.save(update_fields=['is_insured'])
        return self.is_insured
    
    @property
    def active_policy(self):
        """Get the active policy for this vehicle"""
        return self.policies.filter(status='active').first()
    
    @property
    def insurance_status_display(self):
        """Get display-friendly insurance status"""
        if self.is_insured:
            active_policy = self.active_policy
            if active_policy:
                return f"Insured (Policy: {active_policy.policy_number})"
            return "Insured"
        return "Uninsured"
    
    

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
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='sold_policies', help_text="Agent who sold this policy")
    
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
    
    # ========== FINANCIAL CALCULATION METHODS ==========
    
    def get_total_paid(self):
        """Get total amount paid for this policy (completed payments only)"""
        from django.db.models import Sum
        from decimal import Decimal
        
        total = self.payments.filter(
            status='completed',
            amount__gt=0
        ).exclude(
            payment_method='credit_note'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return total
    
    def get_total_credits_applied(self):
        """Get total credit notes applied as payments (negative amounts)"""
        from django.db.models import Sum
        from decimal import Decimal
        
        credits = self.payments.filter(
            status='completed',
            amount__lt=0,
            payment_method='credit_note'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return abs(credits)
    
    def get_total_debit_notes(self):
        """Get total debit notes issued/paid for this policy"""
        from django.db.models import Sum
        from decimal import Decimal
        
        debits = self.debit_credit_notes.filter(
            note_type='debit',
            status__in=['paid', 'issued']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        return debits
    
    def get_total_credit_notes(self):
        """Get total credit notes issued/paid for this policy"""
        from django.db.models import Sum
        from decimal import Decimal
        
        credits = self.debit_credit_notes.filter(
            note_type='credit',
            status__in=['paid', 'issued']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        return credits
    
    def get_outstanding_balance(self):
        """Calculate outstanding balance for this policy"""
        base_premium = self.premium_amount
        total_paid = self.get_total_paid()
        total_credits_applied = self.get_total_credits_applied()
        total_debit_notes = self.get_total_debit_notes()
        total_credit_notes = self.get_total_credit_notes()
        
        outstanding = (
            base_premium + 
            total_debit_notes - 
            total_credit_notes - 
            total_paid + 
            total_credits_applied
        )
        
        return outstanding
    
    def get_payment_status(self):
        """Get payment status of the policy"""
        outstanding = self.get_outstanding_balance()
        base_premium = self.premium_amount
        
        if outstanding <= 0:
            return 'paid'
        elif outstanding >= base_premium:
            return 'unpaid'
        else:
            return 'partial'
    
    def get_pending_payments_total(self):
        """Get total of pending payments"""
        from django.db.models import Sum
        from decimal import Decimal
        
        pending = self.payments.filter(
            status__in=['pending', 'pending_verification']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return pending
    
    def create_renewal(self):
        """Create a renewal record for this policy"""
        from datetime import timedelta
        
        # Check if renewal already exists
        existing_renewal = PolicyRenewal.objects.filter(
            original_policy=self,
            status__in=['pending', 'quoted', 'accepted']
        ).first()
        
        if existing_renewal:
            return existing_renewal
        
        # Calculate renewal dates
        new_start_date = self.end_date + timedelta(days=1)
        new_end_date = new_start_date + timedelta(days=365)
        
        # Calculate renewal premium with NCB
        ncb = NoClaimBonus.objects.filter(user=self.user, vehicle=self.vehicle).first()
        ncb_discount = Decimal('0')
        if ncb:
            ncb_discount = self.premium_amount * (ncb.current_ncb_percentage / Decimal('100'))
        
        # Apply vehicle age factor
        renewal_premium = self.premium_amount
        if self.vehicle:
            vehicle_age = timezone.now().year - self.vehicle.year
            if vehicle_age > 5:
                renewal_premium *= Decimal('1.1')
        
        renewal_premium -= ncb_discount
        
        renewal = PolicyRenewal.objects.create(
            original_policy=self,
            user=self.user,
            original_premium=self.premium_amount,
            renewal_premium=renewal_premium,
            ncb_discount=ncb_discount,
            renewal_date=self.end_date - timedelta(days=30),
            expiry_date=self.end_date,
            new_start_date=new_start_date,
            new_end_date=new_end_date,
            status='pending'
        )
        
        return renewal
    
    def can_be_reinsured(self):
        """Check if policy can be reinsured - now allows cancelled policies too"""
        # Check if already reinsured
        if hasattr(self, 'reinsurance_placement'):
            return False
        
        # Allow active and cancelled policies to be reinsured
        if self.status in ['active', 'cancelled']:
            return True
        
        return False
    
    def get_reinsurance_status(self):
        """Get reinsurance status"""
        if hasattr(self, 'reinsurance_placement'):
            placement = self.reinsurance_placement
            return {
                'is_reinsured': True,
                'ceded_amount': placement.ceded_amount,
                'ceded_premium': placement.ceded_premium,
                'reinsurer': placement.treaty.reinsurer_name,
                'placement_date': placement.placement_date
            }
        return {'is_reinsured': False}

class Claim(models.Model):
    CLAIM_TYPE_CHOICES = (
        ('accident', 'Accident'),
        ('theft', 'Theft'),
        ('natural_disaster', 'Natural Disaster'),
        ('fire', 'Fire'),
        ('vandalism', 'Vandalism'),
        ('third_party', 'Third Party'),
        ('own_damage', 'Own Damage'),
        ('windscreen', 'Windscreen'),
        ('flood', 'Flood'),
        ('other', 'Other'),
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
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='claims')
    vehicle = models.ForeignKey('Vehicle', on_delete=models.CASCADE, related_name='claims', null=True, blank=True,
                                help_text="Vehicle involved in the claim")
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='claims')
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
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_claims')
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
            models.Index(fields=['vehicle']),
            models.Index(fields=['policy']),
        ]
    
    def __str__(self):
        return f"{self.claim_number} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        
        # Auto-populate vehicle from policy if not set
        if not self.vehicle and self.policy and self.policy.vehicle:
            self.vehicle = self.policy.vehicle
        
        super().save(*args, **kwargs)
    
    def get_vehicle_info(self):
        """Get vehicle information for display"""
        if self.vehicle:
            return {
                'make': self.vehicle.make,
                'model': self.vehicle.model,
                'year': self.vehicle.year,
                'registration': self.vehicle.registration_number,
                'color': self.vehicle.color,
                'engine_number': self.vehicle.engine_number,
                'chassis_number': self.vehicle.chassis_number,
            }
        elif self.policy and self.policy.vehicle:
            return {
                'make': self.policy.vehicle.make,
                'model': self.policy.vehicle.model,
                'year': self.policy.vehicle.year,
                'registration': self.policy.vehicle.registration_number,
                'color': self.policy.vehicle.color,
                'engine_number': self.policy.vehicle.engine_number,
                'chassis_number': self.policy.vehicle.chassis_number,
            }
        return None
    
    @property
    def vehicle_display(self):
        """Display-friendly vehicle string"""
        info = self.get_vehicle_info()
        if info:
            return f"{info['make']} {info['model']} ({info['year']}) - {info['registration']}"
        return "No vehicle information"

import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_wallet', 'Mobile Wallet'),
        ('cash', 'Cash'),
        ('credit_note', 'Credit Note'), 
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('pending_verification', 'Pending Verification'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, unique=True)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, unique=True)
    payment_details = models.JSONField(default=dict)
    receipt_url = models.URLField(max_length=500, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')
    verified_at = models.DateTimeField(null=True, blank=True)
    refunded_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='refunded_payments')
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
    
    @classmethod
    def generate_unique_reference(cls, prefix='PAY'):
        """Generate a unique payment reference using UUID"""
        unique_id = uuid.uuid4().hex[:12].upper()
        timestamp = str(int(timezone.now().timestamp()))[-6:]
        reference = f"{prefix}-{timestamp}-{unique_id}"
        
        # Ensure uniqueness
        while cls.objects.filter(payment_reference=reference).exists():
            unique_id = uuid.uuid4().hex[:12].upper()
            reference = f"{prefix}-{timestamp}-{unique_id}"
        
        return reference
    
    @classmethod
    def generate_unique_transaction_id(cls, prefix='TXN'):
        """Generate a unique transaction ID using UUID"""
        unique_id = uuid.uuid4().hex[:12].upper()
        timestamp = str(int(timezone.now().timestamp()))[-6:]
        transaction_id = f"{prefix}-{timestamp}-{unique_id}"
        
        # Ensure uniqueness
        while cls.objects.filter(transaction_id=transaction_id).exists():
            unique_id = uuid.uuid4().hex[:12].upper()
            transaction_id = f"{prefix}-{timestamp}-{unique_id}"
        
        return transaction_id
    
    def save(self, *args, **kwargs):
        """Auto-generate unique references if not provided"""
        if not self.transaction_id:
            self.transaction_id = self.generate_unique_transaction_id('TXN')
        if not self.payment_reference:
            self.payment_reference = self.generate_unique_reference('PAY')
        super().save(*args, **kwargs)

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
    
    # Bank Transfer Settings - Updated defaults
    bank_name = models.CharField(max_length=100, default='Access Bank')
    bank_account_name = models.CharField(max_length=200, default='VehicleInsure Ltd')
    bank_account_number = models.CharField(max_length=20, default='0592787269')
    bank_sort_code = models.CharField(max_length=20, blank=True, default='044152567')
    bank_swift_code = models.CharField(max_length=20, blank=True, default='ABNGNGLA')
    
    # Email Settings
    email_host = models.CharField(max_length=100, blank=True, default='smtp.gmail.com')
    email_port = models.IntegerField(default=587)
    email_host_user = models.CharField(max_length=100, blank=True)
    email_host_password = models.CharField(max_length=100, blank=True)
    email_use_tls = models.BooleanField(default=True)
    default_from_email = models.EmailField(max_length=100, blank=True, default='noreply@vehicleinsure.ng')
    admin_notification_email = models.EmailField(max_length=100, blank=True, help_text="Email for admin notifications")
    
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
    



class PolicyCertificate(models.Model):
    """Policy certificate generated when policy is activated"""
    CERTIFICATE_STATUS_CHOICES = (
        ('generated', 'Generated'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.OneToOneField(InsurancePolicy, on_delete=models.CASCADE, related_name='certificate')
    certificate_number = models.CharField(max_length=50, unique=True)
    certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)
    issue_date = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_certificates')
    status = models.CharField(max_length=20, choices=CERTIFICATE_STATUS_CHOICES, default='pending')
    qr_code = models.ImageField(upload_to='certificates/qr/', null=True, blank=True)
    verification_hash = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'policy_certificates'
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['certificate_number']),
            models.Index(fields=['policy']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Certificate for Policy {self.policy.policy_number}"
    
    def save(self, *args, **kwargs):
        if not self.certificate_number:
            self.certificate_number = f"CERT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)



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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # ADD THIS LINE
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
    
    




# apps/core/models.py - Add these new models at the end of the file

# ============================================
# DEBIT/CREDIT NOTE MODELS
# ============================================

# apps/core/models.py - Updated DebitCreditNote model

class DebitCreditNote(models.Model):
    """Debit and Credit Notes for policy adjustments"""
    NOTE_TYPE_CHOICES = (
        ('debit', 'Debit Note'),
        ('credit', 'Credit Note'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid/Applied'),
        ('cancelled', 'Cancelled'),
    )
    
    REASON_CHOICES = (
        ('premium_adjustment', 'Premium Adjustment'),
        ('endorsement', 'Policy Endorsement'),
        ('cancellation', 'Policy Cancellation'),
        ('refund', 'Premium Refund'),
        ('additional_coverage', 'Additional Coverage'),
        ('tax_adjustment', 'Tax Adjustment'),
        ('fee_waiver', 'Fee Waiver'),
        ('other', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note_number = models.CharField(max_length=50, unique=True)
    note_type = models.CharField(max_length=10, choices=NOTE_TYPE_CHOICES)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='debit_credit_notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debit_credit_notes')
    
    # Amounts
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Details
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField()
    
    # Related transactions
    related_payment = models.ForeignKey('Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='debit_credit_notes')
    related_endorsement = models.ForeignKey('PolicyEndorsement', on_delete=models.SET_NULL, null=True, blank=True, related_name='debit_credit_notes')
    
    # Dates
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    
    # Document
    note_document = models.FileField(upload_to='debit_credit_notes/', null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_notes')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'debit_credit_notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['policy', '-created_at']),
            models.Index(fields=['note_number']),
            models.Index(fields=['note_type']),
            models.Index(fields=['status']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.note_number} - {self.get_note_type_display()} - {self.policy.policy_number}"
    
    def save(self, *args, **kwargs):
        if not self.note_number:
            prefix = 'DBN' if self.note_type == 'debit' else 'CRN'
            self.note_number = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate total if not set
        if not self.total_amount:
            self.total_amount = self.base_amount + self.tax_amount
        
        # Ensure user matches policy user if not set
        if not self.user_id and self.policy_id:
            self.user = self.policy.user
            
        super().save(*args, **kwargs)
    
    @property
    def is_paid(self):
        return self.status == 'paid'
    
    @property
    def outstanding_amount(self):
        """Calculate outstanding amount"""
        if self.status == 'paid':
            return Decimal('0')
        from django.db.models import Sum
        payments = self.note_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return self.total_amount - payments
    
    def apply_to_policy(self):
        """Apply debit/credit note to policy - updates total amount owed"""
        if self.status != 'issued':
            return False
        
        policy = self.policy
        
        if self.note_type == 'debit':
            # Debit note increases amount owed
            # Create a payment record for the additional amount
            from .models import Payment
            import uuid
            import time
            
            transaction_id = f"TXN-DN-{uuid.uuid4().hex[:8].upper()}-{int(time.time())}"
            payment_reference = f"PAY-DN-{uuid.uuid4().hex[:8].upper()}"
            
            payment = Payment.objects.create(
                policy=policy,
                user=self.user,
                amount=self.total_amount,
                payment_method='bank_transfer',  # Default method
                transaction_id=transaction_id,
                payment_reference=payment_reference,
                status='pending',
                payment_details={
                    'type': 'debit_note',
                    'debit_note_id': str(self.id),
                    'note_number': self.note_number
                }
            )
            
            self.related_payment = payment
            self.status = 'paid'
            self.paid_date = timezone.now()
            self.save()
            
            # Send notification to user
            Notification.objects.create(
                user=self.user,
                title='Debit Note Issued',
                message=f'A debit note of ₦{self.total_amount:,.2f} has been issued for policy #{policy.policy_number}. Reason: {self.get_reason_display()}',
                notification_type='payment_confirmation',
                data={'debit_note_id': str(self.id), 'policy_id': str(policy.id)}
            )
            
        elif self.note_type == 'credit':
            # Credit note reduces amount owed or creates refund
            # Create a credit transaction
            from .models import Payment
            import uuid
            import time
            
            transaction_id = f"TXN-CN-{uuid.uuid4().hex[:8].upper()}-{int(time.time())}"
            payment_reference = f"REF-CN-{uuid.uuid4().hex[:8].upper()}"
            
            # Create a negative payment (credit)
            payment = Payment.objects.create(
                policy=policy,
                user=self.user,
                amount=-self.total_amount,  # Negative amount for credit
                payment_method='credit_note',
                transaction_id=transaction_id,
                payment_reference=payment_reference,
                status='completed',
                paid_at=timezone.now(),
                payment_details={
                    'type': 'credit_note',
                    'credit_note_id': str(self.id),
                    'note_number': self.note_number
                }
            )
            
            self.related_payment = payment
            self.status = 'paid'
            self.paid_date = timezone.now()
            self.save()
            
            # Send notification to user
            Notification.objects.create(
                user=self.user,
                title='Credit Note Issued',
                message=f'A credit note of ₦{self.total_amount:,.2f} has been applied to policy #{policy.policy_number}. Reason: {self.get_reason_display()}',
                notification_type='payment_confirmation',
                data={'credit_note_id': str(self.id), 'policy_id': str(policy.id)}
            )
        
        return True
    
    def get_user_balance(self):
        """Get user's outstanding balance including this note"""
        from django.db.models import Sum
        
        # Total payments made
        total_paid = Payment.objects.filter(
            user=self.user,
            policy=self.policy,
            status='completed'
        ).exclude(
            amount__lt=0  # Exclude credit notes
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Total credits applied
        total_credits = Payment.objects.filter(
            user=self.user,
            policy=self.policy,
            status='completed',
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Total debit notes issued
        total_debits = DebitCreditNote.objects.filter(
            user=self.user,
            policy=self.policy,
            note_type='debit',
            status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Total credit notes issued
        total_credit_notes = DebitCreditNote.objects.filter(
            user=self.user,
            policy=self.policy,
            note_type='credit',
            status='paid'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        policy_premium = self.policy.premium_amount
        
        # Calculate balance
        balance = policy_premium + total_debits - total_credit_notes - total_paid + abs(total_credits)
        
        return balance


class NotePayment(models.Model):
    """Payments made against debit notes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    debit_note = models.ForeignKey(DebitCreditNote, on_delete=models.CASCADE, related_name='note_payments')
    payment = models.ForeignKey('Payment', on_delete=models.CASCADE, related_name='note_payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'note_payments'
        unique_together = ['debit_note', 'payment']


# ============================================
# POLICY ENDORSEMENT MODEL
# ============================================
class PolicyEndorsement(models.Model):
    """Policy endorsements/changes during policy period"""
    ENDORSEMENT_TYPE_CHOICES = (
        ('vehicle_change', 'Vehicle Change'),
        ('coverage_change', 'Coverage Change'),
        ('address_change', 'Address Change'),
        ('name_change', 'Name Change'),
        ('add_driver', 'Add Driver'),
        ('remove_driver', 'Remove Driver'),
        ('sum_insured_change', 'Sum Insured Change'),
        ('premium_change', 'Premium Adjustment'),
        ('cancellation', 'Cancellation'),
        ('reinstatement', 'Reinstatement'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('applied', 'Applied to Policy'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endorsement_number = models.CharField(max_length=50, unique=True)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='endorsements')
    endorsement_type = models.CharField(max_length=20, choices=ENDORSEMENT_TYPE_CHOICES)
    
    # Changes - Store both old and new values
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    
    # Financial impact
    premium_adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    effective_date = models.DateField(help_text="When the changes should take effect")
    requested_date = models.DateTimeField(default=timezone.now)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Approvals
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_endorsements')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_endorsements')
    approved_date = models.DateTimeField(null=True, blank=True)
    
    # Reasons
    reason = models.TextField(help_text="Reason for the endorsement request")
    rejection_reason = models.TextField(blank=True)
    
    # Documents
    supporting_documents = models.JSONField(default=list)
    endorsement_document = models.FileField(upload_to='endorsements/', null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'policy_endorsements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['policy', '-created_at']),
            models.Index(fields=['endorsement_number']),
            models.Index(fields=['status']),
            models.Index(fields=['endorsement_type']),
        ]
    
    def __str__(self):
        return f"{self.endorsement_number} - {self.policy.policy_number}"
    
    def save(self, *args, **kwargs):
        if not self.endorsement_number:
            self.endorsement_number = f"END-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate total adjustment
        self.total_adjustment = self.premium_adjustment + self.tax_adjustment
        
        super().save(*args, **kwargs)
    
    def apply_endorsement(self, approved_by=None):
        """Apply the endorsement to the policy and create necessary debit/credit notes"""
        if self.status != 'approved':
            return False
        
        policy = self.policy
        changes_made = []
        
        # Apply changes based on endorsement type
        if self.endorsement_type == 'vehicle_change':
            if 'vehicle_id' in self.new_values:
                old_vehicle = policy.vehicle
                policy.vehicle_id = self.new_values['vehicle_id']
                changes_made.append(f"Vehicle changed from {old_vehicle} to {policy.vehicle}")
        
        elif self.endorsement_type == 'coverage_change':
            if 'coverage_amount' in self.new_values:
                old_coverage = policy.coverage_amount
                policy.coverage_amount = Decimal(str(self.new_values['coverage_amount']))
                changes_made.append(f"Coverage changed from ₦{old_coverage:,.2f} to ₦{policy.coverage_amount:,.2f}")
            
            if 'policy_type' in self.new_values:
                old_type = policy.get_policy_type_display()
                policy.policy_type = self.new_values['policy_type']
                changes_made.append(f"Policy type changed from {old_type} to {policy.get_policy_type_display()}")
        
        elif self.endorsement_type == 'sum_insured_change':
            if 'coverage_amount' in self.new_values:
                old_coverage = policy.coverage_amount
                policy.coverage_amount = Decimal(str(self.new_values['coverage_amount']))
                changes_made.append(f"Sum insured changed from ₦{old_coverage:,.2f} to ₦{policy.coverage_amount:,.2f}")
        
        elif self.endorsement_type == 'premium_change':
            if 'premium_amount' in self.new_values:
                old_premium = policy.premium_amount
                policy.premium_amount = Decimal(str(self.new_values['premium_amount']))
                changes_made.append(f"Premium changed from ₦{old_premium:,.2f} to ₦{policy.premium_amount:,.2f}")
        
        elif self.endorsement_type == 'cancellation':
            policy.status = 'cancelled'
            changes_made.append("Policy cancelled")
        
        elif self.endorsement_type == 'reinstatement':
            policy.status = 'active'
            changes_made.append("Policy reinstated")
        
        # Create debit/credit note if there's a financial adjustment
        if self.total_adjustment != 0:
            note_type = 'debit' if self.total_adjustment > 0 else 'credit'
            
            note = DebitCreditNote.objects.create(
                policy=policy,
                user=policy.user,
                note_type=note_type,
                base_amount=abs(self.premium_adjustment),
                tax_amount=abs(self.tax_adjustment),
                total_amount=abs(self.total_adjustment),
                reason='endorsement',
                description=f"Premium adjustment due to endorsement #{self.endorsement_number}: {self.get_endorsement_type_display()}",
                related_endorsement=self,
                created_by=approved_by,
                status='issued'  # Auto-issue the note
            )
            
            # Apply the note immediately
            note.apply_to_policy()
            changes_made.append(f"{note_type.title()} note #{note.note_number} created for ₦{abs(self.total_adjustment):,.2f}")
        
        # Save policy changes
        policy.save()
        
        # Update endorsement status
        self.status = 'applied'
        self.approved_by = approved_by
        self.approved_date = timezone.now()
        self.save()
        
        # Send notification to user
        from apps.core.models import Notification
        Notification.objects.create(
            user=policy.user,
            title=f'Endorsement Applied - {self.get_endorsement_type_display()}',
            message=f'Your endorsement request #{self.endorsement_number} has been applied to policy #{policy.policy_number}. ' + 
                    ' '.join(changes_made),
            notification_type='system_alert',
            data={
                'endorsement_id': str(self.id),
                'policy_id': str(policy.id),
                'changes': changes_made
            }
        )
        
        return True
    
    def get_changes_summary(self):
        """Get a human-readable summary of changes"""
        summary = []
        
        for key, new_value in self.new_values.items():
            old_value = self.old_values.get(key, 'N/A')
            
            if key == 'vehicle_id':
                summary.append(f"Vehicle: Changed to new vehicle")
            elif key == 'coverage_amount':
                summary.append(f"Coverage: ₦{old_value:,.2f} → ₦{new_value:,.2f}")
            elif key == 'policy_type':
                summary.append(f"Policy Type: {old_value} → {new_value}")
            elif key == 'premium_amount':
                summary.append(f"Premium: ₦{old_value:,.2f} → ₦{new_value:,.2f}")
            else:
                summary.append(f"{key}: {old_value} → {new_value}")
        
        return summary


# ============================================
# NO CLAIM BONUS MODEL
# ============================================

class NoClaimBonus(models.Model):
    """Track No Claim Bonus for users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='no_claim_bonus')
    vehicle = models.ForeignKey('Vehicle', on_delete=models.CASCADE, related_name='no_claim_bonus', null=True, blank=True)
    
    # NCB Details
    current_ncb_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    claim_free_years = models.IntegerField(default=0)
    last_claim_date = models.DateField(null=True, blank=True)
    
    # Protection
    is_protected = models.BooleanField(default=False)
    protection_expiry = models.DateField(null=True, blank=True)
    
    # History
    ncb_history = models.JSONField(default=list)  # Store yearly NCB history
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'no_claim_bonus'
        unique_together = ['user', 'vehicle']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['vehicle']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - NCB: {self.current_ncb_percentage}%"
    
    def calculate_ncb(self):
        """Calculate NCB based on claim-free years"""
        ncb_slabs = {
            1: 20,   # 1 year no claim = 20% discount
            2: 25,   # 2 years = 25%
            3: 35,   # 3 years = 35%
            4: 45,   # 4 years = 45%
            5: 50,   # 5+ years = 50%
        }
        
        percentage = 0
        for years, slab_percentage in sorted(ncb_slabs.items(), reverse=True):
            if self.claim_free_years >= years:
                percentage = slab_percentage
                break
        
        return percentage
    
    def update_after_claim(self):
        """Update NCB after a claim is filed"""
        if self.is_protected and self.protection_expiry and self.protection_expiry >= timezone.now().date():
            # Protected NCB - no reduction
            return
        
        # Reduce NCB based on claim
        if self.claim_free_years >= 5:
            self.claim_free_years = 2  # Drop to 2 years
        elif self.claim_free_years >= 3:
            self.claim_free_years = 1  # Drop to 1 year
        else:
            self.claim_free_years = 0  # Reset to 0
        
        self.last_claim_date = timezone.now().date()
        self.current_ncb_percentage = self.calculate_ncb()
        self.save()
    
    def increment_year(self):
        """Increment claim-free year on renewal"""
        self.claim_free_years += 1
        self.current_ncb_percentage = self.calculate_ncb()
        
        # Add to history
        self.ncb_history.append({
            'year': timezone.now().year,
            'claim_free_years': self.claim_free_years,
            'percentage': float(self.current_ncb_percentage),
            'date': timezone.now().isoformat()
        })
        
        self.save()


# ============================================
# POLICY RENEWAL MODEL
# ============================================

class PolicyRenewal(models.Model):
    """Manage policy renewals"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('quoted', 'Quoted'),
        ('accepted', 'Accepted'),
        ('renewed', 'Renewed'),
        ('lapsed', 'Lapsed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    renewal_number = models.CharField(max_length=50, unique=True)
    original_policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='renewals')
    renewed_policy = models.OneToOneField('InsurancePolicy', on_delete=models.SET_NULL, null=True, blank=True, related_name='renewed_from')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='renewals')
    
    # Renewal details
    renewal_premium = models.DecimalField(max_digits=12, decimal_places=2)
    original_premium = models.DecimalField(max_digits=12, decimal_places=2)
    ncb_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_discounts = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    renewal_date = models.DateField()
    expiry_date = models.DateField()
    new_start_date = models.DateField()
    new_end_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Communications
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_date = models.DateTimeField(null=True, blank=True)
    quote_sent = models.BooleanField(default=False)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'policy_renewals'
        ordering = ['-renewal_date']
        indexes = [
            models.Index(fields=['original_policy', '-renewal_date']),
            models.Index(fields=['user', '-renewal_date']),
            models.Index(fields=['status']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.renewal_number} - {self.original_policy.policy_number}"
    
    def save(self, *args, **kwargs):
        if not self.renewal_number:
            self.renewal_number = f"RNW-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def calculate_renewal_premium(self):
        """Calculate renewal premium with NCB and other factors"""
        base_premium = self.original_premium
        
        # Apply NCB
        ncb = NoClaimBonus.objects.filter(user=self.user, vehicle=self.original_policy.vehicle).first()
        if ncb:
            self.ncb_discount = base_premium * (ncb.current_ncb_percentage / 100)
        
        # Apply vehicle age factor
        if self.original_policy.vehicle:
            vehicle_age = timezone.now().year - self.original_policy.vehicle.year
            if vehicle_age > 5:
                age_factor = 1.1  # 10% increase for older vehicles
                base_premium *= age_factor
        
        self.renewal_premium = base_premium - self.ncb_discount - self.other_discounts
        return self.renewal_premium


# ============================================
# INSTALLMENT PLAN MODEL
# ============================================

class InstallmentPlan(models.Model):
    """Premium installment payment plans with recurring support"""
    FREQUENCY_CHOICES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_MODE_CHOICES = (
        ('manual', 'Manual Payment'),
        ('auto', 'Automatic Debit'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_number = models.CharField(max_length=50, unique=True)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='installment_plans')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='installment_plans')
    
    # Plan details
    total_premium = models.DecimalField(max_digits=12, decimal_places=2)
    down_payment = models.DecimalField(max_digits=12, decimal_places=2)
    financed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Installment details
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES, default='monthly')
    number_of_installments = models.IntegerField()
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Recurring Payment Settings
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, default='manual')
    auto_debit_enabled = models.BooleanField(default=False)
    flutterwave_plan_id = models.CharField(max_length=100, blank=True, help_text="Flutterwave payment plan ID")
    flutterwave_subscription_id = models.CharField(max_length=100, blank=True, help_text="Flutterwave subscription ID")
    card_token = models.CharField(max_length=200, blank=True, help_text="Tokenized card for recurring payments")
    last_auto_debit_date = models.DateTimeField(null=True, blank=True)
    next_auto_debit_date = models.DateTimeField(null=True, blank=True)
    auto_debit_attempts = models.IntegerField(default=0)
    max_auto_debit_attempts = models.IntegerField(default=3)
    
    # Dates
    start_date = models.DateField()
    next_due_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'installment_plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['policy']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['next_due_date']),
            models.Index(fields=['auto_debit_enabled']),
            models.Index(fields=['next_auto_debit_date']),
        ]
    
    def __str__(self):
        return f"{self.plan_number} - {self.policy.policy_number}"
    
    def save(self, *args, **kwargs):
        if not self.plan_number:
            self.plan_number = f"INST-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate financed amount
        if not self.financed_amount:
            self.financed_amount = self.total_premium - self.down_payment
        
        # Calculate interest
        if self.interest_rate > 0:
            self.total_interest = self.financed_amount * (self.interest_rate / Decimal('100'))
        
        # Calculate total payable
        self.total_payable = self.financed_amount + self.total_interest
        
        # Calculate installment amount
        if self.number_of_installments > 0:
            self.installment_amount = self.total_payable / Decimal(str(self.number_of_installments))
        
        super().save(*args, **kwargs)
    
    def get_paid_amount(self):
        """Get total paid amount for this plan"""
        from django.db.models import Sum
        result = self.installments.filter(status='paid').aggregate(
            total=Sum('amount_paid')
        )
        return result['total'] or Decimal('0')
    
    def get_remaining_amount(self):
        """Get remaining amount to be paid"""
        return self.total_payable - self.get_paid_amount()
    
    def get_next_installment(self):
        """Get next pending installment"""
        return self.installments.filter(status='pending').order_by('due_date').first()
    
    def should_auto_debit_today(self):
        """Check if auto-debit should run today"""
        if not self.auto_debit_enabled or self.status != 'active':
            return False
        
        today = timezone.now().date()
        pending_installment = self.installments.filter(
            status='pending',
            due_date__lte=today
        ).order_by('due_date').first()
        
        return pending_installment is not None
    
    def create_flutterwave_payment_plan(self):
        """Create a payment plan on Flutterwave for recurring debits"""
        import requests
        from django.conf import settings
        
        settings_obj = InsuranceSettings.get_settings()
        
        url = "https://api.flutterwave.com/v3/payment-plans"
        
        # Calculate interval based on frequency
        if self.frequency == 'monthly':
            interval = 'monthly'
            duration = self.number_of_installments
        elif self.frequency == 'quarterly':
            interval = 'quarterly'
            duration = self.number_of_installments * 3
        else:
            interval = 'biannually'
            duration = self.number_of_installments * 6
        
        payload = {
            "amount": float(self.installment_amount),
            "name": f"Installment Plan - {self.plan_number}",
            "interval": interval,
            "duration": duration,
            "currency": "NGN"
        }
        
        headers = {
            'Authorization': f'Bearer {settings_obj.flutterwave_secret_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            if data.get('status') == 'success':
                self.flutterwave_plan_id = str(data['data']['id'])
                self.save()
                return {'success': True, 'plan_id': self.flutterwave_plan_id}
            else:
                return {'success': False, 'message': data.get('message', 'Failed to create plan')}
                
        except Exception as e:
            return {'success': False, 'message': str(e)}



class Installment(models.Model):
    """Individual installment payments"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),  # For auto-debit in progress
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('overdue', 'Overdue'),
        ('waived', 'Waived'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    installment_plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='installments')
    installment_number = models.IntegerField()
    
    # Amounts
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    due_date = models.DateField()
    paid_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Payment reference
    payment = models.ForeignKey('Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='installments')
    
    # Auto-debit tracking
    auto_debit_attempted = models.BooleanField(default=False)
    auto_debit_attempts = models.IntegerField(default=0)
    last_auto_debit_attempt = models.DateTimeField(null=True, blank=True)
    auto_debit_error = models.TextField(blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'installments'
        ordering = ['installment_number']
        unique_together = ['installment_plan', 'installment_number']
        indexes = [
            models.Index(fields=['installment_plan', 'status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Installment {self.installment_number} - {self.installment_plan.plan_number}"
    
    @property
    def is_overdue(self):
        return self.status == 'pending' and self.due_date < timezone.now().date()
    
    @property
    def remaining_amount(self):
        return self.total_amount - self.amount_paid



# ============================================
# POLICY CANCELLATION MODEL
# ============================================

class PolicyCancellation(models.Model):
    """Policy cancellation requests and processing"""
    REASON_CHOICES = (
        ('vehicle_sold', 'Vehicle Sold'),
        ('better_premium', 'Found Better Premium'),
        ('no_longer_needed', 'No Longer Needed'),
        ('dissatisfied', 'Dissatisfied with Service'),
        ('financial', 'Financial Reasons'),
        ('moving', 'Moving/Relocation'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processed', 'Processed'),
        ('refunded', 'Refunded'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cancellation_number = models.CharField(max_length=50, unique=True)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='cancellations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cancellations')
    
    # Cancellation details
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    other_reason = models.TextField(blank=True)
    cancellation_date = models.DateField()
    effective_date = models.DateField()
    
    # Refund calculation
    total_premium = models.DecimalField(max_digits=12, decimal_places=2)
    earned_premium = models.DecimalField(max_digits=12, decimal_places=2)
    unearned_premium = models.DecimalField(max_digits=12, decimal_places=2)
    cancellation_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Short-rate table used
    short_rate_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Approvals
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_cancellations')
    approved_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Refund details
    refund_method = models.CharField(max_length=50, blank=True)
    refund_reference = models.CharField(max_length=100, blank=True)
    refund_date = models.DateTimeField(null=True, blank=True)
    
    # Documents
    cancellation_document = models.FileField(upload_to='cancellations/', null=True, blank=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'policy_cancellations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['policy']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['cancellation_number']),
        ]
    
    def __str__(self):
        return f"{self.cancellation_number} - {self.policy.policy_number}"
    
    def save(self, *args, **kwargs):
        if not self.cancellation_number:
            self.cancellation_number = f"CAN-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate refund if not set
        if not self.refund_amount and self.total_premium > 0:
            self.calculate_refund()
        
        super().save(*args, **kwargs)
    
    def calculate_refund(self):
        """Calculate refund using short-rate cancellation table"""
        from decimal import Decimal
        
        # Calculate days in force
        if self.policy.start_date and self.effective_date:
            days_in_force = (self.effective_date - self.policy.start_date).days
        else:
            days_in_force = 0
            
        if self.policy.start_date and self.policy.end_date:
            total_days = (self.policy.end_date - self.policy.start_date).days
        else:
            total_days = 365
        
        if days_in_force <= 0:
            self.earned_premium = Decimal('0')
        else:
            # Short-rate cancellation table
            if days_in_force < 30:
                earned_percentage = Decimal('10')
            elif days_in_force < 60:
                earned_percentage = Decimal('20')
            elif days_in_force < 90:
                earned_percentage = Decimal('30')
            elif days_in_force < 120:
                earned_percentage = Decimal('40')
            elif days_in_force < 150:
                earned_percentage = Decimal('50')
            elif days_in_force < 180:
                earned_percentage = Decimal('60')
            elif days_in_force < 210:
                earned_percentage = Decimal('70')
            elif days_in_force < 240:
                earned_percentage = Decimal('80')
            elif days_in_force < 270:
                earned_percentage = Decimal('90')
            else:
                earned_percentage = Decimal('100')
            
            self.short_rate_percentage = earned_percentage
            self.earned_premium = self.total_premium * (earned_percentage / Decimal('100'))
        
        self.unearned_premium = self.total_premium - self.earned_premium
        self.refund_amount = self.unearned_premium - self.cancellation_fee
        
        if self.refund_amount < 0:
            self.refund_amount = Decimal('0')
        
        return self.refund_amount
    
    def process_cancellation(self):
        """Process the cancellation"""
        if self.status != 'approved':
            return False
        
        # Update policy status
        self.policy.status = 'cancelled'
        self.policy.save()
        
        # Create credit note for refund
        if self.refund_amount > 0:
            credit_note = DebitCreditNote.objects.create(
                policy=self.policy,
                user=self.user,
                note_type='credit',
                base_amount=self.refund_amount,
                total_amount=self.refund_amount,
                reason='cancellation',
                description=f"Premium refund for policy cancellation #{self.cancellation_number}",
                created_by=self.approved_by,
                status='issued'
            )
            
            # Apply the credit note immediately
            credit_note.apply_to_policy()
        
        self.status = 'processed'
        self.save()
        
        return True


# ============================================
# CO-INSURANCE / REINSURANCE MODEL
# ============================================

class ReinsuranceTreaty(models.Model):
    """Reinsurance treaty agreements"""
    TREATY_TYPE_CHOICES = (
        ('quota_share', 'Quota Share'),
        ('surplus', 'Surplus'),
        ('excess_of_loss', 'Excess of Loss'),
        ('stop_loss', 'Stop Loss'),
        ('facultative', 'Facultative'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    treaty_number = models.CharField(max_length=50, unique=True)
    treaty_name = models.CharField(max_length=200)
    reinsurer_name = models.CharField(max_length=200)
    treaty_type = models.CharField(max_length=20, choices=TREATY_TYPE_CHOICES)
    
    # Treaty terms
    cession_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage of risk ceded")
    retention_limit = models.DecimalField(max_digits=12, decimal_places=2, help_text="Maximum retention amount")
    treaty_limit = models.DecimalField(max_digits=12, decimal_places=2, help_text="Maximum treaty capacity")
    
    # Commission
    reinsurance_commission = models.DecimalField(max_digits=5, decimal_places=2, help_text="Commission from reinsurer")
    profit_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Dates
    effective_date = models.DateField()
    expiry_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_treaties')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reinsurance_treaties'
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['treaty_number']),
            models.Index(fields=['status']),
            models.Index(fields=['reinsurer_name']),
        ]
    
    def __str__(self):
        return f"{self.treaty_number} - {self.reinsurer_name}"


class PolicyReinsurance(models.Model):
    """Reinsurance placement for individual policies"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey('InsurancePolicy', on_delete=models.CASCADE, related_name='reinsurance_placements')
    treaty = models.ForeignKey(ReinsuranceTreaty, on_delete=models.CASCADE, related_name='policy_placements')
    
    # Amounts
    sum_insured = models.DecimalField(max_digits=12, decimal_places=2)
    retention_amount = models.DecimalField(max_digits=12, decimal_places=2)
    ceded_amount = models.DecimalField(max_digits=12, decimal_places=2)
    ceded_premium = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Commission
    commission_earned = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dates
    placement_date = models.DateField()
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'policy_reinsurance'
        ordering = ['-placement_date']
        indexes = [
            models.Index(fields=['policy']),
            models.Index(fields=['treaty']),
        ]
    
    def __str__(self):
        return f"Reinsurance for {self.policy.policy_number}"
    
    def calculate_cession(self):
        """Calculate reinsurance cession"""
        if self.treaty.treaty_type == 'quota_share':
            self.ceded_amount = self.sum_insured * (self.treaty.cession_percentage / 100)
            self.retention_amount = self.sum_insured - self.ceded_amount
        
        elif self.treaty.treaty_type == 'surplus':
            if self.sum_insured > self.treaty.retention_limit:
                self.retention_amount = self.treaty.retention_limit
                self.ceded_amount = min(
                    self.sum_insured - self.retention_amount,
                    self.treaty.treaty_limit
                )
            else:
                self.retention_amount = self.sum_insured
                self.ceded_amount = 0
        
        # Calculate ceded premium
        if self.sum_insured > 0:
            cession_ratio = self.ceded_amount / self.sum_insured
            self.ceded_premium = self.policy.premium_amount * cession_ratio
        
        # Calculate commission
        self.commission_earned = self.ceded_premium * (self.treaty.reinsurance_commission / 100)
        
        self.save()
























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
    
    
    
    
    
    
    


# Add to your existing models.py

class SecurityEvent(models.Model):
    """Security event logging for SOC"""
    SEVERITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )
    
    EVENT_TYPE_CHOICES = (
        ('LOGIN_SUCCESS', 'Login Success'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('LOGOUT', 'Logout'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('PROFILE_UPDATE', 'Profile Update'),
        ('ATTACK_DETECTED', 'Attack Detected'),
        ('PATH_TRAVERSAL', 'Path Traversal'),
        ('SQLI_ATTEMPT', 'SQLi Attempt'),
        ('XSS_ATTEMPT', 'XSS Attempt'),
        ('RATE_LIMIT', 'Rate Limit Exceeded'),
        ('BLOCKED_IP', 'Blocked IP'),
        ('MALICIOUS_UA', 'Malicious User Agent'),
        ('FILE_UPLOAD', 'File Upload'),
        ('MALWARE_DETECTED', 'Malware Detected'),
        ('ADMIN_ACTION', 'Admin Action'),
        ('API_KEY_GENERATED', 'API Key Generated'),
        ('PERMISSION_DENIED', 'Permission Denied'),
        ('CONFIG_CHANGE', 'Configuration Change'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    user_agent = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict)
    request_data = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.ip_address} - {self.created_at}"


class ThreatIntel(models.Model):
    """Threat intelligence database"""
    INTEL_TYPE_CHOICES = (
        ('ip', 'IP Address'),
        ('domain', 'Domain'),
        ('url', 'URL'),
        ('hash', 'File Hash'),
        ('email', 'Email'),
    )
    
    SOURCE_CHOICES = (
        ('manual', 'Manual Entry'),
        ('virustotal', 'VirusTotal'),
        ('abuseipdb', 'AbuseIPDB'),
        ('alienvault', 'AlienVault OTX'),
        ('internal', 'Internal Detection'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intel_type = models.CharField(max_length=20, choices=INTEL_TYPE_CHOICES)
    value = models.CharField(max_length=500)
    threat_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reference_url = models.URLField(blank=True)
    tags = models.JSONField(default=list)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'threat_intel'
        ordering = ['-threat_score', '-created_at']
        indexes = [
            models.Index(fields=['intel_type', 'value']),
            models.Index(fields=['is_active']),
            models.Index(fields=['threat_score']),
        ]
        unique_together = ['intel_type', 'value']
    
    def __str__(self):
        return f"{self.intel_type}:{self.value} - Score:{self.threat_score}"


class AuditLog(models.Model):
    """Comprehensive audit trail for compliance"""
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('ASSIGN', 'Assign'),
        ('ESCALATE', 'Escalate'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50, help_text="Model name")
    resource_id = models.CharField(max_length=100, blank=True)
    resource_name = models.CharField(max_length=500, blank=True)
    changes = models.JSONField(default=dict, help_text="Before/after values")
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=500, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    request_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['action']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.resource_type} - {self.created_at}"


class APIKey(models.Model):
    """API keys for external integrations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=64, unique=True)
    key_hash = models.CharField(max_length=128)
    prefix = models.CharField(max_length=8)
    scopes = models.JSONField(default=list)
    rate_limit = models.IntegerField(default=1000)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'api_keys'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.prefix}..."
    
    def save(self, *args, **kwargs):
        if not self.key:
            import secrets
            self.key = secrets.token_urlsafe(32)
            self.key_hash = hashlib.sha256(self.key.encode()).hexdigest()
            self.prefix = self.key[:8]
        super().save(*args, **kwargs)
    
    def verify(self, key):
        return hashlib.sha256(key.encode()).hexdigest() == self.key_hash





class ScheduledReport(models.Model):
    """Scheduled security reports"""
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    )
    
    REPORT_TYPE_CHOICES = (
        ('daily', 'Daily Summary'),
        ('weekly', 'Weekly Trend Analysis'),
        ('monthly', 'Monthly Executive Report'),
        ('compliance', 'Compliance Audit Report'),
    )
    
    FORMAT_CHOICES = (
        ('pdf', 'PDF Document'),
        ('csv', 'CSV Spreadsheet'),
        ('email', 'Email Summary'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='pdf')
    
    # Schedule configuration
    day_of_week = models.IntegerField(null=True, blank=True, help_text="0=Monday, 6=Sunday (for weekly)")
    day_of_month = models.IntegerField(null=True, blank=True, help_text="1-31 (for monthly)")
    time_of_day = models.TimeField(default='08:00:00')
    
    # Recipients
    recipients = models.TextField(help_text="Comma-separated email addresses")
    cc_recipients = models.TextField(blank=True, help_text="CC recipients")
    bcc_recipients = models.TextField(blank=True, help_text="BCC recipients")
    
    # Report configuration
    include_charts = models.BooleanField(default=True)
    include_tables = models.BooleanField(default=True)
    include_recommendations = models.BooleanField(default=True)
    date_range_days = models.IntegerField(default=7, help_text="Number of days to include")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    
    # Filters
    severity_filter = models.CharField(max_length=50, blank=True, help_text="Comma-separated severities")
    event_type_filter = models.CharField(max_length=200, blank=True, help_text="Comma-separated event types")
    
    # Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='scheduled_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'scheduled_reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def save(self, *args, **kwargs):
        # Calculate next run time
        if not self.next_run or self.status == 'active':
            self.next_run = self.calculate_next_run()
        super().save(*args, **kwargs)
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency"""
        from datetime import datetime, timedelta
        
        now = timezone.now()
        today = now.date()
        
        # Set base time
        next_run = datetime.combine(today, self.time_of_day)
        next_run = timezone.make_aware(next_run)
        
        if next_run < now:
            next_run += timedelta(days=1)
        
        if self.frequency == 'daily':
            return next_run
        
        elif self.frequency == 'weekly':
            if self.day_of_week is not None:
                days_ahead = self.day_of_week - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return next_run + timedelta(days=days_ahead)
        
        elif self.frequency == 'monthly':
            if self.day_of_month is not None:
                # Find next occurrence of day_of_month
                target_date = today.replace(day=1)
                while target_date.day != min(self.day_of_month, 28):
                    target_date += timedelta(days=1)
                
                if target_date < today or (target_date == today and next_run.time() < now.time()):
                    # Move to next month
                    if target_date.month == 12:
                        target_date = target_date.replace(year=target_date.year + 1, month=1)
                    else:
                        target_date = target_date.replace(month=target_date.month + 1)
                
                return datetime.combine(target_date, self.time_of_day)
        
        return next_run + timedelta(days=1)
    
    def mark_run(self, success=True, error=None):
        """Mark a report run"""
        self.last_run = timezone.now()
        self.run_count += 1
        self.next_run = self.calculate_next_run()
        
        if not success:
            self.status = 'failed'
            self.last_error = error
        else:
            self.status = 'active'
        
        self.save()
    
    def get_recipients_list(self):
        """Get list of recipient emails"""
        return [email.strip() for email in self.recipients.split(',') if email.strip()]
    
    def get_cc_list(self):
        """Get list of CC emails"""
        if not self.cc_recipients:
            return []
        return [email.strip() for email in self.cc_recipients.split(',') if email.strip()]
    
    def get_bcc_list(self):
        """Get list of BCC emails"""
        if not self.bcc_recipients:
            return []
        return [email.strip() for email in self.bcc_recipients.split(',') if email.strip()]


class ReportRunHistory(models.Model):
    """History of scheduled report runs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_report = models.ForeignKey(ScheduledReport, on_delete=models.CASCADE, related_name='run_history')
    status = models.CharField(max_length=20, choices=(
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ))
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    recipients_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    report_file = models.FileField(upload_to='reports/scheduled/', null=True, blank=True)
    file_size = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'report_run_history'
        ordering = ['-started_at']
        verbose_name_plural = 'Report Run History'
    
    def __str__(self):
        return f"{self.scheduled_report.name} - {self.started_at}"