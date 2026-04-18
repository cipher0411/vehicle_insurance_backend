import uuid
import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker
from apps.core.models import (
    User, Vehicle, InsurancePolicy, Claim, Payment, InsuranceQuote,
    InsuranceSettings, Notification, Document, SupportTicket, TicketReply,
    PromoCode, BlogCategory, BlogTag, BlogPost, BlogComment,
    NewsletterSubscriber, PressCategory, PressRelease, MediaCoverage,
    JobCategory, JobLocation, JobType, JobPosting, JobApplication,
    DocumentCategory, PublicDocument, ContactInquiry, OfficeLocation,
    NoClaimBonus, PolicyRenewal
)

fake = Faker()
User = get_user_model()

class Command(BaseCommand):
    help = 'Populate database with demo data'

    def handle(self, *args, **kwargs):
        # Clear only demo data
        self.clear_existing_data()
        
        self.stdout.write('Starting database population...')
        
        # Create users
        self.create_users()
        
        # Create settings
        self.create_settings()
        
        # Create document categories
        self.create_document_categories()
        
        # Create vehicles
        self.create_vehicles()
        
        # Create policies (with varied dates and statuses)
        self.create_policies()
        
        # Create no claim bonus for customers
        self.create_no_claim_bonus()
        
        # Create claims (some users have policy for over 3 years without claims)
        self.create_claims()
        
        # Create payments
        self.create_payments()
        
        # Create quotes
        self.create_quotes()
        
        # Create notifications
        self.create_notifications()
        
        # Create documents
        self.create_documents()
        
        # Create support tickets (reduced)
        self.create_support_tickets()
        
        # Create promo codes
        self.create_promocodes()
        
        # Create blog content (reduced)
        self.create_blog_content()
        
        # Create newsletter subscribers (reduced)
        self.create_newsletter_subscribers()
        
        # Create press content (reduced)
        self.create_press_content()
        
        # Create job postings
        self.create_job_postings()
        
        # Create contact inquiries (reduced)
        self.create_contact_inquiries()
        
        # Create office locations
        self.create_office_locations()
        
        # Print credentials
        self.print_credentials()

    def clear_existing_data(self):
        """Clear only demo data created by this script"""
        self.stdout.write('Clearing existing demo data...')
        
        # Define demo email patterns
        demo_emails = [
            'admin@vehicleinsure.ng',
        ]
        
        # Add support emails
        for i in range(1, 4):
            demo_emails.append(f'support{i}@vehicleinsure.ng')
        
        # Add customer emails (15 customers)
        for i in range(1, 16):
            demo_emails.append(f'customer{i}@vehicleinsure.ng')
        
        # Add agent emails (3 agents)
        for i in range(1, 4):
            demo_emails.append(f'agent{i}@vehicleinsure.ng')
        
        # Add underwriter emails (2 underwriters)
        for i in range(1, 3):
            demo_emails.append(f'underwriter{i}@vehicleinsure.ng')
        
        # Clear demo users only
        users_deleted = User.objects.filter(email__in=demo_emails).delete()
        self.stdout.write(f'  Cleared {users_deleted[0]} demo users')
        
        # Clear other demo data
        models_to_clear = [
            Vehicle, InsurancePolicy, Claim, Payment, InsuranceQuote,
            Notification, SupportTicket, TicketReply,
            PromoCode, BlogPost, BlogComment, BlogTag, BlogCategory,
            NewsletterSubscriber, PressRelease, MediaCoverage, PressCategory,
            JobPosting, JobApplication, JobType, JobLocation, JobCategory,
            ContactInquiry, PublicDocument, NoClaimBonus, PolicyRenewal
        ]
        
        for model in models_to_clear:
            try:
                count = model.objects.all().count()
                if count > 0:
                    model.objects.all().delete()
                    self.stdout.write(f'  Cleared {model.__name__}: {count} records')
            except Exception as e:
                pass
        
        self.stdout.write('✅ Demo data cleared successfully')

    def create_users(self):
        self.stdout.write('Creating users...')
        
        # Admin user
        admin, created = User.objects.get_or_create(
            email='admin@vehicleinsure.ng',
            defaults={
                'username': 'admin@vehicleinsure.ng',
                'first_name': 'System',
                'last_name': 'Administrator',
                'role': 'admin',
                'is_verified': True,
                'is_phone_verified': True
            }
        )
        if created:
            admin.set_password('Admin@123456')
            admin.save()
        
        # Support staff (3 support agents)
        support_agents = [
            ('John', 'Support', 'support1@vehicleinsure.ng'),
            ('Jane', 'Support', 'support2@vehicleinsure.ng'),
            ('Mike', 'Helpdesk', 'support3@vehicleinsure.ng'),
        ]
        
        support_users = []
        for first, last, email in support_agents:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': first,
                    'last_name': last,
                    'role': 'support',
                    'is_verified': True,
                    'is_phone_verified': True
                }
            )
            if created:
                user.set_password('Support@123456')
                user.save()
            support_users.append(user)
        
        # Nigerian names for realistic data
        nigerian_first_names = [
            'Chidi', 'Emeka', 'Ngozi', 'Funke', 'Adebayo', 'Tunde', 'Blessing', 
            'Victor', 'Grace', 'Daniel', 'Elizabeth', 'Michael', 'Esther', 'David',
            'Oluwaseun', 'Fatima', 'Chinwe', 'Ibrahim', 'Musa', 'Amina'
        ]
        
        nigerian_last_names = [
            'Okonkwo', 'Okafor', 'Eze', 'Nwosu', 'Ogunleye', 'Balogun', 'Adeyemi', 
            'Bello', 'Mohammed', 'Onyekwere', 'Nwachukwu', 'Ugwu', 'Obi', 'Adebayo',
            'Suleiman', 'Abubakar', 'Gbadamosi', 'Ogunlana', 'Akinwale'
        ]
        
        cities = ['Lagos', 'Abuja', 'Port Harcourt', 'Ibadan', 'Kano', 'Enugu', 'Benin City']
        states = ['Lagos', 'FCT', 'Rivers', 'Oyo', 'Kano', 'Enugu', 'Edo']
        
        # Customers (15 users)
        customers = []
        for i in range(1, 16):
            gender = random.choice(['Male', 'Female'])
            first_name = random.choice(nigerian_first_names)
            last_name = random.choice(nigerian_last_names)
            city = random.choice(cities)
            state = states[cities.index(city)] if city in cities else random.choice(states)
            
            user, created = User.objects.get_or_create(
                email=f'customer{i}@vehicleinsure.ng',
                defaults={
                    'username': f'customer{i}@vehicleinsure.ng',
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'customer',
                    'is_verified': True,
                    'is_phone_verified': True,
                    'phone_number': f'080{random.randint(10000000, 99999999)}',
                    'address': f"{random.randint(1, 999)} {fake.street_name()}, {city}",
                    'city': city,
                    'state': state,
                    'country': 'NG',
                    'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=70),
                    'gender': gender
                }
            )
            if created:
                user.set_password(f'Customer@{i}23')
                user.save()
            customers.append(user)
        
        # Agents (3 insurance agents)
        agents = []
        for i in range(1, 4):
            gender = random.choice(['Male', 'Female'])
            first_name = random.choice(nigerian_first_names)
            last_name = random.choice(nigerian_last_names)
            city = random.choice(cities)
            
            user, created = User.objects.get_or_create(
                email=f'agent{i}@vehicleinsure.ng',
                defaults={
                    'username': f'agent{i}@vehicleinsure.ng',
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'agent',
                    'is_verified': True,
                    'is_phone_verified': True,
                    'phone_number': f'081{random.randint(10000000, 99999999)}',
                    'city': city,
                    'state': states[cities.index(city)] if city in cities else random.choice(states),
                    'country': 'NG'
                }
            )
            if created:
                user.set_password('Agent@123456')
                user.save()
            agents.append(user)
        
        # Underwriters (2 underwriters)
        underwriters = []
        for i in range(1, 3):
            gender = random.choice(['Male', 'Female'])
            first_name = random.choice(nigerian_first_names)
            last_name = random.choice(nigerian_last_names)
            city = random.choice(cities)
            
            user, created = User.objects.get_or_create(
                email=f'underwriter{i}@vehicleinsure.ng',
                defaults={
                    'username': f'underwriter{i}@vehicleinsure.ng',
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'underwriter',
                    'is_verified': True,
                    'is_phone_verified': True,
                    'phone_number': f'070{random.randint(10000000, 99999999)}',
                    'city': city,
                    'state': states[cities.index(city)] if city in cities else random.choice(states),
                    'country': 'NG'
                }
            )
            if created:
                user.set_password('Under@123456')
                user.save()
            underwriters.append(user)
        
        total_users = 1 + len(support_users) + len(customers) + len(agents) + len(underwriters)
        self.stdout.write(f'✅ Created {total_users} users (1 Admin, {len(support_users)} Support, {len(customers)} Customers, {len(agents)} Agents, {len(underwriters)} Underwriters)')
        
        # Store credentials for display
        self.credentials = {
            'Admin': {'email': 'admin@vehicleinsure.ng', 'password': 'Admin@123456', 'role': 'Admin'},
        }
        
        for i, support in enumerate(support_users, 1):
            self.credentials[f'Support {i}'] = {
                'email': support.email,
                'password': 'Support@123456',
                'role': 'Support'
            }
        
        for i, agent in enumerate(agents, 1):
            self.credentials[f'Agent {i}'] = {
                'email': agent.email,
                'password': 'Agent@123456',
                'role': 'Agent'
            }
        
        for i, customer in enumerate(customers[:5], 1):
            self.credentials[f'Customer {i}'] = {
                'email': customer.email,
                'password': f'Customer@{i}23',
                'role': 'Customer'
            }
        
        # Store customers list for later use
        self.customers = customers

    def create_settings(self):
        self.stdout.write('Creating insurance settings...')
        settings, created = InsuranceSettings.objects.get_or_create(pk=1)
        if created:
            settings.base_premium_amount = Decimal('50000.00')
            settings.comprehensive_multiplier = Decimal('1.8')
            settings.third_party_multiplier = Decimal('1.0')
            settings.car_multiplier = Decimal('1.0')
            settings.motorcycle_multiplier = Decimal('0.7')
            settings.save()
            self.stdout.write('✅ Insurance settings configured')
        else:
            self.stdout.write('✅ Insurance settings already exist')

    def create_vehicles(self):
        self.stdout.write('Creating vehicles...')
        customers = User.objects.filter(role='customer', email__contains='customer')
        
        makes = ['Toyota', 'Honda', 'Hyundai', 'Kia', 'Nissan', 'Ford', 'Mercedes', 'BMW']
        models_list = ['Camry', 'Corolla', 'Civic', 'Accord', 'Elantra', 'Sonata', 'Optima', 'Altima', '3 Series', 'C-Class']
        
        for customer in customers:
            # Create 1-2 vehicles per customer
            for _ in range(random.randint(1, 2)):
                Vehicle.objects.create(
                    user=customer,
                    registration_number=f"{fake.license_plate()}-{uuid.uuid4().hex[:4].upper()}",
                    engine_number=f"ENG-{uuid.uuid4().hex[:8].upper()}",
                    chassis_number=f"CHS-{uuid.uuid4().hex[:8].upper()}",
                    vehicle_type=random.choice(['car', 'motorcycle', 'truck']),
                    make=random.choice(makes),
                    model=random.choice(models_list),
                    year=random.randint(2015, 2025),
                    fuel_type=random.choice(['petrol', 'diesel', 'electric']),
                    engine_capacity=random.randint(1200, 3500),
                    color=random.choice(['Black', 'White', 'Silver', 'Blue', 'Red', 'Gray']),
                    ownership_type=random.choice(['single', 'joint']),
                    current_mileage=random.randint(1000, 100000),
                    is_insured=random.choice([True, False])
                )
        
        self.stdout.write(f'✅ Created {Vehicle.objects.count()} vehicles')

    def create_policies(self):
        self.stdout.write('Creating insurance policies with varied dates and statuses...')
        vehicles = list(Vehicle.objects.all())
        
        policy_types = ['comprehensive', 'third_party', 'standalone']
        today = timezone.now().date()
        
        policies_created = 0
        
        for vehicle in vehicles:
            # Determine policy status based on random distribution
            status_choice = random.choices(
                ['active', 'expired', 'active', 'active', 'expired', 'pending', 'cancelled'],
                weights=[40, 25, 10, 5, 10, 5, 5],  # 40% active, 25% expired, etc.
                k=1
            )[0]
            
            if status_choice == 'active':
                # Active policies: start date between 1-365 days ago, end date in future
                days_since_start = random.randint(1, 300)
                start_date = today - timedelta(days=days_since_start)
                end_date = start_date + timedelta(days=365)
                
                # Ensure end_date is in future
                if end_date < today:
                    end_date = today + timedelta(days=random.randint(30, 300))
                    start_date = end_date - timedelta(days=365)
                
            elif status_choice == 'expired':
                # Expired policies: end date in the past
                days_expired = random.randint(1, 365)
                end_date = today - timedelta(days=days_expired)
                start_date = end_date - timedelta(days=365)
                
            elif status_choice == 'pending':
                # Pending policies: start date in near future
                start_date = today + timedelta(days=random.randint(1, 30))
                end_date = start_date + timedelta(days=365)
                
            else:  # cancelled
                # Cancelled policies: cancelled within 30-180 days of start
                days_since_start = random.randint(30, 180)
                start_date = today - timedelta(days=days_since_start)
                end_date = start_date + timedelta(days=365)
            
            try:
                policy = InsurancePolicy.objects.create(
                    policy_number=f"POL-{uuid.uuid4().hex[:8].upper()}",
                    user=vehicle.user,
                    vehicle=vehicle,
                    policy_type=random.choice(policy_types),
                    status=status_choice,
                    coverage_amount=Decimal(random.randint(1000000, 7000000)),
                    premium_amount=Decimal(random.randint(50000, 250000)),
                    deductible=Decimal(random.randint(5000, 30000)),
                    start_date=start_date,
                    end_date=end_date,
                    terms_accepted=True
                )
                policies_created += 1
                
                # Create renewal record for policies that are 40 days from expiry
                if status_choice == 'active':
                    days_to_expiry = (end_date - today).days
                    if 35 <= days_to_expiry <= 45:  # ~40 days to expire
                        PolicyRenewal.objects.create(
                            original_policy=policy,
                            user=policy.user,
                            original_premium=policy.premium_amount,
                            renewal_premium=policy.premium_amount * Decimal('0.9'),  # 10% discount
                            ncb_discount=policy.premium_amount * Decimal('0.1'),
                            renewal_date=today,
                            expiry_date=end_date,
                            new_start_date=end_date + timedelta(days=1),
                            new_end_date=end_date + timedelta(days=366),
                            status='pending'
                        )
                        self.stdout.write(f'  Created renewal for policy {policy.policy_number} (expires in {days_to_expiry} days)')
                        
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {policies_created} policies')
        
        # Log policy status distribution
        active_count = InsurancePolicy.objects.filter(status='active').count()
        expired_count = InsurancePolicy.objects.filter(status='expired').count()
        pending_count = InsurancePolicy.objects.filter(status='pending').count()
        cancelled_count = InsurancePolicy.objects.filter(status='cancelled').count()
        
        self.stdout.write(f'  Policy Status Distribution: Active: {active_count}, Expired: {expired_count}, Pending: {pending_count}, Cancelled: {cancelled_count}')

    def create_no_claim_bonus(self):
        self.stdout.write('Creating No Claim Bonus records...')
        
        customers = User.objects.filter(role='customer', email__contains='customer')
        
        ncb_created = 0
        for customer in customers:
            vehicles = Vehicle.objects.filter(user=customer)
            for vehicle in vehicles:
                # Check if customer has any claims
                has_claims = Claim.objects.filter(user=customer, vehicle=vehicle).exists()
                
                if not has_claims:
                    # Calculate claim-free years (some up to 5+ years)
                    claim_free_years = random.choices(
                        [0, 1, 2, 3, 4, 5, 6],
                        weights=[5, 10, 15, 25, 20, 15, 10],
                        k=1
                    )[0]
                    
                    ncb_percentage = 0
                    if claim_free_years >= 5:
                        ncb_percentage = 50
                    elif claim_free_years >= 4:
                        ncb_percentage = 45
                    elif claim_free_years >= 3:
                        ncb_percentage = 35
                    elif claim_free_years >= 2:
                        ncb_percentage = 25
                    elif claim_free_years >= 1:
                        ncb_percentage = 20
                    
                    try:
                        NoClaimBonus.objects.create(
                            user=customer,
                            vehicle=vehicle,
                            current_ncb_percentage=ncb_percentage,
                            claim_free_years=claim_free_years,
                            last_claim_date=None if claim_free_years > 0 else timezone.now().date() - timedelta(days=random.randint(100, 1000)),
                            is_protected=random.choice([True, False]) if claim_free_years >= 3 else False
                        )
                        ncb_created += 1
                        
                        if claim_free_years >= 3:
                            self.stdout.write(f'  Customer {customer.email} has {claim_free_years} claim-free years with {ncb_percentage}% NCB')
                    except Exception as e:
                        pass
        
        self.stdout.write(f'✅ Created {ncb_created} No Claim Bonus records')

    def create_claims(self):
        self.stdout.write('Creating claims...')
        policies = list(InsurancePolicy.objects.filter(status='active'))
        
        claim_types = ['accident', 'theft', 'fire', 'vandalism', 'third_party']
        statuses = ['pending', 'under_review', 'approved', 'settled', 'rejected']
        
        claims_created = 0
        customers_with_claims = set()
        
        for policy in policies[:20]:  # Limit to 20 policies for claims
            # 40% chance of having a claim
            if random.random() < 0.4:
                try:
                    Claim.objects.create(
                        claim_number=f"CLM-{uuid.uuid4().hex[:8].upper()}",
                        policy=policy,
                        user=policy.user,
                        vehicle=policy.vehicle,
                        claim_type=random.choice(claim_types),
                        status=random.choice(statuses),
                        incident_date=timezone.now() - timedelta(days=random.randint(1, 180)),
                        incident_location=fake.address()[:255],
                        incident_description=fake.text(max_nb_chars=150),
                        claimed_amount=Decimal(random.randint(100000, 1500000)),
                        approved_amount=Decimal(random.randint(50000, 1000000)) if random.choice([True, False]) else None
                    )
                    claims_created += 1
                    customers_with_claims.add(policy.user.email)
                except Exception as e:
                    pass
        
        # Identify customers with policies over 3 years without claims
        three_years_ago = timezone.now().date() - timedelta(days=1095)
        
        # Get customers with policies older than 3 years
        old_policies = InsurancePolicy.objects.filter(
            start_date__lte=three_years_ago,
            status__in=['active', 'expired']
        ).values_list('user', flat=True).distinct()
        
        # Check which of these have no claims
        no_claim_customers = []
        for user_id in old_policies:
            if not Claim.objects.filter(user_id=user_id).exists():
                user = User.objects.filter(id=user_id).first()
                if user:
                    no_claim_customers.append(user.email)
        
        if no_claim_customers:
            self.stdout.write(f'  Customers with policies over 3 years and NO claims:')
            for email in no_claim_customers[:5]:  # Show first 5
                self.stdout.write(f'    - {email}')
        
        self.stdout.write(f'✅ Created {claims_created} claims')
        self.stdout.write(f'  Customers with at least one claim: {len(customers_with_claims)}')
        self.stdout.write(f'  Customers with 3+ years claim-free: {len(no_claim_customers)}')

    def create_payments(self):
        self.stdout.write('Creating payments...')
        policies = InsurancePolicy.objects.all()[:20]
        
        payment_methods = ['card', 'bank_transfer', 'mobile_wallet']
        statuses = ['completed', 'pending', 'failed']
        
        payments_created = 0
        for policy in policies:
            try:
                Payment.objects.create(
                    transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    policy=policy,
                    user=policy.user,
                    amount=policy.premium_amount,
                    payment_method=random.choice(payment_methods),
                    status=random.choice(statuses),
                    payment_reference=f"REF-{uuid.uuid4().hex[:10].upper()}",
                    paid_at=timezone.now() - timedelta(days=random.randint(1, 180)) if random.choice([True, False]) else None
                )
                payments_created += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {payments_created} payments')

    def create_quotes(self):
        self.stdout.write('Creating insurance quotes...')
        vehicles = Vehicle.objects.all()
        
        if not vehicles.exists():
            self.stdout.write('  No vehicles found, skipping quotes...')
            return
        
        coverage_types = ['basic', 'standard', 'premium']
        statuses = ['pending', 'approved', 'expired']
        
        quotes_created = 0
        for vehicle in vehicles[:15]:
            try:
                InsuranceQuote.objects.create(
                    user=vehicle.user,
                    vehicle=vehicle,
                    coverage_type=random.choice(coverage_types),
                    status=random.choice(statuses),
                    base_premium=Decimal(random.randint(40000, 150000)),
                    total_premium=Decimal(random.randint(50000, 200000)),
                    coverage_amount=Decimal(random.randint(1000000, 6000000)),
                    deductible=Decimal(random.randint(5000, 30000)),
                    valid_until=timezone.now() + timedelta(days=30),
                    coverage_details={
                        'collision': True,
                        'theft': True,
                        'liability': True,
                        'fire': random.choice([True, False])
                    }
                )
                quotes_created += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {quotes_created} insurance quotes')

    def create_notifications(self):
        self.stdout.write('Creating notifications...')
        customers = User.objects.filter(role='customer', email__contains='customer')[:12]
        
        notification_types = ['claim_update', 'policy_expiry', 'payment_confirmation', 'quote_generated', 'system_alert']
        titles = [
            'Policy Renewal Reminder', 'Claim Status Update', 'Payment Received',
            'New Quote Available', 'Document Ready', 'Policy Expiring Soon',
            'Welcome to VehicleInsure', 'Your Policy is Active'
        ]
        
        notifications_created = 0
        for customer in customers:
            for _ in range(random.randint(2, 5)):
                try:
                    Notification.objects.create(
                        user=customer,
                        title=random.choice(titles),
                        message=fake.text(max_nb_chars=100),
                        notification_type=random.choice(notification_types),
                        is_read=random.choice([True, False])
                    )
                    notifications_created += 1
                except Exception as e:
                    pass
        
        self.stdout.write(f'✅ Created {notifications_created} notifications')

    def create_documents(self):
        self.stdout.write('Creating documents...')
        customers = User.objects.filter(role='customer', email__contains='customer')[:12]
        
        doc_types = ['driving_license', 'rc', 'other']
        verification_statuses = ['pending', 'verified', 'rejected']
        doc_names = ["Driver's License", 'Vehicle Registration', 'Identification Card', 'Proof of Address']
        
        documents_created = 0
        for customer in customers:
            for _ in range(random.randint(1, 2)):
                try:
                    Document.objects.create(
                        user=customer,
                        name=random.choice(doc_names),
                        document_type=random.choice(doc_types),
                        document_number=f"DOC-{uuid.uuid4().hex[:8].upper()}",
                        is_verified=random.choice([True, False]),
                        verification_status=random.choice(verification_statuses)
                    )
                    documents_created += 1
                except Exception as e:
                    pass
        
        self.stdout.write(f'✅ Created {documents_created} documents')

    def create_support_tickets(self):
        self.stdout.write('Creating support tickets (reduced)...')
        customers = User.objects.filter(role='customer', email__contains='customer')[:6]  # Reduced from 10 to 6
        support_staff = User.objects.filter(role='support')
        
        priorities = ['low', 'medium', 'high']
        statuses = ['open', 'in_progress', 'resolved', 'closed']
        subjects = [
            'Login Issue', 'Payment Failed', 'Claim Processing', 'Policy Question',
            'Document Upload Problem', 'Need Assistance', 'Update Information'
        ]
        
        tickets_created = 0
        for customer in customers:
            # 60% chance of having a ticket (reduced)
            if random.random() < 0.6:
                try:
                    ticket = SupportTicket.objects.create(
                        ticket_number=f"TKT-{uuid.uuid4().hex[:8].upper()}",
                        user=customer,
                        subject=random.choice(subjects),
                        message=fake.text(max_nb_chars=150),
                        priority=random.choice(priorities),
                        status=random.choice(statuses),
                        assigned_to=random.choice(support_staff) if support_staff.exists() else None
                    )
                    tickets_created += 1
                    
                    # Add reply sometimes (40% chance)
                    if random.random() < 0.4 and support_staff.exists():
                        TicketReply.objects.create(
                            ticket=ticket,
                            user=random.choice(support_staff),
                            message=fake.text(max_nb_chars=100)
                        )
                except Exception as e:
                    pass
        
        self.stdout.write(f'✅ Created {tickets_created} support tickets')

    def create_promocodes(self):
        self.stdout.write('Creating promo codes...')
        admin = User.objects.filter(role='admin').first()
        
        promos = [
            {'code': 'WELCOME20', 'discount_value': 20, 'discount_type': 'percentage', 'description': 'Welcome discount for new customers'},
            {'code': 'SAVE15', 'discount_value': 15, 'discount_type': 'percentage', 'description': '15% off on all policies'},
            {'code': 'FLAT5000', 'discount_value': 5000, 'discount_type': 'fixed', 'description': 'Flat ₦5000 off'},
            {'code': 'RENEW10', 'discount_value': 10, 'discount_type': 'percentage', 'description': '10% off on renewals'},
        ]
        
        for promo_data in promos:
            try:
                PromoCode.objects.get_or_create(
                    code=promo_data['code'],
                    defaults={
                        'discount_type': promo_data['discount_type'],
                        'discount_value': Decimal(promo_data['discount_value']),
                        'valid_from': timezone.now(),
                        'valid_to': timezone.now() + timedelta(days=90),
                        'max_uses': 100,
                        'is_active': True,
                        'description': promo_data['description'],
                        'created_by': admin
                    }
                )
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {PromoCode.objects.count()} promo codes')

    def create_blog_content(self):
        self.stdout.write('Creating blog content (reduced)...')
        
        # Categories
        categories = []
        cat_names = ['Insurance Tips', 'Car Maintenance', 'Safety Tips']
        for name in cat_names:
            cat, created = BlogCategory.objects.get_or_create(
                name=name,
                defaults={
                    'slug': slugify(name),
                    'description': f"Posts about {name.lower()}"
                }
            )
            categories.append(cat)
        
        # Tags
        tags = []
        tag_names = ['Insurance', 'Vehicle', 'Safety', 'Tips']
        for name in tag_names:
            tag, created = BlogTag.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name)}
            )
            tags.append(tag)
        
        # Posts (reduced from 8 to 4)
        users = User.objects.all()
        posts_created = 0
        for i in range(4):
            try:
                post = BlogPost.objects.create(
                    title=fake.sentence(nb_words=6)[:200],
                    slug=f"blog-post-{i+1}-{uuid.uuid4().hex[:4]}",
                    category=random.choice(categories),
                    excerpt=fake.text(max_nb_chars=150),
                    content=f"<p>{fake.text(max_nb_chars=500)}</p><p>{fake.text(max_nb_chars=500)}</p>",
                    status='published',
                    author=random.choice(users) if users.exists() else None,
                    published_at=timezone.now() - timedelta(days=random.randint(1, 90)),
                    is_featured=random.choice([True, False])
                )
                post.tags.add(*random.sample(tags, k=min(random.randint(2, 3), len(tags))))
                posts_created += 1
                
                # Add comments (reduced)
                for _ in range(random.randint(0, 2)):  # 0-2 comments instead of 1-3
                    BlogComment.objects.create(
                        post=post,
                        name=fake.name()[:100],
                        email=fake.email(),
                        content=fake.text(max_nb_chars=100),
                        is_approved=True
                    )
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {posts_created} blog posts')

    def create_newsletter_subscribers(self):
        self.stdout.write('Creating newsletter subscribers (reduced)...')
        subscribers_created = 0
        for i in range(8):  # Reduced from 15 to 8
            try:
                NewsletterSubscriber.objects.get_or_create(
                    email=fake.email(),
                    defaults={
                        'name': fake.name()[:100],
                        'is_active': True,
                        'is_confirmed': True,
                        'source': random.choice(['website', 'blog', 'footer'])
                    }
                )
                subscribers_created += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {subscribers_created} subscribers')

    def create_press_content(self):
        self.stdout.write('Creating press releases (reduced)...')
        
        # Categories
        press_cats = ['Product Launch', 'Company News']
        categories = []
        for name in press_cats:
            cat, created = PressCategory.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name)}
            )
            categories.append(cat)
        
        # Press releases (reduced from 5 to 3)
        users = User.objects.filter(role='admin').first()
        releases_created = 0
        for i in range(3):
            try:
                PressRelease.objects.create(
                    title=fake.sentence(nb_words=8)[:200],
                    slug=f"press-release-{i+1}-{uuid.uuid4().hex[:4]}",
                    category=random.choice(categories),
                    excerpt=fake.text(max_nb_chars=150),
                    content=f"<p>{fake.text(max_nb_chars=400)}</p>",
                    status='published',
                    author=users,
                    published_at=timezone.now() - timedelta(days=random.randint(1, 120)),
                    location=random.choice(['Lagos', 'Abuja', 'International'])
                )
                releases_created += 1
            except Exception as e:
                pass
        
        # Media coverage (reduced from 8 to 4)
        publications = ['TechCrunch', 'AutoNews', 'Business Insider', 'Pulse']
        media_created = 0
        for i in range(4):
            try:
                MediaCoverage.objects.create(
                    title=fake.sentence(nb_words=6)[:200],
                    publication=random.choice(publications)[:200],
                    url=fake.url()[:500],
                    excerpt=fake.text(max_nb_chars=120),
                    coverage_date=timezone.now().date() - timedelta(days=random.randint(1, 90)),
                    is_active=True,
                    featured=random.choice([True, False])
                )
                media_created += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {releases_created} press releases and {media_created} media coverage items')

    def create_job_postings(self):
        self.stdout.write('Creating job postings...')
        
        # Categories
        job_cats = ['Engineering', 'Sales', 'Marketing']
        categories = []
        for name in job_cats:
            cat, created = JobCategory.objects.get_or_create(
                name=name,
                defaults={
                    'slug': slugify(name),
                    'description': f"Jobs in {name}"
                }
            )
            categories.append(cat)
        
        # Locations
        locations = []
        loc_data = [
            ('Lagos HQ', 'Lagos', 'Lagos'),
            ('Abuja Office', 'Abuja', 'FCT'),
        ]
        for name, city, state in loc_data:
            loc, created = JobLocation.objects.get_or_create(
                name=name,
                defaults={
                    'slug': slugify(name),
                    'city': city,
                    'state': state,
                    'country': 'NG'
                }
            )
            locations.append(loc)
        
        # Job Types
        job_types = ['Full-time', 'Part-time', 'Remote']
        types = []
        for name in job_types:
            jt, created = JobType.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name)}
            )
            types.append(jt)
        
        # Job postings (reduced from 8 to 5)
        users = User.objects.filter(role='admin').first()
        job_titles = [
            'Software Engineer', 'Sales Executive', 'Marketing Manager', 
            'Customer Support Agent', 'Data Analyst'
        ]
        
        jobs_created = 0
        for i, title in enumerate(job_titles):
            try:
                JobPosting.objects.create(
                    title=title,
                    slug=f"job-{i+1}-{uuid.uuid4().hex[:4]}",
                    category=random.choice(categories),
                    location=random.choice(locations),
                    job_type=random.choice(types),
                    short_description=fake.text(max_nb_chars=150),
                    description=f"<p>{fake.text(max_nb_chars=400)}</p>",
                    requirements=f"<p>{fake.text(max_nb_chars=200)}</p>",
                    responsibilities=f"<p>{fake.text(max_nb_chars=200)}</p>",
                    experience_level=random.choice(['entry', 'mid', 'senior']),
                    salary_min=Decimal(random.randint(100000, 400000)),
                    salary_max=Decimal(random.randint(500000, 1500000)),
                    application_email='careers@vehicleinsure.ng',
                    status='published',
                    is_active=True,
                    created_by=users,
                    published_at=timezone.now() - timedelta(days=random.randint(1, 45))
                )
                jobs_created += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {jobs_created} job postings')

    def create_contact_inquiries(self):
        self.stdout.write('Creating contact inquiries (reduced)...')
        
        inquiry_types = ['general', 'quote', 'claim', 'policy', 'complaint', 'partnership']
        
        inquiries_created = 0
        for i in range(8):  # Reduced from 12 to 8
            try:
                ContactInquiry.objects.create(
                    full_name=fake.name()[:200],
                    email=fake.email(),
                    phone=fake.phone_number()[:20],
                    inquiry_type=random.choice(inquiry_types),
                    subject=fake.sentence(nb_words=5)[:200],
                    message=fake.text(max_nb_chars=200),
                    status=random.choice(['pending', 'in_progress', 'resolved']),
                    priority=random.choice(['low', 'medium', 'high'])
                )
                inquiries_created += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {inquiries_created} contact inquiries')

    def create_office_locations(self):
        self.stdout.write('Creating office locations...')
        
        offices = [
            {'name': 'Lagos Headquarters', 'city': 'Lagos', 'state': 'Lagos', 'is_headquarters': True},
            {'name': 'Abuja Regional Office', 'city': 'Abuja', 'state': 'FCT', 'is_headquarters': False},
            {'name': 'Port Harcourt Branch', 'city': 'Port Harcourt', 'state': 'Rivers', 'is_headquarters': False},
        ]
        
        for office_data in offices:
            try:
                OfficeLocation.objects.get_or_create(
                    name=office_data['name'],
                    defaults={
                        'slug': slugify(office_data['name']),
                        'address': f"Plot {random.randint(1, 30)} {office_data['name']} Road, {office_data['city']}",
                        'city': office_data['city'],
                        'state': office_data['state'],
                        'country': 'NG',
                        'phone': f"+234 800 123 {random.randint(1000, 9999)}",
                        'email': f"info@{office_data['name'].replace(' ', '').lower()}.com",
                        'working_hours': "Mon-Fri: 9AM - 6PM",
                        'is_headquarters': office_data['is_headquarters'],
                        'is_active': True
                    }
                )
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {OfficeLocation.objects.count()} office locations')

    def create_document_categories(self):
        self.stdout.write('Creating document categories...')
        
        doc_cats = [
            {'name': 'Policies', 'icon': 'fa-file-contract', 'color': '#4169E1'},
            {'name': 'Claims', 'icon': 'fa-file-invoice', 'color': '#DC2626'},
            {'name': 'Receipts', 'icon': 'fa-receipt', 'color': '#10B981'},
        ]
        
        for cat_data in doc_cats:
            try:
                DocumentCategory.objects.get_or_create(
                    name=cat_data['name'],
                    defaults={
                        'slug': slugify(cat_data['name']),
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                        'is_active': True
                    }
                )
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {DocumentCategory.objects.count()} document categories')

    def print_credentials(self):
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('📋 DEMO LOGIN CREDENTIALS'))
        self.stdout.write('='*70)
        
        for name, creds in self.credentials.items():
            self.stdout.write(f'\n{self.style.SUCCESS(name)}:')
            self.stdout.write(f'  Email: {creds["email"]}')
            self.stdout.write(f'  Password: {creds["password"]}')
            self.stdout.write(f'  Role: {creds["role"]}')
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('🎉 All demo data created successfully!'))
        self.stdout.write('='*70)
        self.stdout.write('\n📊 Summary:')
        self.stdout.write(f'  • Users: {User.objects.count()}')
        self.stdout.write(f'  • Vehicles: {Vehicle.objects.count()}')
        self.stdout.write(f'  • Policies: {InsurancePolicy.objects.count()}')
        self.stdout.write(f'  • Claims: {Claim.objects.count()}')
        self.stdout.write(f'  • Payments: {Payment.objects.count()}')
        self.stdout.write(f'  • Quotes: {InsuranceQuote.objects.count()}')
        self.stdout.write(f'  • Blog Posts: {BlogPost.objects.count()}')
        self.stdout.write(f'  • Job Postings: {JobPosting.objects.count()}')
        self.stdout.write('='*70)