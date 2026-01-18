from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from .views import upload_clients, crm_dashboard


urlpatterns = [
    path('home/', views.home, name='home'),
    path('', LoginView.as_view(
        template_name='login.html',
        redirect_authenticated_user=True,
        next_page='home'
    ), name='login'),
    
    # Password Change URLs
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='crm/password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='crm/password_change_done.html'), name='password_change_done'),

    path('dashboard/', views.crm_dashboard, name='crm_dashboard'),
    path('logout/', views.custom_logout_view, name='logout'),


    #client
    path('clients/', views.client_list, name='client_list'),
    path('clients/<int:client_id>/add_meeting/', views.add_meeting, name='add_meeting'),
    path('clients/<int:client_id>/add_sales/', views.add_sale, name='add_sales'),
    path('clients/update/<int:client_id>/', views.update_client, name='update_client'),
    path('upload-clients/', upload_clients, name='upload_clients'),
    path('success/', views.success_page, name='success_page'),
    path('add-client/', views.add_client, name='add_client'),
    path('bulk-rm-transfer/', views.bulk_rm_transfer, name='bulk_rm_transfer'),
    path('clients/export/', views.export_clients_csv, name='export_clients_csv'),
    path('client/<int:client_id>/delete/', views.delete_client, name='delete_client'),

    #Meeting
    path('meetings/', views.meetings_list, name='meetings_list'),
    path('meetings/<int:client_id>/', views.meetings_list, name='meetings_list'),
    path('meetings/<int:client_id>/add/', views.add_meeting, name='add_meeting'),
    path('meetings/<int:meeting_id>/update/', views.update_meeting, name='update_meeting'),
    path('meetings/<int:meeting_id>/delete/', views.delete_meeting, name='delete_meeting'),
    path('export-meetings/', views.export_meetings_to_excel, name='export_meetings'),
    path('upload-meetings/', views.upload_meetings, name='upload_meetings'),

    #sales
    path('sales/', views.sales_list, name='sales_list'),
    path('export-sales/', views.export_sales_to_excel, name='export_sales'),
    path('sale/update/<int:sale_id>/', views.update_sale, name='update_sale'),
    path('sale/delete/<int:sale_id>/', views.delete_sale, name='delete_sale'),
    path('upload-sales/', views.upload_sales, name='upload_sales'),

# NEW CALL MANAGEMENT URLs - Add these
    path('calls/', views.calls_list, name='calls_list'),
    path('calls/add/<int:client_id>/', views.add_call, name='add_call'),
    path('calls/<int:call_id>/', views.call_detail, name='call_detail'),
    path('calls/<int:call_id>/update/', views.update_call, name='update_call'),
    path('calls/<int:call_id>/delete/', views.delete_call, name='delete_call'),
    path('calls/client/<int:client_id>/', views.client_calls, name='client_calls'),
    path('calls/analytics/', views.calls_analytics, name='calls_analytics'),
    path('calls/export/', views.export_calls_csv, name='export_calls_csv'),
    path('calls/upload/', views.upload_calls, name='upload_calls'),

    # add lead
    path('add-lead/', views.add_lead, name='add_lead'),
    path('leads/', views.leads_list, name='leads_list'),
    path('leads/edit/<int:pk>/', views.edit_lead, name='edit_lead'),
    path('leads/delete/<int:lead_id>/', views.delete_lead, name='delete_lead'),
    path('leads/export/', views.leads_export, name='leads_export'),
    path('leads/upload/', views.bulk_leads_upload, name='bulk_leads_upload'),
    path('leads/transfer/<int:lead_id>/', views.transfer_lead_to_client, name='transfer_lead_to_client'),

# RM Performance Dashboard
    path('rm-performance/<int:rm_id>/', views.rm_performance, name='rm_performance'),
    
    # BDM Performance Dashboard
    path('bdm-performance/<int:bdm_id>/', views.bdm_performance, name='bdm_performance'),

    # Redemptions
    path('redemptions/', views.redemptions_list, name='redemptions_list'),
    path('redemptions/add/<int:client_id>/', views.add_redemption, name='add_redemption'),
    path('redemptions/update/<int:redemption_id>/', views.update_redemption, name='update_redemption'),
    path('redemptions/delete/<int:redemption_id>/', views.delete_redemption, name='delete_redemption'),

    # 360-Degree Appraisal System
    path('appraisal/', views.appraisal_list, name='appraisal_list'),
    path('appraisal/self/<int:period_id>/', views.appraisal_self_review, name='appraisal_self_review'),
    path('appraisal/manager/<int:review_id>/', views.appraisal_manager_review, name='appraisal_manager_review'),
    path('appraisal/admin/', views.appraisal_admin_view, name='appraisal_admin_view'),
    path('appraisal/admin/finalize/<int:review_id>/', views.appraisal_admin_finalize, name='appraisal_admin_finalize'),
    path('appraisal/final/<int:review_id>/', views.appraisal_employee_final, name='appraisal_employee_final'),
    path('backup-db/', views.download_db, name='download_db'),
]



