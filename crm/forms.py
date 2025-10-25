from django import forms
from .models import Sale
from .models import Client, Call, Lead,BusinessDevelopmentManager
from .models import User
from django.contrib.auth.models import User
class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['product', 'amount', 'sale_date']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
        }

class FileUploadForm(forms.Form):
    file = forms.FileField()



class AddClientForm(forms.Form):
    name = forms.CharField(max_length=255, required=True, label="Client Name")
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=15, required=True, label="Phone")
    pan = forms.CharField(max_length=10, required=False, label="PAN")  # Optional field
    relationship_manager = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name="Relationship Managers"),
        required=False,
        label="Relationship Manager"
    )

    sourced_by = forms.ModelChoiceField(
        queryset=BusinessDevelopmentManager.objects.all(),
        required=False,
        label="Sourced By (BDM)",
        empty_label="Select Business Development Manager"
    )


class UpdateClientForm(forms.ModelForm):
    sourced_by = forms.ModelChoiceField(
        queryset=BusinessDevelopmentManager.objects.all(),
        required=False,
        label="Sourced By (BDM)",
        empty_label="Select Business Development Manager"
    )

    class Meta:
        model = Client
        fields = ['name', 'email', 'phone', 'pan', 'relationship_manager', 'sourced_by']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter client name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter email address'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Enter phone number'}),
            'pan': forms.TextInput(attrs={'placeholder': 'Enter PAN (optional)'}),
        }


class BulkRMTransferForm(forms.Form):
    old_rm = forms.ModelChoiceField(queryset=User.objects.filter(groups__name='Relationship Managers'), label="Old RM")
    new_rm = forms.ModelChoiceField(queryset=User.objects.filter(groups__name='Relationship Managers'), label="New RM")

class FileUploadForm(forms.Form):
    file = forms.FileField(label="Select file (CSV or XLSX)")


#call details

class AddCallForm(forms.ModelForm):
    class Meta:
        model = Call
        fields = [
            'call_type', 'call_status', 'call_purpose', 'phone_number',
            'call_start_time', 'call_end_time', 'duration_minutes',
            'connection_time_seconds', 'notes', 'follow_up_required', 'follow_up_date'
        ]
        widgets = {
            'call_type': forms.Select(attrs={'class': 'form-control'}),
            'call_status': forms.Select(attrs={'class': 'form-control'}),
            'call_purpose': forms.Select(attrs={'class': 'form-control'}),
            'call_start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'call_end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(
                attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Enter call conversation notes...'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
            'duration_minutes': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Duration in minutes'}),
            'connection_time_seconds': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Time to connect in seconds'}),
        }




class LeadForm(forms.Form):
    existing_client = forms.ModelChoiceField(
        queryset=Client.objects.all(),
        required=False,
        label="Select Existing Client",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    # New client info fields
    name = forms.CharField(
        max_length=255, required=False, label="Client Name",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False, label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    phone = forms.CharField(
        max_length=10, required=False, label="Phone",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    lead_info = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows':4}),
        label="Lead Information"
    )
    relationship_manager = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name="Relationship Managers"),
        required=False,
        label="Relationship Manager",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        existing_client = cleaned_data.get('existing_client')
        name = cleaned_data.get('name')
        email = cleaned_data.get('email')
        phone = cleaned_data.get('phone')
        # Add required field validation as before
        if not existing_client and (not name or not email or not phone):
            raise forms.ValidationError(
                "You must select an existing client or provide name, email, and phone for a new client."
            )
        return cleaned_data


class CallFilterForm(forms.Form):
    CALL_TYPE_CHOICES = [('', 'All Types')] + Call.CALL_TYPE_CHOICES
    CALL_STATUS_CHOICES = [('', 'All Status')] + Call.CALL_STATUS_CHOICES
    CALL_PURPOSE_CHOICES = [('', 'All Purposes')] + Call.CALL_PURPOSE_CHOICES

    relationship_manager = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Relationship Managers'),
        required=False,
        empty_label="All RMs",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'})
    )
    call_type = forms.ChoiceField(
        choices=CALL_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'})
    )
    call_status = forms.ChoiceField(
        choices=CALL_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'})
    )
    call_purpose = forms.ChoiceField(
        choices=CALL_PURPOSE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    client_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control form-control-sm', 'placeholder': 'Search by client name...'})
    )


class BulkCallUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.xlsx'})
    )

class BulkLeadUploadForm(forms.Form):
    file = forms.FileField(label="Upload CSV or Excel file")

class LeadModelForm(forms.ModelForm):
    relationship_manager = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name="Relationship Managers"),
        required=False,
        label="Relationship Manager",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    generated_by = forms.ModelChoiceField(
        queryset=BusinessDevelopmentManager.objects.select_related('user').all(),
        required=False,
        label="Generated By (BDM)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    temp_client_name = forms.CharField(
        max_length=255, required=False, label="Client Name",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    temp_client_email = forms.EmailField(
        required=False, label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    temp_client_phone = forms.CharField(
        max_length=10, required=False, label="Phone",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Lead
        fields = ['lead_info', 'generated_by', 'relationship_manager',
                  'temp_client_name', 'temp_client_email', 'temp_client_phone']
        widgets = {
            'lead_info': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),

        }
