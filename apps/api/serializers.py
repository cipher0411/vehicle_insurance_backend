from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from apps.core.models import *
from decimal import Decimal

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'phone_number', 
                  'profile_picture', 'role', 'is_verified', 'date_of_birth', 
                  'address', 'city', 'state', 'country', 'created_at']
        read_only_fields = ['id', 'role', 'is_verified', 'created_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password', 'confirm_password', 'phone_number']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class VehicleSerializer(serializers.ModelSerializer):
    vehicle_age = serializers.ReadOnlyField()
    vehicle_full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = ['id', 'registration_number', 'engine_number', 'chassis_number', 
                  'vehicle_type', 'make', 'model', 'year', 'fuel_type', 
                  'engine_capacity', 'color', 'ownership_type', 'current_mileage',
                  'vehicle_age', 'vehicle_full_name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_vehicle_full_name(self, obj):
        return f"{obj.make} {obj.model} ({obj.year})"

class InsurancePolicySerializer(serializers.ModelSerializer):
    formatted_premium = serializers.SerializerMethodField()
    formatted_coverage = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    vehicle_details = VehicleSerializer(source='vehicle', read_only=True)
    
    class Meta:
        model = InsurancePolicy
        fields = ['id', 'policy_number', 'policy_type', 'status', 'coverage_amount',
                  'premium_amount', 'deductible', 'start_date', 'end_date',
                  'additional_benefits', 'custom_coverage', 'formatted_premium',
                  'formatted_coverage', 'is_active', 'days_remaining', 'vehicle_details']
        read_only_fields = ['id', 'policy_number', 'created_at']
    
    def get_formatted_premium(self, obj):
        return f"₦{obj.premount_amount:,.2f}"
    
    def get_formatted_coverage(self, obj):
        return f"₦{obj.coverage_amount:,.2f}"

class ClaimSerializer(serializers.ModelSerializer):
    formatted_claimed_amount = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    
    class Meta:
        model = Claim
        fields = ['id', 'claim_number', 'claim_type', 'status', 'incident_date',
                  'incident_location', 'incident_description', 'claimed_amount',
                  'approved_amount', 'documents', 'photos', 'rejection_reason',
                  'formatted_claimed_amount', 'status_color', 'created_at']
        read_only_fields = ['id', 'claim_number', 'created_at']
    
    def get_formatted_claimed_amount(self, obj):
        return f"₦{obj.claimed_amount:,.2f}"
    
    def get_status_color(self, obj):
        colors = {
            'pending': 'orange',
            'under_review': 'blue',
            'approved': 'green',
            'rejected': 'red',
            'settled': 'purple'
        }
        return colors.get(obj.status, 'gray')

class ClaimCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = ['policy', 'claim_type', 'incident_date', 'incident_location',
                  'incident_description', 'claimed_amount', 'documents', 'photos']
    
    def validate_policy(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Policy is not active")
        return value

class PaymentSerializer(serializers.ModelSerializer):
    formatted_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = ['id', 'transaction_id', 'amount', 'payment_method', 'status',
                  'formatted_amount', 'paid_at', 'created_at']
        read_only_fields = ['id', 'transaction_id', 'created_at']
    
    def get_formatted_amount(self, obj):
        return f"₦{obj.amount:,.2f}"

class InsuranceQuoteSerializer(serializers.ModelSerializer):
    formatted_premium = serializers.SerializerMethodField()
    is_valid = serializers.ReadOnlyField()
    vehicle_details = VehicleSerializer(source='vehicle', read_only=True)
    
    class Meta:
        model = InsuranceQuote
        fields = ['id', 'coverage_type', 'status', 'base_premium', 'total_premium',
                  'coverage_amount', 'deductible', 'add_ons', 'valid_until',
                  'formatted_premium', 'is_valid', 'vehicle_details', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_formatted_premium(self, obj):
        return f"₦{obj.total_premium:,.2f}"

class QuoteGenerateSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    coverage_type = serializers.ChoiceField(choices=InsuranceQuote.COVERAGE_TYPE_CHOICES)
    coverage_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    add_ons = serializers.ListField(child=serializers.CharField(), required=False)

class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'is_read', 
                  'time_ago', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_time_ago(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at)

class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['id', 'ticket_number', 'subject', 'message', 'priority', 
                  'status', 'created_at']
        read_only_fields = ['id', 'ticket_number', 'created_at']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_new_password = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({"new_password": "Passwords don't match"})
        return attrs

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": "Passwords don't match"})
        return attrs

class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = ['code', 'discount_type', 'discount_value', 'is_valid']
    
    def get_is_valid(self, obj):
        return obj.is_valid