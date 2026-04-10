from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm as AuthPasswordChangeForm
from .models import Notification, User, Vehicle, InsurancePolicy, Claim, SupportTicket, TicketReply, PromoCode, Notification, PressCategory, PressRelease, MediaCoverage, MediaKit, BlogPost, BlogCategory, BlogTag, BlogComment, NewsletterSubscriber
from django_countries.fields import CountryField
from django.utils import timezone
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'date_of_birth']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data

class UserLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    
# Add to forms.py

from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

User = get_user_model()


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with email validation"""
    
    email = forms.EmailField(
        label="Email Address",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email address',
            'autocomplete': 'email',
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email, is_active=True).exists():
            raise ValidationError(
                "No active account found with this email address. "
                "Please check your email or register for a new account."
            )
        return email
    
    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        """Send the password reset email"""
        subject = render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        
        html_content = render_to_string(email_template_name, context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        print(f"✅ Email sent to {to_email} from {from_email}")  # Debug
    
    def save(self, domain_override=None, subject_template_name=None,
             email_template_name=None, use_https=False, token_generator=None,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """Override save to properly send emails"""
        
        print(f"🔵 Custom save called for email: {self.cleaned_data['email']}")  # Debug
        
        if token_generator is None:
            token_generator = default_token_generator
        
        email = self.cleaned_data["email"]
        
        # Find the user(s) with this email
        for user in self.get_users(email):
            if not domain_override:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                current_site = None
                site_name = domain_override
                domain = domain_override
            
            # Build the email context
            context = {
                'email': email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
            }
            if extra_email_context is not None:
                context.update(extra_email_context)
            
            # Send the email
            self.send_mail(
                subject_template_name or 'core/emails/password_reset_subject.txt',
                email_template_name or 'core/emails/password_reset_email.html',
                context,
                from_email or '9f6029001@smtp-brevo.com',  # Use Brevo sender as fallback
                email,
                html_email_template_name=html_email_template_name,
            )


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form with password strength validation"""
    
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password',
            'autocomplete': 'new-password',
        }),
        strip=False,
    )
    
    new_password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password',
        }),
        strip=False,
    )
    
    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        
        # Password strength validation
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        
        if not any(char.isdigit() for char in password):
            raise ValidationError("Password must contain at least one number.")
        
        if not any(char.isupper() for char in password):
            raise ValidationError("Password must contain at least one uppercase letter.")
        
        if not any(char.islower() for char in password):
            raise ValidationError("Password must contain at least one lowercase letter.")
        
        return password
    

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'registration_number', 'engine_number', 'chassis_number',
            'vehicle_type', 'make', 'model', 'year', 'fuel_type',
            'engine_capacity', 'color', 'ownership_type', 
            'registration_certificate', 'current_mileage'
        ]
        widgets = {
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter registration number'}),
            'engine_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter engine number'}),
            'chassis_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter chassis number'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'make': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Toyota, Honda'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Camry, Accord'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': '1900', 'max': '2026'}),
            'fuel_type': forms.Select(attrs={'class': 'form-control'}),
            'engine_capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Engine capacity in CC'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Black, White'}),
            'ownership_type': forms.Select(attrs={'class': 'form-control'}),
            'registration_certificate': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'current_mileage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Current mileage in km', 'min': '0'}),
        }

class PolicyPurchaseForm(forms.Form):
    vehicle_id = forms.CharField(widget=forms.HiddenInput())
    coverage_type = forms.ChoiceField(choices=InsurancePolicy.POLICY_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    coverage_amount = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control'}))
    promo_code = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))


    

from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Claim, InsurancePolicy

class ClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = [
            'policy',
            'claim_type',
            'incident_date',
            'incident_location',
            'incident_description',
            'claimed_amount'
        ]
        widgets = {
            'policy': forms.Select(attrs={'class': 'form-control'}),
            'claim_type': forms.Select(attrs={'class': 'form-control'}),
            'incident_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'incident_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter incident location'}),
            'incident_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe what happened in detail...'}),
            'claimed_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter amount in Naira', 'min': '1000', 'step': '1000'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default incident date to now (rounded to nearest 5 minutes)
        if not self.initial.get('incident_date'):
            now = timezone.now()
            minutes = (now.minute // 5) * 5
            self.initial['incident_date'] = now.replace(minute=minutes, second=0, microsecond=0)
        
        if user:
            self.fields['policy'].queryset = InsurancePolicy.objects.filter(user=user, status='active')
        else:
            self.fields['policy'].queryset = InsurancePolicy.objects.filter(status='active')
    
    def clean_claimed_amount(self):
        claimed_amount = self.cleaned_data.get('claimed_amount')
        policy = self.cleaned_data.get('policy')
        
        if policy and claimed_amount:
            if claimed_amount > policy.coverage_amount:
                raise forms.ValidationError(
                    f'Claim amount cannot exceed your coverage amount of ₦{policy.coverage_amount:,.2f}'
                )
            if claimed_amount <= 0:
                raise forms.ValidationError('Claim amount must be greater than zero')
        
        return claimed_amount
    
    def clean_incident_date(self):
        incident_date = self.cleaned_data.get('incident_date')
        policy = self.cleaned_data.get('policy')
        
        if incident_date:
            now = timezone.now()
            
            # Allow incidents up to 10 minutes in the future (handles submission time)
            if incident_date > now + timedelta(minutes=10):
                raise forms.ValidationError('Incident date cannot be in the future')
            
            if policy:
                # Convert policy start_date (date) to datetime for comparison
                policy_start = timezone.make_aware(
                    datetime.combine(policy.start_date, datetime.min.time())
                )
                
                if incident_date < policy_start:
                    raise forms.ValidationError(
                        f'Incident date cannot be before policy start date ({policy.start_date.strftime("%B %d, %Y")})'
                    )
                
                # Check against policy end date
                if policy.status == 'active':
                    policy_end = timezone.make_aware(
                        datetime.combine(policy.end_date, datetime.max.time())
                    )
                    if incident_date > policy_end:
                        raise forms.ValidationError(
                            f'Incident date cannot be after policy end date ({policy.end_date.strftime("%B %d, %Y")})'
                        )
        
        return incident_date
    
    

from django import forms
from django_countries.widgets import CountrySelectWidget
from .models import User

class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'readonly': 'readonly',
            'placeholder': 'Email address'
        })
    )
    gender = forms.ChoiceField(
        choices=[('', 'Select Gender'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone_number', 
            'date_of_birth', 'gender', 'address', 'city', 'state', 
            'country', 'postal_code', 'profile_picture'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter city'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter state'}),
            'country': CountrySelectWidget(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter postal code'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['email'].initial = self.instance.email
        
        # Make country required
        self.fields['country'].required = True
        self.fields['country'].empty_label = "Select Country"
        
        # Set default to Nigeria if no country selected
        if self.instance and not self.instance.country:
            self.fields['country'].initial = 'NG'
        
        # Mark required fields
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['phone_number'].required = False
        self.fields['address'].required = False
        self.fields['city'].required = False
        self.fields['state'].required = False
        self.fields['postal_code'].required = False
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone and str(phone).strip():
            return phone
        return None
    
    def clean_country(self):
        country = self.cleaned_data.get('country')
        if not country:
            country = 'NG'  # Default to Nigeria
        return country
    

class PasswordChangeForm(AuthPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

from django import forms
from .models import SupportTicket, TicketReply

class SupportTicketForm(forms.ModelForm):
    # Honeypot field - hidden from real users
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control honeypot',
        'style': 'display:none !important; position:absolute; left:-9999px;',
        'tabindex': '-1',
        'autocomplete': 'off'
    }))
    
    # Timestamp check - to prevent rapid submissions
    timestamp = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = SupportTicket
        fields = ['subject', 'message', 'priority']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description of your issue',
                'maxlength': '200'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Please provide detailed information about your issue...',
                'maxlength': '5000'
            }),
            'priority': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_website(self):
        """Honeypot check - if filled, it's a bot"""
        website = self.cleaned_data.get('website')
        if website:
            raise forms.ValidationError("Bot detected")
        return website
    
    def clean_timestamp(self):
        """Check if form was submitted too quickly (bot)"""
        timestamp = self.cleaned_data.get('timestamp')
        if timestamp:
            import time
            current_time = int(time.time())
            # If form submitted in less than 3 seconds, likely a bot
            if current_time - int(timestamp) < 3:
                raise forms.ValidationError("Submission too fast")
        return timestamp
    
    def clean_subject(self):
        subject = self.cleaned_data.get('subject', '')
        # Check for spam patterns
        spam_keywords = ['http://', 'https://', 'www.', '.com', '.net', '.org', 'viagra', 'casino', 'lottery', 'winner']
        subject_lower = subject.lower()
        for keyword in spam_keywords:
            if keyword in subject_lower:
                raise forms.ValidationError("Invalid content detected")
        
        # Check for excessive caps (spam indicator)
        if len(subject) > 10:
            caps_ratio = sum(1 for c in subject if c.isupper()) / len(subject)
            if caps_ratio > 0.7:
                raise forms.ValidationError("Please do not use excessive capital letters")
        
        return subject
    
    def clean_message(self):
        message = self.cleaned_data.get('message', '')
        # Check for spam patterns
        spam_keywords = ['http://', 'https://', 'www.', '.com', '.net', '.org', 'viagra', 'casino', 'lottery', 'winner']
        message_lower = message.lower()
        for keyword in spam_keywords:
            if keyword in message_lower:
                raise forms.ValidationError("Invalid content detected")
        
        # Check for minimum meaningful content
        if len(message.split()) < 5:
            raise forms.ValidationError("Please provide more details about your issue")
        
        return message


