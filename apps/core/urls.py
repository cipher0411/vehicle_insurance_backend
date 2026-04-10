from django.urls import path, re_path
from django.contrib.auth import views as auth_views
from . import views
from . import admin_views
from . import staff_views


app_name = 'core'

urlpatterns = [
    # Public URLs
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    # Password Reset URLs
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),  
    path('password-reset/done/',  views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'), 
    path('password-reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'), 
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('public_promotions/', views.public_promotions, name='public_promotions'),
    path('about/', views.about, name='about'),
    path('motor-insurance/', views.motor_insurance, name='motor_insurance'),
    path('instant-quote/', views.instant_quote, name='instant_quote'),
    path('policies/', views.policies, name='policies'),
    path('digital-documents/', views.digital_documents, name='digital_documents'),
    path('renew-policy/', views.renew_policy, name='renew_policy'),
    path('file-claim/', views.file_claim, name='file_claim'),
    path('track-claims/', views.track_claims, name='track_claims'),
    path('secure-payments/', views.secure_payments, name='secure_payments'),
    path('individual-plans/', views.individual_plans, name='individual_plans'),
    path('premium-calculator/', views.premium_calculator, name='premium_calculator'),
    path('easy-renewals/', views.easy_renewals, name='easy_renewals'),
    path('fleet-insurance/', views.fleet_insurance, name='fleet_insurance'),
    path('commercial-coverage/', views.commercial_coverage, name='commercial_coverage'),
    path('claims-management/', views.claims_management, name='claims_management'),
    path('solutions/', views.solutions, name='solutions'),
    path('support/', views.support, name='support'),
    path('faqs/', views.faqs, name='faqs'),
    path('contact/', views.contact, name='contact'),
    path('claims-support/', views.claims_support, name='claims_support'),
    path('careers/', views.careers, name='careers'),
    path('blog/', views.blog, name='blog'),
    path('press/', views.press, name='press'),
    path('terms/', views.terms, name='terms'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('cookie-policy/', views.cookie_policy, name='cookie_policy'),
    path('cookie-settings/', views.cookie_settings, name='cookie_settings'),
    path('licenses/', views.licenses, name='licenses'),
    path('public-promotions/', views.public_promotions, name='public_promotions'),
       
    path('blog/', views.blog, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('blog/category/<slug:category_slug>/', views.blog_by_category, name='blog_category'),
    path('blog/tag/<slug:tag_slug>/', views.blog_by_tag, name='blog_tag'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
        
    # Public Press URLs
    path('press/', views.press, name='press'),
    path('press/<slug:slug>/', views.press_detail, name='press_detail'),
    path('press/category/<slug:category_slug>/', views.press, name='press_category'),
    path('media-kit/<uuid:kit_id>/download/', views.media_kit_download, name='media_kit_download'),
    
    # Customer URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('vehicles/', views.vehicles, name='vehicles'),
    path('vehicles/edit/<uuid:vehicle_id>/', views.edit_vehicle, name='edit_vehicle'),
    path('vehicles/delete/<uuid:vehicle_id>/', views.delete_vehicle, name='delete_vehicle'),
    path('get-quote/', views.get_quote, name='get_quote'),
    path('validate-promo/', views.validate_promo_code, name='validate_promo_code'),
    path('promotions/', views.promotions, name='promotions'),
    path('purchase-policy/', views.purchase_policy, name='purchase_policy'),
    path('purchase-policy/<uuid:quote_id>/', views.purchase_policy, name='purchase_policy_quote'),
    path('my-policies/', views.my_policies, name='my_policies'),
    path('policy/<uuid:policy_id>/', views.policy_detail, name='policy_detail'),
    path('file-claim/', views.file_claim, name='file_claim'),
    path('file-claim/<uuid:policy_id>/', views.file_claim, name='file_claim_policy'),
    path('my-claims/', views.my_claims, name='my_claims'),
    path('claim/<uuid:claim_id>/', views.claim_detail, name='claim_detail'),
    path('payment/<uuid:payment_id>/', views.payment_page, name='payment'),
    path('payment/<uuid:payment_id>/card/', views.process_card_payment, name='process_card_payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('payment/<uuid:payment_id>/verify/', views.verify_payment, name='verify_payment'),
    path('payment/<uuid:payment_id>/bank-transfer/', views.bank_transfer_instructions, name='bank_transfer_instructions'),
    path('payment/<uuid:payment_id>/confirm-transfer/', views.confirm_bank_transfer, name='confirm_bank_transfer'),
    path('payment/<uuid:payment_id>/status/', views.payment_status, name='payment_status'),
    path('profile/', views.profile, name='profile'),
    path('profile/upload-kyc/', views.upload_kyc, name='upload_kyc'),
    path('change-password/', views.change_password, name='change_password'),
    path('support-tickets/', views.support_tickets, name='support_tickets'),
    path('ticket/<uuid:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<uuid:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Staff URLs
    path('staff/dashboard/', staff_views.staff_dashboard, name='staff_dashboard'),
    path('staff/claims/', staff_views.staff_claims, name='staff_claims'),
    path('staff/claim/<uuid:claim_id>/', staff_views.staff_claim_detail, name='staff_claim_detail'),
    path('staff/policies/', staff_views.staff_policies, name='staff_policies'),
    path('staff/policy/<uuid:policy_id>/', staff_views.staff_policy_detail, name='staff_policy_detail'),
    path('staff/tickets/', staff_views.staff_tickets, name='staff_tickets'),
    path('staff/tickets/<uuid:ticket_id>/assign/', staff_views.staff_assign_ticket, name='staff_assign_ticket'),
    path('staff/tickets/<uuid:ticket_id>/start/', staff_views.staff_start_ticket, name='staff_start_ticket'),
    path('staff/ticket/<uuid:ticket_id>/', staff_views.staff_ticket_detail, name='staff_ticket_detail'),
    path('staff/customers/', staff_views.staff_customers, name='staff_customers'),
    path('staff/customer/<uuid:user_id>/', staff_views.staff_customer_detail, name='staff_customer_detail'),
    # Staff Blog Management URLs
    path('staff/blog/', views.blog_manage, name='blog_manage'),
    path('staff/blog/create/', views.blog_create, name='blog_create'),
    path('staff/blog/<uuid:post_id>/edit/', views.blog_edit, name='blog_edit'),
    path('staff/blog/<uuid:post_id>/delete/', views.blog_delete, name='blog_delete'),
    path('staff/blog/preview/', views.blog_preview, name='blog_preview'),
    # Staff Category Management
    path('staff/blog/categories/', views.blog_categories_manage, name='blog_categories_manage'),
    path('staff/blog/categories/<uuid:category_id>/edit/', views.blog_category_edit, name='blog_category_edit'),
    path('staff/blog/categories/<uuid:category_id>/delete/', views.blog_category_delete, name='blog_category_delete'),   
    # Staff Comments Management
    path('staff/blog/comments/', views.blog_comments_manage, name='blog_comments_manage'),
    path('staff/blog/comments/<uuid:comment_id>/approve/', views.blog_comment_approve, name='blog_comment_approve'),
    path('staff/blog/comments/<uuid:comment_id>/delete/', views.blog_comment_delete, name='blog_comment_delete'), 
    # Staff Newsletter Management
    path('staff/newsletter/subscribers/', views.newsletter_subscribers_manage, name='newsletter_subscribers_manage'),
    # Newsletter Subscriber Management
    path('staff/newsletter/subscribers/', views.newsletter_subscribers_manage, name='newsletter_subscribers_manage'),
    path('staff/newsletter/subscribers/export/', views.newsletter_subscribers_export, name='newsletter_subscribers_export'),
    path('staff/newsletter/unsubscribe/<uuid:subscriber_id>/', views.newsletter_unsubscribe, name='newsletter_unsubscribe'),
    path('staff/newsletter/resubscribe/<uuid:subscriber_id>/', views.newsletter_resubscribe, name='newsletter_resubscribe'),
    path('staff/newsletter/delete/<uuid:subscriber_id>/', views.newsletter_delete, name='newsletter_delete'),
    
    # Staff Press Management URLs
    path('staff/press/', views.press_manage, name='press_manage'),
    path('staff/press/create/', views.press_create, name='press_create'),
    path('staff/press/<uuid:release_id>/edit/', views.press_edit, name='press_edit'),
    path('staff/press/<uuid:release_id>/delete/', views.press_delete, name='press_delete'),
    
    # Staff Press Categories
    path('staff/press/categories/', views.press_categories_manage, name='press_categories_manage'),
    re_path(r'^staff/press/categories/(?P<category_id>[0-9a-f-]+)/edit/$', views.press_category_edit, name='press_category_edit'),
    re_path(r'^staff/press/categories/(?P<category_id>[0-9a-f-]+)/delete/$', views.press_category_delete, name='press_category_delete'),
    
    # Staff Media Coverage
    path('staff/media-coverage/', views.media_coverage_manage, name='media_coverage_manage'),
    path('staff/media-coverage/<uuid:coverage_id>/edit/', views.media_coverage_edit, name='media_coverage_edit'),
    path('staff/media-coverage/<uuid:coverage_id>/delete/', views.media_coverage_delete, name='media_coverage_delete'),
    
    # Staff Media Kit
    path('staff/media-kit/', views.media_kit_manage, name='media_kit_manage'),
    path('staff/media-kit/<uuid:kit_id>/edit/', views.media_kit_edit, name='media_kit_edit'),
    path('staff/media-kit/<uuid:kit_id>/delete/', views.media_kit_delete, name='media_kit_delete'),
    
    # Admin URLs
    path('custom_admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('custom_admin/users/', admin_views.admin_users, name='admin_users'),
    path('custom_admin/user/<uuid:user_id>/', admin_views.admin_user_detail, name='admin_user_detail'),
    path('custom_admin/user/<uuid:user_id>/verify/', admin_views.admin_verify_user, name='admin_verify_user'),
    path('custom_admin/user/<uuid:user_id>/suspend/', admin_views.admin_suspend_user, name='admin_suspend_user'),
    path('custom_admin/user/<uuid:user_id>/activate/', admin_views.admin_activate_user, name='admin_activate_user'),
    path('custom_admin/document/<uuid:doc_id>/verify/', admin_views.admin_verify_document, name='admin_verify_document'),
    path('custom_admin/policies/', admin_views.admin_policies, name='admin_policies'),
    path('custom_admin/policy/<uuid:policy_id>/', admin_views.admin_policy_detail, name='admin_policy_detail'),
    path('custom_admin/claims/', admin_views.admin_claims, name='admin_claims'),
    path('custom_admin/claim/<uuid:claim_id>/', admin_views.admin_claim_detail, name='admin_claim_detail'),
    path('custom_admin/payments/', admin_views.admin_payments, name='admin_payments'),
    path('custom_admin/payments/<uuid:payment_id>/mark-completed/', admin_views.admin_payment_action, name='admin_payment_mark_completed'),
    path('custom_admin/payments/<uuid:payment_id>/verify-transfer/', admin_views.admin_payment_action, name='admin_payment_verify_transfer'),
    path('custom_admin/payments/<uuid:payment_id>/mark-failed/', admin_views.admin_payment_action, name='admin_payment_mark_failed'),
    path('custom_admin/payments/<uuid:payment_id>/refund/', admin_views.admin_payment_action, name='admin_payment_refund'),
    path('custom_admin/promo-codes/', admin_views.admin_promo_codes, name='admin_promo_codes'),
    path('custom_admin/promo-codes/delete/<int:code_id>/', admin_views.admin_delete_promo_code, name='admin_delete_promo_code'),
    path('custom_admin/promo-codes/', admin_views.admin_promo_codes, name='admin_promo_codes'),
    path('custom_admin/promo-codes/edit/<int:code_id>/', admin_views.admin_edit_promo_code, name='admin_edit_promo_code'),
    path('custom_admin/promo-codes/toggle/<int:code_id>/', admin_views.admin_toggle_promo_code, name='admin_toggle_promo_code'),
    path('custom_admin/promo-codes/delete/<int:code_id>/', admin_views.admin_delete_promo_code, name='admin_delete_promo_code'),
    path('promotions/', views.promotions, name='promotions'),
    path('custom_admin/support-tickets/', admin_views.admin_support_tickets, name='admin_support_tickets'),
    path('custom_admin/support-tickets/assign/', admin_views.admin_bulk_assign_tickets, name='admin_bulk_assign_tickets'),
    path('custom_admin/support-tickets/bulk-update/', admin_views.admin_bulk_update_tickets, name='admin_bulk_update_tickets'),
    path('custom_admin/ticket/<uuid:ticket_id>/', admin_views.admin_ticket_detail, name='admin_ticket_detail'),
    path('custom_admin/reports/', admin_views.admin_reports, name='admin_reports'),
    path('custom_admin/export/', admin_views.admin_export_data, name='admin_export_data'),
    path('custom_admin/send-notification/', admin_views.admin_send_notification, name='admin_send_notification'),
    path('custom_admin/get-recipient-count/', admin_views.get_recipient_count, name='get_recipient_count'),
    path('custom_admin/insurance-settings/', admin_views.admin_insurance_settings, name='admin_insurance_settings'),
    # Admin Vehicles
    path('custom_admin/vehicles/', admin_views.admin_vehicles, name='admin_vehicles'),
    path('custom_admin/vehicle/<uuid:vehicle_id>/', admin_views.admin_vehicle_detail, name='admin_vehicle_detail'),
    path('custom_admin/vehicle/<uuid:vehicle_id>/<str:action>/', admin_views.admin_vehicle_action, name='admin_vehicle_action'),
    path('custom_admin/user/<uuid:user_id>/vehicles/', admin_views.admin_vehicles_by_user, name='admin_vehicles_by_user'),
    
    
    
    
    
    
    
    
    
    
    
    # Public Careers URLs
    path('careers/', views.careers, name='careers'),
    path('careers/<slug:slug>/', views.job_detail, name='job_detail'),
    path('careers/category/<slug:category_slug>/', views.careers, name='careers_category'),
    path('careers/location/<slug:location_slug>/', views.careers, name='careers_location'),
    
    # Staff Job Management URLs
    path('staff/jobs/', views.jobs_manage, name='jobs_manage'),
    path('staff/jobs/create/', views.job_create, name='job_create'),
    path('staff/jobs/<uuid:job_id>/edit/', views.job_edit, name='job_edit'),
    path('staff/jobs/<uuid:job_id>/delete/', views.job_delete, name='job_delete'),
    
    # Staff Job Categories
    path('staff/jobs/categories/', views.job_categories_manage, name='job_categories_manage'),
    re_path(r'^staff/jobs/categories/(?P<category_id>[0-9a-f-]+)/edit/$', views.job_category_edit, name='job_category_edit'),
    re_path(r'^staff/jobs/categories/(?P<category_id>[0-9a-f-]+)/delete/$', views.job_category_delete, name='job_category_delete'),
    
    # Staff Job Locations
    path('staff/jobs/locations/', views.job_locations_manage, name='job_locations_manage'),
    re_path(r'^staff/jobs/locations/(?P<location_id>[0-9a-f-]+)/edit/$', views.job_location_edit, name='job_location_edit'),
    re_path(r'^staff/jobs/locations/(?P<location_id>[0-9a-f-]+)/delete/$', views.job_location_delete, name='job_location_delete'),
    
    # Staff Job Types
    path('staff/jobs/types/', views.job_types_manage, name='job_types_manage'),
    re_path(r'^staff/jobs/types/(?P<type_id>[0-9a-f-]+)/edit/$', views.job_type_edit, name='job_type_edit'),
    re_path(r'^staff/jobs/types/(?P<type_id>[0-9a-f-]+)/delete/$', views.job_type_delete, name='job_type_delete'),
    
    # Staff Job Applications
    path('staff/jobs/applications/', views.job_applications_manage, name='job_applications_manage'),
    path('staff/jobs/applications/<uuid:application_id>/', views.job_application_detail, name='job_application_detail'),
    path('staff/jobs/applications/<uuid:application_id>/update/', views.job_application_status_update, name='job_application_status_update'),
    
    
    # User Public Document URLs
    path('digital-documents/', views.digital_documents, name='digital_documents'),
    path('digital-documents/<slug:slug>/', views.public_document_detail, name='public_document_detail'),
    path('digital-documents/<slug:slug>/download/', views.public_document_download, name='public_document_download'),
    path('digital-documents/<slug:slug>/verify/', views.public_document_verify, name='public_document_verify'),
    
    # Staff Document Management URLs
    path('staff/documents/', views.documents_manage, name='documents_manage'),
    path('staff/documents/create/', views.document_create, name='document_create'),
    path('staff/documents/bulk-upload/', views.document_bulk_upload, name='document_bulk_upload'),
    path('staff/documents/<uuid:document_id>/edit/', views.document_edit, name='document_edit'),
    path('staff/documents/<uuid:document_id>/delete/', views.document_delete, name='document_delete'),
    path('staff/documents/<uuid:document_id>/verify/', views.document_verify_toggle, name='document_verify_toggle'),
    
    # Staff Document Categories
    path('staff/documents/categories/', views.document_categories_manage, name='document_categories_manage'),
    path('staff/documents/categories/<int:category_id>/edit/', views.document_category_edit, name='document_category_edit'),
    path('staff/documents/categories/<int:category_id>/delete/', views.document_category_delete, name='document_category_delete'),
    
    # Contact Page
    path('contact/', views.contact, name='contact'),
    
    # Staff Inquiry Management
    path('staff/inquiries/', views.inquiries_manage, name='inquiries_manage'),
    path('staff/inquiries/<uuid:inquiry_id>/', views.inquiry_detail, name='inquiry_detail'),
    
    # Staff Office Management
    path('staff/offices/', views.offices_manage, name='offices_manage'),
    path('staff/offices/<int:office_id>/edit/', views.office_edit, name='office_edit'),
    path('staff/offices/<int:office_id>/delete/', views.office_delete, name='office_delete'),
    
    
    
    
]