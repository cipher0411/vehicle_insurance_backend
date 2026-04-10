from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Vehicle, InsurancePolicy, Claim, Payment, 
    InsuranceQuote, Notification, Document, SupportTicket, 
    TicketReply, PromoCode, UserActivityLog
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'get_full_name', 'role', 'is_verified', 'is_active', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_active', 'country')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'role', 'profile_picture', 'date_of_birth', 
                      'address', 'city', 'state', 'country', 'postal_code',
                      'is_verified', 'is_phone_verified', 'is_kyc_completed',
                      'device_token')
        }),
    )

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'user', 'make', 'model', 'year', 'vehicle_type')
    list_filter = ('vehicle_type', 'fuel_type', 'year', 'ownership_type')
    search_fields = ('registration_number', 'engine_number', 'chassis_number', 'user__email')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(InsurancePolicy)
class InsurancePolicyAdmin(admin.ModelAdmin):
    list_display = ('policy_number', 'user', 'policy_type', 'status', 'premium_amount', 'start_date', 'end_date')
    list_filter = ('policy_type', 'status', 'start_date', 'end_date')
    search_fields = ('policy_number', 'user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user', 'vehicle')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_number', 'user', 'policy', 'claim_type', 'status', 'claimed_amount', 'approved_amount')
    list_filter = ('claim_type', 'status', 'created_at')
    search_fields = ('claim_number', 'user__email', 'policy__policy_number')
    raw_id_fields = ('user', 'policy', 'approved_by')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'user', 'policy', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('payment_method', 'status', 'created_at')
    search_fields = ('transaction_id', 'payment_reference', 'user__email')
    raw_id_fields = ('user', 'policy')

@admin.register(InsuranceQuote)
class InsuranceQuoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'vehicle', 'coverage_type', 'total_premium', 'status', 'created_at')
    list_filter = ('coverage_type', 'status', 'created_at')
    search_fields = ('user__email', 'vehicle__registration_number')
    raw_id_fields = ('user', 'vehicle')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__email', 'title')
    raw_id_fields = ('user',)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'document_number', 'is_verified', 'created_at')
    list_filter = ('document_type', 'is_verified', 'created_at')
    search_fields = ('user__email', 'document_number')
    raw_id_fields = ('user', 'verified_by')

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'user', 'subject', 'priority', 'status', 'created_at')
    list_filter = ('priority', 'status', 'created_at')
    search_fields = ('ticket_number', 'user__email', 'subject')
    raw_id_fields = ('user', 'assigned_to')

from django.contrib import admin
from django import forms
from .models import InsuranceSettings, PromoCode

class InsuranceSettingsForm(forms.ModelForm):
    class Meta:
        model = InsuranceSettings
        fields = '__all__'
        widgets = {
            'comprehensive_multiplier': forms.NumberInput(attrs={'step': '0.1'}),
            'third_party_multiplier': forms.NumberInput(attrs={'step': '0.1'}),
            'standalone_multiplier': forms.NumberInput(attrs={'step': '0.1'}),
            'personal_accident_multiplier': forms.NumberInput(attrs={'step': '0.1'}),
        }

@admin.register(InsuranceSettings)
class InsuranceSettingsAdmin(admin.ModelAdmin):
    form = InsuranceSettingsForm
    
    fieldsets = (
        ('Coverage Type Multipliers', {
            'fields': (
                'comprehensive_multiplier', 'third_party_multiplier',
                'standalone_multiplier', 'personal_accident_multiplier'
            ),
            'description': 'Multipliers applied to base premium based on coverage type'
        }),
        ('Base Premium Settings', {
            'fields': ('base_premium_amount', 'base_coverage_reference')
        }),
        ('Minimum Premium Settings', {
            'fields': (
                'min_premium_comprehensive', 'min_premium_third_party',
                'min_premium_standalone', 'min_premium_personal_accident'
            )
        }),
        ('Vehicle Age Multipliers', {
            'fields': (
                'age_0_1_multiplier', 'age_2_3_multiplier', 'age_4_5_multiplier',
                'age_6_10_multiplier', 'age_10_plus_multiplier'
            )
        }),
        ('Vehicle Type Multipliers', {
            'fields': (
                'car_multiplier', 'motorcycle_multiplier', 'truck_multiplier',
                'bus_multiplier', 'rickshaw_multiplier'
            )
        }),
        ('Engine Capacity Multipliers', {
            'fields': (
                'engine_above_3000_multiplier', 'engine_2000_3000_multiplier',
                'engine_1000_2000_multiplier', 'engine_below_1000_multiplier'
            )
        }),
        ('Deductible Settings', {
            'fields': ('deductible_percentage', 'min_deductible', 'max_deductible')
        }),
        ('Add-on Costs', {
            'fields': (
                'roadside_assistance_cost', 'zero_depreciation_cost',
                'engine_protection_cost', 'personal_accident_cover_cost'
            )
        }),
        ('Promo Code Defaults', {
            'fields': ('default_promo_percentage',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not InsuranceSettings.objects.exists()
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'valid_from', 'valid_to', 
                   'used_count', 'max_uses', 'is_active', 'is_valid']
    list_filter = ['is_active', 'discount_type', 'applicable_to', 'created_at']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count', 'created_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Promo Code Details', {
            'fields': ('code', 'description', 'discount_type', 'discount_value')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_to', 'max_uses', 'is_active')
        }),
        ('Restrictions', {
            'fields': ('min_purchase_amount', 'applicable_to', 'max_discount_amount')
        }),
        ('Statistics', {
            'fields': ('used_count', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New promo code
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def is_valid(self, obj):
        return obj.is_valid
    is_valid.boolean = True

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)