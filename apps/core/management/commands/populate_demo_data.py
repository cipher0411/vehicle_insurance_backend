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
    DocumentCategory, PublicDocument, ContactInquiry, OfficeLocation
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
        
        # Create policies
        self.create_policies()
        
        # Create claims
        self.create_claims()
        
        # Create payments
        self.create_payments()
        
        # Create quotes
        self.create_quotes()
        
        # Create notifications
        self.create_notifications()
        
        # Create documents
        self.create_documents()
        
        # Create support tickets
        self.create_support_tickets()
        
        # Create promo codes
        self.create_promocodes()
        
        # Create blog content
        self.create_blog_content()
        
        # Create newsletter subscribers
        self.create_newsletter_subscribers()
        
        # Create press content
        self.create_press_content()
        
        # Create job postings
        self.create_job_postings()
        
        # Create contact inquiries
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
        for i in range(1, 6):
            demo_emails.append(f'support{i}@vehicleinsure.ng')
        
        # Add customer emails (50 customers)
        for i in range(1, 51):
            demo_emails.append(f'customer{i}@vehicleinsure.ng')
        
        # Add agent emails (10 agents)
        for i in range(1, 11):
            demo_emails.append(f'agent{i}@vehicleinsure.ng')
        
        # Add underwriter emails (5 underwriters)
        for i in range(1, 6):
            demo_emails.append(f'underwriter{i}@vehicleinsure.ng')
        
        # Clear demo users only
        users_deleted = User.objects.filter(email__in=demo_emails).delete()
        self.stdout.write(f'  Cleared {users_deleted[0]} demo users')
        
        # Clear other demo data (all records from these tables are demo data)
        models_to_clear = [
            Vehicle, InsurancePolicy, Claim, Payment, InsuranceQuote,
            Notification, SupportTicket, TicketReply,
            PromoCode, BlogPost, BlogComment, BlogTag, BlogCategory,
            NewsletterSubscriber, PressRelease, MediaCoverage, PressCategory,
            JobPosting, JobApplication, JobType, JobLocation, JobCategory,
            ContactInquiry, PublicDocument
        ]
        
        for model in models_to_clear:
            try:
                count = model.objects.all().count()
                if count > 0:
                    model.objects.all().delete()
                    self.stdout.write(f'  Cleared {model.__name__}: {count} records')
            except Exception as e:
                pass  # Skip if error
        
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
        
        # Support staff (5 support agents)
        support_agents = [
            ('John', 'Support', 'support1@vehicleinsure.ng'),
            ('Jane', 'Support', 'support2@vehicleinsure.ng'),
            ('Mike', 'Helpdesk', 'support3@vehicleinsure.ng'),
            ('Sarah', 'Support', 'support4@vehicleinsure.ng'),
            ('David', 'Customer Care', 'support5@vehicleinsure.ng'),
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
        nigerian_first_names_male = [
            'Chidi', 'Emeka', 'Adebayo', 'Tunde', 'Victor', 'Daniel', 'Michael', 'David',
            'Joseph', 'Samuel', 'Joshua', 'Jonathan', 'Stephen', 'Andrew', 'Philip',
            'Simon', 'Timothy', 'Paul', 'Oluwaseun', 'Ibrahim', 'Musa', 'Adamu',
            'Okechukwu', 'Chukwudi', 'Nnamdi', 'Uchenna', 'Ifeanyi', 'Obinna'
        ]
        
        nigerian_first_names_female = [
            'Ngozi', 'Funke', 'Chinwe', 'Fatima', 'Blessing', 'Grace', 'Esther', 'Mary',
            'Jennifer', 'Elizabeth', 'Ruth', 'Deborah', 'Hannah', 'Patience', 'Joy',
            'Catherine', 'Martha', 'Rebecca', 'Sarah', 'Amina', 'Zainab', 'Bola',
            'Chiamaka', 'Adaeze', 'Ifeoma', 'Nkechi', 'Amara', 'Chidinma'
        ]
        
        nigerian_last_names = [
            'Okonkwo', 'Okafor', 'Eze', 'Nwosu', 'Ogunleye', 'Balogun', 'Adeyemi', 'Bello',
            'Mohammed', 'Aliu', 'Onyekwere', 'Nwachukwu', 'Ugwu', 'Obi', 'Ezeobi',
            'Adebayo', 'Oladipo', 'Fashola', 'Oyinlola', 'Kanu', 'Okocha', 'Ikpeba',
            'Amokachi', 'Yekini', 'Osimhen', 'Lookman', 'Iwobi', 'Ndidi', 'Ejuke', 'Simon',
            'Adewale', 'Ogunlana', 'Akinwale', 'Ogunbiyi', 'Suleiman', 'Abubakar', 'Gbadamosi'
        ]
        
        cities = ['Lagos', 'Abuja', 'Port Harcourt', 'Ibadan', 'Kano', 'Enugu', 'Benin City', 
                  'Jos', 'Abeokuta', 'Warri', 'Calabar', 'Uyo', 'Maiduguri', 'Kaduna', 'Ilorin']
        states = ['Lagos', 'FCT', 'Rivers', 'Oyo', 'Kano', 'Enugu', 'Edo', 'Plateau', 'Ogun', 
                  'Delta', 'Cross River', 'Akwa Ibom', 'Borno', 'Kaduna', 'Kwara']
        
        # Customers (50 users)
        customers = []
        for i in range(1, 51):
            gender = random.choice(['Male', 'Female'])
            if gender == 'Male':
                first_name = random.choice(nigerian_first_names_male)
            else:
                first_name = random.choice(nigerian_first_names_female)
            
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
        
        # Agents (10 insurance agents)
        agents = []
        for i in range(1, 11):
            gender = random.choice(['Male', 'Female'])
            if gender == 'Male':
                first_name = random.choice(nigerian_first_names_male)
            else:
                first_name = random.choice(nigerian_first_names_female)
            
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
        
        # Underwriters (5 underwriters)
        underwriters = []
        for i in range(1, 6):
            gender = random.choice(['Male', 'Female'])
            if gender == 'Male':
                first_name = random.choice(nigerian_first_names_male)
            else:
                first_name = random.choice(nigerian_first_names_female)
            
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
        
        # Store credentials for display (first 10 customers only)
        self.credentials = {
            'Admin': {'email': 'admin@vehicleinsure.ng', 'password': 'Admin@123456', 'role': 'Admin'},
        }
        
        for i, support in enumerate(support_users[:3], 1):
            self.credentials[f'Support {i}'] = {
                'email': support.email,
                'password': 'Support@123456',
                'role': 'Support'
            }
        
        for i, agent in enumerate(agents[:3], 1):
            self.credentials[f'Agent {i}'] = {
                'email': agent.email,
                'password': 'Agent@123456',
                'role': 'Agent'
            }
        
        for i, customer in enumerate(customers[:10], 1):
            self.credentials[f'Customer {i}'] = {
                'email': customer.email,
                'password': f'Customer@{i}23',
                'role': 'Customer'
            }

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
        
        makes = ['Toyota', 'Honda', 'Ford', 'Hyundai', 'Kia', 'Nissan', 'Mercedes', 'BMW', 'Lexus', 'Mazda', 
                 'Volkswagen', 'Subaru', 'Mitsubishi', 'Chevrolet', 'Hyundai', 'Kia', 'Suzuki', 'Peugeot']
        models = ['Camry', 'Corolla', 'Civic', 'Accord', 'Fusion', 'Elantra', 'Sonata', 'Optima', 'Altima', '3 Series',
                  'Golf', 'Passat', 'Outback', 'Forester', 'Lancer', 'Cruze', 'Rio', 'Cerato', 'Swift']
        
        for customer in customers:
            # Create 1-2 vehicles per customer
            for _ in range(random.randint(1, 2)):
                Vehicle.objects.create(
                    user=customer,
                    registration_number=f"{fake.license_plate()}-{uuid.uuid4().hex[:4].upper()}",
                    engine_number=f"ENG-{uuid.uuid4().hex[:8].upper()}",
                    chassis_number=f"CHS-{uuid.uuid4().hex[:8].upper()}",
                    vehicle_type=random.choice(['car', 'motorcycle', 'truck', 'bus']),
                    make=random.choice(makes),
                    model=random.choice(models),
                    year=random.randint(2015, 2025),
                    fuel_type=random.choice(['petrol', 'diesel', 'electric', 'hybrid']),
                    engine_capacity=random.randint(1000, 3500),
                    color=random.choice(['Black', 'White', 'Silver', 'Blue', 'Red', 'Gray', 'Green', 'Brown']),
                    ownership_type=random.choice(['single', 'joint', 'corporate']),
                    current_mileage=random.randint(1000, 150000),
                    is_insured=random.choice([True, False])
                )
        
        self.stdout.write(f'✅ Created {Vehicle.objects.count()} vehicles')

    def create_policies(self):
        self.stdout.write('Creating insurance policies...')
        vehicles = Vehicle.objects.all()
        
        policy_types = ['comprehensive', 'third_party', 'standalone', 'personal_accident']
        statuses = ['active', 'expired', 'pending']
        
        for vehicle in vehicles:
            start_date = timezone.now().date() - timedelta(days=random.randint(0, 365))
            end_date = start_date + timedelta(days=365)
            
            InsurancePolicy.objects.create(
                policy_number=f"POL-{uuid.uuid4().hex[:8].upper()}",
                user=vehicle.user,
                vehicle=vehicle,
                policy_type=random.choice(policy_types),
                status=random.choice(statuses),
                coverage_amount=Decimal(random.randint(1000000, 10000000)),
                premium_amount=Decimal(random.randint(50000, 500000)),
                deductible=Decimal(random.randint(5000, 50000)),
                start_date=start_date,
                end_date=end_date,
                terms_accepted=True
            )
        
        self.stdout.write(f'✅ Created {InsurancePolicy.objects.count()} policies')

    def create_claims(self):
        self.stdout.write('Creating claims...')
        policies = InsurancePolicy.objects.filter(status='active')[:50]
        
        claim_types = ['accident', 'theft', 'natural_disaster', 'fire', 'vandalism', 'third_party']
        statuses = ['pending', 'under_review', 'approved', 'settled', 'rejected']
        
        for policy in policies:
            if random.choice([True, False]):  # 50% chance of claim
                Claim.objects.create(
                    claim_number=f"CLM-{uuid.uuid4().hex[:8].upper()}",
                    policy=policy,
                    user=policy.user,
                    claim_type=random.choice(claim_types),
                    status=random.choice(statuses),
                    incident_date=timezone.now() - timedelta(days=random.randint(1, 90)),
                    incident_location=fake.address()[:255],
                    incident_description=fake.text(max_nb_chars=200),
                    claimed_amount=Decimal(random.randint(100000, 2000000)),
                    approved_amount=Decimal(random.randint(50000, 1500000)) if random.choice([True, False]) else None
                )
        
        self.stdout.write(f'✅ Created {Claim.objects.count()} claims')

    def create_payments(self):
        self.stdout.write('Creating payments...')
        policies = InsurancePolicy.objects.all()
        
        payment_methods = ['card', 'bank_transfer', 'mobile_wallet', 'cash']
        statuses = ['completed', 'pending', 'failed', 'refunded']
        
        for policy in policies[:100]:
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
            except Exception as e:
                pass
        
        self.stdout.write(f'✅ Created {Payment.objects.count()} payments')

    def create_quotes(self):
        self.stdout.write('Creating insurance quotes...')
        customers = User.objects.filter(role='customer', email__contains='customer')
        
        coverage_types = ['basic', 'standard', 'premium', 'custom']
        
        for customer in customers[:40]:
            Vehicle.objects.create(
                user=customer,
                registration_number=f"QUOTE-{uuid.uuid4().hex[:8].upper()}",
                engine_number=f"ENG-{uuid.uuid4().hex[:8].upper()}",
                chassis_number=f"CHS-{uuid.uuid4().hex[:8].upper()}",
                vehicle_type=random.choice(['car', 'motorcycle', 'truck', 'bus']),
                make=random.choice(['Toyota', 'Honda', 'Hyundai', 'Kia']),
                model=random.choice(['Corolla', 'Civic', 'Elantra', 'Cerato']),
                year=random.randint(2018, 2024),
                fuel_type=random.choice(['petrol', 'diesel']),
                engine_capacity=random.randint(1300, 2500),
                color=random.choice(['White', 'Silver', 'Black']),
                ownership_type='single',
                current_mileage=random.randint(1000, 50000),
                is_insured=False
            )
        
        vehicles = Vehicle.objects.filter(registration_number__startswith='QUOTE')
        
        for vehicle in vehicles:
            InsuranceQuote.objects.create(
                user=vehicle.user,
                vehicle=vehicle,
                coverage_type=random.choice(coverage_types),
                status=random.choice(['pending', 'approved', 'expired']),
                base_premium=Decimal(random.randint(40000, 150000)),
                total_premium=Decimal(random.randint(50000, 250000)),
                coverage_amount=Decimal(random.randint(1000000, 7500000)),
                deductible=Decimal(random.randint(5000, 50000)),
                valid_until=timezone.now() + timedelta(days=30),
                coverage_details={
                    'collision': True,
                    'theft': True,
                    'liability': True,
                    'fire': random.choice([True, False]),
                    'flood': random.choice([True, False])
                }
            )
        
        self.stdout.write(f'✅ Created {InsuranceQuote.objects.count()} quotes')

    def create_notifications(self):
        self.stdout.write('Creating notifications...')
        customers = User.objects.filter(role='customer', email__contains='customer')[:40]
        
        notification_types = ['claim_update', 'policy_expiry', 'payment_confirmation', 'quote_generated', 'system_alert']
        titles = [
            'Policy Renewal Reminder', 'Claim Status Update', 'Payment Received',
            'New Quote Available', 'Document Ready', 'Policy Expiring Soon',
            'Welcome to VehicleInsure', 'Your Policy is Active', 'Claim Approved'
        ]
        
        for customer in customers:
            for _ in range(random.randint(2, 8)):
                Notification.objects.create(
                    user=customer,
                    title=random.choice(titles),
                    message=fake.text(max_nb_chars=150),
                    notification_type=random.choice(notification_types),
                    is_read=random.choice([True, False])
                )
        
        self.stdout.write(f'✅ Created {Notification.objects.count()} notifications')

    def create_documents(self):
        self.stdout.write('Creating documents...')
        customers = User.objects.filter(role='customer', email__contains='customer')[:40]
        
        doc_types = ['driving_license', 'rc', 'other']
        verification_statuses = ['pending', 'verified', 'rejected']
        doc_names = ["Driver's License", 'Vehicle Registration', 'Identification Card', 'Proof of Address']
        
        for customer in customers:
            for _ in range(random.randint(1, 3)):
                Document.objects.create(
                    user=customer,
                    name=random.choice(doc_names),
                    document_type=random.choice(doc_types),
                    document_number=f"DOC-{uuid.uuid4().hex[:8].upper()}",
                    is_verified=random.choice([True, False]),
                    verification_status=random.choice(verification_statuses)
                )
        
        self.stdout.write(f'✅ Created {Document.objects.count()} documents')

    def create_support_tickets(self):
        self.stdout.write('Creating support tickets...')
        customers = User.objects.filter(role='customer', email__contains='customer')[:30]
        support_staff = User.objects.filter(role='support')
        
        priorities = ['low', 'medium', 'high', 'urgent']
        statuses = ['open', 'in_progress', 'resolved', 'closed']
        subjects = [
            'Login Issue', 'Payment Failed', 'Claim Processing', 'Policy Question',
            'Document Upload Problem', 'Wrong Premium Calculation', 'Need Assistance',
            'Update Personal Information', 'Vehicle Addition Request'
        ]
        
        for customer in customers:
            if random.choice([True, False]):
                ticket = SupportTicket.objects.create(
                    ticket_number=f"TKT-{uuid.uuid4().hex[:8].upper()}",
                    user=customer,
                    subject=random.choice(subjects),
                    message=fake.text(max_nb_chars=250),
                    priority=random.choice(priorities),
                    status=random.choice(statuses),
                    assigned_to=random.choice(support_staff) if support_staff.exists() else None
                )
                
                if random.choice([True, False]) and support_staff.exists():
                    TicketReply.objects.create(
                        ticket=ticket,
                        user=random.choice(support_staff),
                        message=fake.text(max_nb_chars=150)
                    )
        
        self.stdout.write(f'✅ Created {SupportTicket.objects.count()} tickets')

    def create_promocodes(self):
        self.stdout.write('Creating promo codes...')
        admin = User.objects.filter(role='admin').first()
        
        promos = [
            {'code': 'WELCOME20', 'discount_value': 20, 'discount_type': 'percentage', 'description': 'Welcome discount for new customers'},
            {'code': 'SAVE15', 'discount_value': 15, 'discount_type': 'percentage', 'description': '15% off on all policies'},
            {'code': 'FLAT5000', 'discount_value': 5000, 'discount_type': 'fixed', 'description': 'Flat ₦5000 off'},
            {'code': 'RENEW10', 'discount_value': 10, 'discount_type': 'percentage', 'description': '10% off on renewals'},
            {'code': 'FESTIVE25', 'discount_value': 25, 'discount_type': 'percentage', 'description': 'Festive season discount'},
            {'code': 'FIRSTCAR', 'discount_value': 15, 'discount_type': 'percentage', 'description': 'First vehicle discount'},
            {'code': 'LOYALTY', 'discount_value': 20, 'discount_type': 'percentage', 'description': 'Loyalty discount'},
            {'code': 'FLAT10000', 'discount_value': 10000, 'discount_type': 'fixed', 'description': 'Flat ₦10000 off on comprehensive'},
        ]
        
        for promo_data in promos:
            PromoCode.objects.get_or_create(
                code=promo_data['code'],
                defaults={
                    'discount_type': promo_data['discount_type'],
                    'discount_value': Decimal(promo_data['discount_value']),
                    'valid_from': timezone.now(),
                    'valid_to': timezone.now() + timedelta(days=90),
                    'max_uses': random.randint(50, 200),
                    'is_active': True,
                    'description': promo_data['description'],
                    'created_by': admin
                }
            )
        
        self.stdout.write(f'✅ Created {PromoCode.objects.count()} promo codes')

    def create_blog_content(self):
        self.stdout.write('Creating blog content...')
        
        # Categories
        categories = []
        cat_names = ['Insurance Tips', 'Car Maintenance', 'Safety', 'Industry News', 'Claims Guide', 'Vehicle Reviews', 'Road Safety']
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
        tag_names = ['Insurance', 'Vehicle', 'Safety', 'Tips', 'Claims', 'Renewal', 'Discount', 
                     'Car Care', 'Driving', 'Accident', 'Prevention', 'Coverage']
        for name in tag_names:
            tag, created = BlogTag.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name)}
            )
            tags.append(tag)
        
        # Posts
        users = User.objects.all()
        for i in range(15):
            post = BlogPost.objects.create(
                title=fake.sentence(nb_words=8)[:300],
                slug=f"blog-post-{i+1}-{uuid.uuid4().hex[:4]}",
                category=random.choice(categories),
                excerpt=fake.text(max_nb_chars=200),
                content=f"<p>{fake.text(max_nb_chars=800)}</p><p>{fake.text(max_nb_chars=800)}</p><p>{fake.text(max_nb_chars=500)}</p>",
                status='published',
                author=random.choice(users) if users.exists() else None,
                published_at=timezone.now() - timedelta(days=random.randint(1, 120)),
                is_featured=random.choice([True, False])
            )
            post.tags.add(*random.sample(tags, k=min(random.randint(2, 4), len(tags))))
            
            # Add comments
            for _ in range(random.randint(1, 5)):
                BlogComment.objects.create(
                    post=post,
                    name=fake.name()[:100],
                    email=fake.email(),
                    content=fake.text(max_nb_chars=120),
                    is_approved=random.choice([True, False])
                )
        
        self.stdout.write(f'✅ Created {BlogPost.objects.count()} blog posts with {BlogComment.objects.count()} comments')

    def create_newsletter_subscribers(self):
        self.stdout.write('Creating newsletter subscribers...')
        for i in range(30):
            NewsletterSubscriber.objects.get_or_create(
                email=fake.email(),
                defaults={
                    'name': fake.name()[:100],
                    'is_active': True,
                    'is_confirmed': True,
                    'source': random.choice(['website', 'blog', 'checkout', 'footer'])
                }
            )
        self.stdout.write(f'✅ Created {NewsletterSubscriber.objects.count()} subscribers')

    def create_press_content(self):
        self.stdout.write('Creating press releases...')
        
        # Categories
        press_cats = ['Product Launch', 'Company News', 'Awards', 'Partnership', 'Expansion', 'Milestone']
        categories = []
        for name in press_cats:
            cat, created = PressCategory.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name)}
            )
            categories.append(cat)
        
        # Press releases
        users = User.objects.filter(role='admin').first()
        for i in range(10):
            PressRelease.objects.create(
                title=fake.sentence(nb_words=10)[:300],
                slug=f"press-release-{i+1}-{uuid.uuid4().hex[:4]}",
                category=random.choice(categories),
                excerpt=fake.text(max_nb_chars=200),
                content=f"<p>{fake.text(max_nb_chars=600)}</p><p>{fake.text(max_nb_chars=600)}</p>",
                status='published',
                author=users,
                published_at=timezone.now() - timedelta(days=random.randint(1, 180)),
                location=random.choice(['Lagos', 'Abuja', 'Port Harcourt', 'International'])
            )
        
        # Media coverage
        publications = ['TechCrunch', 'AutoNews', 'Business Insider', 'Pulse', 'Guardian', 'Vanguard', 
                       'Punch', 'ThisDay', 'Channels TV', 'Arise TV', 'Bloomberg', 'Reuters']
        for i in range(15):
            MediaCoverage.objects.create(
                title=fake.sentence(nb_words=8)[:300],
                publication=random.choice(publications)[:200],
                url=fake.url()[:500],
                excerpt=fake.text(max_nb_chars=150),
                coverage_date=timezone.now().date() - timedelta(days=random.randint(1, 120)),
                is_active=True,
                featured=random.choice([True, False])
            )
        
        self.stdout.write(f'✅ Created press content')

    def create_job_postings(self):
        self.stdout.write('Creating job postings...')
        
        # Categories
        job_cats = ['Engineering', 'Sales', 'Marketing', 'Customer Support', 'Operations', 
                    'Finance', 'HR', 'Legal', 'Product', 'Data Science']
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
            ('Port Harcourt', 'Port Harcourt', 'Rivers'),
            ('Ibadan Office', 'Ibadan', 'Oyo'),
            ('Kano Office', 'Kano', 'Kano'),
            ('Enugu Office', 'Enugu', 'Enugu')
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
        job_types = ['Full-time', 'Part-time', 'Contract', 'Remote', 'Hybrid', 'Internship']
        types = []
        for name in job_types:
            jt, created = JobType.objects.get_or_create(
                name=name,
                defaults={'slug': slugify(name)}
            )
            types.append(jt)
        
        # Job postings
        users = User.objects.filter(role='admin').first()
        job_titles = [
            'Software Engineer', 'Sales Executive', 'Marketing Manager', 'Customer Support Agent',
            'Insurance Underwriter', 'Claims Adjuster', 'Data Analyst', 'Product Manager',
            'UI/UX Designer', 'DevOps Engineer', 'Financial Analyst', 'HR Generalist',
            'Legal Counsel', 'Risk Analyst', 'Business Development Manager'
        ]
        
        for i in range(15):
            JobPosting.objects.create(
                title=random.choice(job_titles),
                slug=f"job-{i+1}-{uuid.uuid4().hex[:4]}",
                category=random.choice(categories),
                location=random.choice(locations),
                job_type=random.choice(types),
                short_description=fake.text(max_nb_chars=200),
                description=f"<p>{fake.text(max_nb_chars=600)}</p><h3>Requirements</h3><p>{fake.text(max_nb_chars=400)}</p>",
                requirements=f"<ul><li>{fake.text(max_nb_chars=100)}</li><li>{fake.text(max_nb_chars=100)}</li><li>{fake.text(max_nb_chars=100)}</li></ul>",
                responsibilities=f"<ul><li>{fake.text(max_nb_chars=100)}</li><li>{fake.text(max_nb_chars=100)}</li><li>{fake.text(max_nb_chars=100)}</li></ul>",
                experience_level=random.choice(['entry', 'mid', 'senior', 'lead', 'executive']),
                salary_min=Decimal(random.randint(100000, 500000)),
                salary_max=Decimal(random.randint(600000, 2000000)),
                application_email='careers@vehicleinsure.ng',
                status='published',
                is_active=True,
                created_by=users,
                published_at=timezone.now() - timedelta(days=random.randint(1, 45))
            )
        
        self.stdout.write(f'✅ Created {JobPosting.objects.count()} job postings')

    def create_contact_inquiries(self):
        self.stdout.write('Creating contact inquiries...')
        
        inquiry_types = ['general', 'quote', 'claim', 'policy', 'complaint', 'partnership', 'feedback', 'support']
        
        for i in range(25):
            ContactInquiry.objects.create(
                full_name=fake.name()[:200],
                email=fake.email(),
                phone=fake.phone_number()[:20],
                inquiry_type=random.choice(inquiry_types),
                subject=fake.sentence(nb_words=6)[:300],
                message=fake.text(max_nb_chars=300),
                status=random.choice(['pending', 'in_progress', 'resolved', 'closed']),
                priority=random.choice(['low', 'medium', 'high', 'urgent']),
                ip_address=fake.ipv4(),
                user_agent=fake.user_agent()
            )
        
        self.stdout.write(f'✅ Created {ContactInquiry.objects.count()} inquiries')

    def create_office_locations(self):
        self.stdout.write('Creating office locations...')
        
        offices = [
            {'name': 'Lagos Headquarters', 'city': 'Lagos', 'state': 'Lagos', 'is_headquarters': True, 'lat': 6.5244, 'lng': 3.3792},
            {'name': 'Abuja Regional Office', 'city': 'Abuja', 'state': 'FCT', 'is_headquarters': False, 'lat': 9.0579, 'lng': 7.4951},
            {'name': 'Port Harcourt Branch', 'city': 'Port Harcourt', 'state': 'Rivers', 'is_headquarters': False, 'lat': 4.8156, 'lng': 7.0498},
            {'name': 'Ibadan Office', 'city': 'Ibadan', 'state': 'Oyo', 'is_headquarters': False, 'lat': 7.3775, 'lng': 3.9470},
            {'name': 'Kano Office', 'city': 'Kano', 'state': 'Kano', 'is_headquarters': False, 'lat': 12.0022, 'lng': 8.5917},
            {'name': 'Enugu Office', 'city': 'Enugu', 'state': 'Enugu', 'is_headquarters': False, 'lat': 6.4567, 'lng': 7.5465},
            {'name': 'Benin City Branch', 'city': 'Benin City', 'state': 'Edo', 'is_headquarters': False, 'lat': 6.3176, 'lng': 5.6145},
            {'name': 'Jos Office', 'city': 'Jos', 'state': 'Plateau', 'is_headquarters': False, 'lat': 9.8965, 'lng': 8.8583},
        ]
        
        for office_data in offices:
            OfficeLocation.objects.get_or_create(
                name=office_data['name'],
                defaults={
                    'slug': slugify(office_data['name']),
                    'address': f"Plot {random.randint(1, 50)} {office_data['name']} Road, {office_data['city']}",
                    'city': office_data['city'],
                    'state': office_data['state'],
                    'country': 'NG',
                    'phone': f"+234 800 123 {random.randint(1000, 9999)}",
                    'email': f"info@{office_data['name'].replace(' ', '').lower()}.com",
                    'working_hours': "Mon-Fri: 9AM - 6PM, Sat: 10AM - 2PM",
                    'is_headquarters': office_data['is_headquarters'],
                    'is_active': True,
                    'latitude': office_data.get('lat'),
                    'longitude': office_data.get('lng')
                }
            )
        
        self.stdout.write(f'✅ Created {OfficeLocation.objects.count()} office locations')

    def create_document_categories(self):
        self.stdout.write('Creating document categories...')
        
        doc_cats = [
            {'name': 'Policies', 'icon': 'fa-file-contract', 'color': '#4169E1'},
            {'name': 'Claims', 'icon': 'fa-file-invoice', 'color': '#DC2626'},
            {'name': 'Receipts', 'icon': 'fa-receipt', 'color': '#10B981'},
            {'name': 'Certificates', 'icon': 'fa-certificate', 'color': '#F59E0B'},
            {'name': 'Legal', 'icon': 'fa-gavel', 'color': '#8B5CF6'},
            {'name': 'KYC Documents', 'icon': 'fa-id-card', 'color': '#6366F1'},
            {'name': 'Vehicle Papers', 'icon': 'fa-car', 'color': '#14B8A6'},
        ]
        
        for cat_data in doc_cats:
            DocumentCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'slug': slugify(cat_data['name']),
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'is_active': True
                }
            )
        
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
        self.stdout.write(f'  • Blog Posts: {BlogPost.objects.count()}')
        self.stdout.write(f'  • Job Postings: {JobPosting.objects.count()}')
        self.stdout.write('='*70)