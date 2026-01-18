from django.contrib import admin
from .models import (
    Client, Lead, Meeting, Sale, BusinessDevelopmentManager,
    Redemption, AppraisalPeriod, AppraisalQuestion, EmployeeAssignment,
    AppraisalReview, AppraisalAnswer
)
import pandas as pd
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Client

admin.site.site_header = "Samarth Wealth Pvt Ltd CRM"
admin.site.site_title = "Samarth Wealth Pvt Ltd CRM"
admin.site.index_title = "Welcome to CRM"

@admin.register(BusinessDevelopmentManager)
class BDMAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'joining_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'department')
    list_filter = ('department', 'joining_date')
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'relationship_manager')
    actions = ['import_clients']

    def import_clients(self, request, queryset):
        """Admin action to import clients from CSV or Excel."""
        if 'file' in request.FILES:
            file = request.FILES['file']
            try:
                # Determine file type and read the data
                data = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)

                # Ensure required columns exist
                required_columns = ['Name', 'Email', 'Phone', 'Relationship Manager Email']
                for col in required_columns:
                    if col not in data.columns:
                        self.message_user(request, f"Missing column: {col}", level=messages.ERROR)
                        return

                # Iterate and create Client objects
                for _, row in data.iterrows():
                    manager_email = row['Relationship Manager Email']
                    manager = User.objects.filter(email=manager_email).first()

                    Client.objects.create(
                        name=row['Name'],
                        email=row['Email'],
                        phone=row['Phone'],
                        relationship_manager=manager
                    )

                self.message_user(request, "Clients imported successfully!", level=messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Error: {e}", level=messages.ERROR)
        else:
            self.message_user(request, "No file uploaded.", level=messages.ERROR)

    import_clients.short_description = "Import clients from CSV/Excel"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('client', 'lead_info', 'created_at')
    search_fields = ('client__name', 'lead_info')
    list_filter = ('created_at',)

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('client', 'relationship_manager', 'date', 'notes')
    search_fields = ('client__name', 'relationship_manager__username')
    list_filter = ('date',)

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('client', 'product', 'amount', 'sale_date')
    search_fields = ('client__name', 'product')
    list_filter = ('product', 'sale_date')


# Redemption Admin
@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ('client', 'product', 'redemption_type', 'amount', 'redemption_date', 'relationship_manager')
    search_fields = ('client__name', 'fund_name')
    list_filter = ('product', 'redemption_type', 'redemption_date')
    date_hierarchy = 'redemption_date'


# 360-Degree Appraisal Admin Classes
@admin.register(AppraisalPeriod)
class AppraisalPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(AppraisalQuestion)
class AppraisalQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'question_type', 'is_active', 'order')
    list_filter = ('question_type', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('question_text',)


@admin.register(EmployeeAssignment)
class EmployeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'manager', 'employee_type', 'updated_at')
    list_filter = ('employee_type',)
    search_fields = ('employee__first_name', 'employee__last_name', 'manager__first_name', 'manager__last_name')
    autocomplete_fields = ['employee', 'manager']


class AppraisalAnswerInline(admin.TabularInline):
    model = AppraisalAnswer
    extra = 0
    readonly_fields = ('question', 'answer_text', 'rating')


@admin.register(AppraisalReview)
class AppraisalReviewAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period', 'manager', 'status', 'self_overall_rating', 'manager_rating', 'final_rating')
    list_filter = ('status', 'period')
    search_fields = ('employee__first_name', 'employee__last_name')
    inlines = [AppraisalAnswerInline]
    readonly_fields = ('created_at', 'updated_at', 'self_submitted_at', 'manager_reviewed_at', 'completed_at')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('period', 'employee', 'manager', 'status')
        }),
        ('Self Assessment', {
            'fields': ('self_overall_rating', 'self_comments', 'self_submitted_at')
        }),
        ('Employee Rating for Manager', {
            'fields': ('manager_rating_by_employee', 'manager_comments_by_employee'),
            'description': 'This rating is hidden from the manager and only visible to admin.'
        }),
        ('Manager Assessment', {
            'fields': ('manager_rating', 'manager_comments', 'manager_reviewed_at')
        }),
        ('Final Assessment', {
            'fields': ('final_rating', 'final_comments', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