class TicketReplyForm(forms.ModelForm):
    # Honeypot field
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control honeypot',
        'style': 'display:none !important; position:absolute; left:-9999px;',
        'tabindex': '-1',
        'autocomplete': 'off'
    }))
    
    timestamp = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = TicketReply
        fields = ['message', 'attachment']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Type your reply here...',
                'maxlength': '3000'
            }),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_website(self):
        website = self.cleaned_data.get('website')
        if website:
            raise forms.ValidationError("Bot detected")
        return website
    
    def clean_timestamp(self):
        timestamp = self.cleaned_data.get('timestamp')
        if timestamp:
            import time
            if int(time.time()) - int(timestamp) < 2:
                raise forms.ValidationError("Submission too fast")
        return timestamp
    
    def clean_message(self):
        message = self.cleaned_data.get('message', '')
        spam_keywords = ['http://', 'https://', 'www.', '.com', '.net', 'viagra', 'casino']
        message_lower = message.lower()
        for keyword in spam_keywords:
            if keyword in message_lower:
                raise forms.ValidationError("Links are not allowed in replies")
        return message

# Admin Forms
class AdminUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'is_active', 'is_verified', 'is_kyc_completed']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_kyc_completed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class AdminPolicyForm(forms.ModelForm):
    class Meta:
        model = InsurancePolicy
        fields = ['status', 'coverage_amount', 'premium_amount', 'start_date', 'end_date']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'coverage_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'premium_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

class AdminClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ['status', 'approved_amount', 'rejection_reason', 'surveyor_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'approved_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'surveyor_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class PromoCodeForm(forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = ['code', 'description', 'discount_type', 'discount_value', 
                  'min_purchase_amount', 'max_discount_amount', 'applicable_to',
                  'valid_from', 'valid_to', 'max_uses', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., SAVE20'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Summer Discount'}),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'min_purchase_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'max_discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'applicable_to': forms.Select(attrs={'class': 'form-control'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'valid_to': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'max_uses': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').upper().strip()
        if not code:
            raise forms.ValidationError('Code is required')
        return code
    
    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')
        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value')
        max_discount = cleaned_data.get('max_discount_amount')
        
        if valid_from and valid_to and valid_from >= valid_to:
            raise forms.ValidationError('Valid From must be before Valid To')
        
        if discount_type == 'percentage' and discount_value and discount_value > 100:
            raise forms.ValidationError('Percentage discount cannot exceed 100%')
        
        if max_discount and discount_value and max_discount > discount_value:
            self.add_error('max_discount_amount', 'Max discount cannot exceed discount value')
        
        return cleaned_data
    
    

class AdminNotificationForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter notification title'})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Enter your message here...'})
    )
    user_type = forms.ChoiceField(
        choices=[
            ('all', 'All Users'),
            ('customers', 'Only Customers'),
            ('staff', 'Only Staff'),
            ('specific', 'Specific User'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    specific_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'email'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notification_type = forms.ChoiceField(
        choices=Notification.NOTIFICATION_TYPE_CHOICES,
        initial='system_alert',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')],
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class StaffClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ['surveyor_notes', 'approved_amount', 'rejection_reason']
        widgets = {
            'surveyor_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'approved_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class StaffPolicyForm(forms.ModelForm):
    class Meta:
        model = InsurancePolicy
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class StaffTicketReplyForm(forms.ModelForm):
    change_status = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    new_status = forms.ChoiceField(choices=SupportTicket.STATUS_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    
    class Meta:
        model = TicketReply
        fields = ['message', 'attachment']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
        
        
             
class PolicyPurchaseForm(forms.Form):
    vehicle_id = forms.CharField(required=False, widget=forms.HiddenInput())
    coverage_type = forms.ChoiceField(
        choices=InsurancePolicy.POLICY_TYPE_CHOICES, 
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    coverage_amount = forms.DecimalField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    promo_code = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter promo code'}))
    
    
    
    
    
    
    
    
    
    
    
# core/forms.py or create blog/forms.py

from django import forms
from .models import BlogPost, BlogCategory, BlogTag, BlogComment, NewsletterSubscriber
from ckeditor.widgets import CKEditorWidget
from django.utils.text import slugify


class BlogPostForm(forms.ModelForm):
    """Form for creating/editing blog posts (Staff/Admin)"""
    tags_input = forms.CharField(
        required=False,
        help_text="Enter tags separated by commas",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., insurance, car, safety'})
    )
    
    class Meta:
        model = BlogPost
        fields = [
            'title', 'slug', 'category', 'featured_image', 'excerpt', 
            'content', 'status', 'is_featured', 'reading_time',
            'meta_title', 'meta_description', 'meta_keywords'
        ]
        widgets = {
            'content': CKEditorWidget(config_name='default'),
            'excerpt': forms.Textarea(attrs={'rows': 3}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = "Leave blank to auto-generate from title"
        
        if self.instance.pk:
            # Pre-populate tags input
            tags = self.instance.tags.all()
            self.initial['tags_input'] = ', '.join(tag.name for tag in tags)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            self.save_tags(instance)
        
        return instance
    
    def save_tags(self, instance):
        """Save tags from comma-separated input"""
        tags_input = self.cleaned_data.get('tags_input', '')
        if tags_input:
            tag_names = [name.strip() for name in tags_input.split(',') if name.strip()]
            tags = []
            for name in tag_names:
                tag, created = BlogTag.objects.get_or_create(
                    name=name,
                    defaults={'slug': slugify(name)}
                )
                tags.append(tag)
            instance.tags.set(tags)


class BlogCategoryForm(forms.ModelForm):
    """Form for managing blog categories"""
    class Meta:
        model = BlogCategory
        fields = ['name', 'slug', 'description', 'icon', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class BlogCommentForm(forms.ModelForm):
    """Form for submitting blog comments"""
    class Meta:
        model = BlogComment
        fields = ['name', 'email', 'website', 'content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your thoughts...'}),
            'name': forms.TextInput(attrs={'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Your email'}),
            'website': forms.URLInput(attrs={'placeholder': 'Your website (optional)'}),
        }


class NewsletterSubscribeForm(forms.ModelForm):
    """Form for newsletter subscription"""
    class Meta:
        model = NewsletterSubscriber
        fields = ['email', 'name']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Your email address'}),
            'name': forms.TextInput(attrs={'placeholder': 'Your name (optional)'}),
        }
        
        
        
        

# Add to your forms.py

class PressReleaseForm(forms.ModelForm):
    """Form for creating/editing press releases"""
    
    class Meta:
        model = PressRelease
        fields = [
            'title', 'slug', 'category', 'featured_image', 'excerpt',
            'content', 'status', 'is_featured', 'location', 'press_date',
            'media_contact_name', 'media_contact_email', 'media_contact_phone',
            'meta_title', 'meta_description', 'meta_keywords'
        ]
        widgets = {
            'content': CKEditorWidget(config_name='default'),
            'excerpt': forms.Textarea(attrs={'rows': 3}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
            'press_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class PressCategoryForm(forms.ModelForm):
    """Form for managing press categories"""
    class Meta:
        model = PressCategory
        fields = ['name', 'slug', 'description', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class MediaCoverageForm(forms.ModelForm):
    """Form for adding media coverage"""
    class Meta:
        model = MediaCoverage
        fields = ['title', 'publication', 'publication_logo', 'url', 'excerpt', 'coverage_date', 'featured', 'is_active']
        widgets = {
            'coverage_date': forms.DateInput(attrs={'type': 'date'}),
            'excerpt': forms.Textarea(attrs={'rows': 3}),
        }


class MediaKitForm(forms.ModelForm):
    """Form for media kit resources"""
    class Meta:
        model = MediaKit
        fields = ['title', 'description', 'file', 'file_type', 'is_active']    
        
        




# Add to your forms.py
from django.db.models import Q
from .models import JobPosting, JobCategory, JobLocation, JobType, JobApplication


class JobPostingForm(forms.ModelForm):
    """Form for creating/editing job postings"""
    
    class Meta:
        model = JobPosting
        fields = [
            'title', 'slug', 'category', 'location', 'job_type',
            'short_description', 'description', 'requirements', 'responsibilities', 'benefits',
            'experience_level', 'salary_min', 'salary_max', 'salary_currency', 'salary_is_visible',
            'application_email', 'application_url',
            'status', 'is_active', 'is_featured', 'is_remote', 'expires_at',
            'meta_title', 'meta_description'
        ]
        widgets = {
            'description': CKEditorWidget(config_name='default'),
            'requirements': CKEditorWidget(config_name='default'),
            'responsibilities': CKEditorWidget(config_name='default'),
            'benefits': CKEditorWidget(config_name='default'),
            'short_description': forms.Textarea(attrs={'rows': 3}),
            'expires_at': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class JobCategoryForm(forms.ModelForm):
    """Form for managing job categories"""
    class Meta:
        model = JobCategory
        fields = ['name', 'slug', 'description', 'icon', 'is_active', 'order']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class JobLocationForm(forms.ModelForm):
    """Form for managing job locations"""
    class Meta:
        model = JobLocation
        fields = ['name', 'slug', 'address', 'city', 'state', 'country', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class JobTypeForm(forms.ModelForm):
    """Form for managing job types"""
    class Meta:
        model = JobType
        fields = ['name', 'slug', 'description', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class JobApplicationForm(forms.ModelForm):
    """Form for submitting job applications"""
    
    class Meta:
        model = JobApplication
        fields = [
            'full_name', 'email', 'phone', 'location',
            'resume', 'cover_letter', 'portfolio_url', 'linkedin_url', 'github_url',
            'current_company', 'current_role', 'years_experience', 'expected_salary', 'available_from'
        ]
        widgets = {
            'cover_letter': forms.Textarea(attrs={'rows': 5}),
            'available_from': forms.DateInput(attrs={'type': 'date'}),
        }
        
        
        
        
        
        
        


# Add to your forms.py

from .models import PublicDocument, DocumentCategory


class PublicDocumentForm(forms.ModelForm):
    """Form for creating/editing public documents"""
    
    class Meta:
        model = PublicDocument
        fields = [
            'title', 'slug', 'document_number', 'user', 'policy', 'claim', 'payment',
            'category', 'document_type', 'document_file', 'description', 'tags',
            'issue_date', 'expiry_date', 'valid_until',
            'status', 'is_active', 'is_public', 'is_verified'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'e.g., certificate, insurance, 2024'}),
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['user'].required = False


class DocumentCategoryForm(forms.ModelForm):
    """Form for managing document categories"""
    class Meta:
        model = DocumentCategory
        fields = ['name', 'slug', 'description', 'icon', 'color', 'is_active', 'order']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        
        
        
        
        
        
        
        
        
# Add to your forms.py

from django import forms
from .models import ContactInquiry, OfficeLocation
import re


class ContactInquiryForm(forms.ModelForm):
    """Contact form with honeypot protection"""
    
    # Honeypot field - hidden from real users, bots will fill it
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'hidden-field',
            'style': 'display: none !important; position: absolute; left: -9999px;',
            'tabindex': '-1',
            'autocomplete': 'off',
        })
    )
    
    # Time-based honeypot - bots fill forms instantly
    timestamp = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'form_timestamp'})
    )
    
    class Meta:
        model = ContactInquiry
        fields = ['full_name', 'email', 'phone', 'policy_number', 'inquiry_type', 'subject', 'message']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'e.g., Oluwaseun Adebayo',
                'class': 'form-control',
                'autocomplete': 'name',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'you@example.com',
                'class': 'form-control',
                'autocomplete': 'email',
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '0803 456 7890',
                'class': 'form-control',
                'autocomplete': 'tel',
            }),
            'policy_number': forms.TextInput(attrs={
                'placeholder': 'e.g., VIN-2024-001234',
                'class': 'form-control',
            }),
            'inquiry_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'message': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Please provide as much detail as possible...',
                'class': 'form-control',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inquiry_type'].choices = [('', 'Select Subject')] + list(ContactInquiry.INQUIRY_TYPE_CHOICES)
        self.fields['subject'].required = False
    
    def clean_website(self):
        """Check honeypot field - should be empty"""
        website = self.cleaned_data.get('website')
        if website:
            raise forms.ValidationError("Spam detected")
        return website
    
    def clean_timestamp(self):
        """Check if form was filled too quickly (bots)"""
        timestamp = self.cleaned_data.get('timestamp')
        if timestamp:
            try:
                import time
                fill_time = int(timestamp) / 1000
                current_time = time.time()
                # If form filled in less than 3 seconds, likely a bot
                if current_time - fill_time < 3:
                    raise forms.ValidationError("Form filled too quickly")
            except (ValueError, TypeError):
                pass
        return timestamp
    
    def clean_message(self):
        """Check message for spam patterns"""
        message = self.cleaned_data.get('message', '')
        
        # Check for common spam patterns
        spam_patterns = [
            r'https?://',  # URLs (common in spam)
            r'\[url=',  # BB code URLs
            r'viagra',  # Common spam words
            r'cialis',
            r'casino',
            r'lottery',
            r'cryptocurrency',
            r'bitcoin',
        ]
        
        spam_score = 0
        for pattern in spam_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                spam_score += 1
        
        # Store spam score for later use
        self.spam_score = spam_score
        
        # If too many spam indicators, mark as suspicious but don't block
        if spam_score >= 3:
            self.is_suspicious = True
        
        return message
    
    def clean_phone(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone', '')
        # Remove non-digits for validation
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise forms.ValidationError("Please enter a valid phone number")
        return phone


class OfficeLocationForm(forms.ModelForm):
    """Form for managing office locations"""
    class Meta:
        model = OfficeLocation
        fields = ['name', 'slug', 'address', 'city', 'state', 'country', 'phone', 
                  'email', 'working_hours', 'is_headquarters', 'is_active', 'order',
                  'latitude', 'longitude']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        
        
        
        
        
        
