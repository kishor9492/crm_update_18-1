from django.contrib import admin
from .models import Client, Lead, Meeting, Sale, BusinessDevelopmentManager
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
