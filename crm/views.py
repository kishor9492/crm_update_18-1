from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Client, Lead, Meeting, Sale, BusinessDevelopmentManager
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.contrib.auth.models import User

from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
import pandas as pd
from .models import Client, ClientRMHistory
from django.db import transaction
from django.contrib import messages
from .forms import FileUploadForm, AddClientForm,BulkRMTransferForm, FileUploadForm, BulkLeadUploadForm, LeadModelForm
from django.db.models import Count, Sum, Q, OuterRef, Subquery, Avg
from openpyxl import Workbook
import json
import openpyxl
from django.utils.timezone import now
import datetime
from datetime import timedelta
from django.http import JsonResponse
from .models import Sale, Meeting, User, Call, Client
from django.utils.dateparse import parse_datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse
from django.conf import settings


from .forms import AddCallForm, CallFilterForm, BulkCallUploadForm
import io

from django.utils import timezone
from .forms import UpdateClientForm
from .forms import LeadForm  # assume you have a LeadForm for lead creation
from .models import BusinessDevelopmentManager, Redemption
from .models import (
    AppraisalPeriod, AppraisalQuestion, EmployeeAssignment,
    AppraisalReview, AppraisalAnswer
)


@login_required
def home(request):
    # Get counts based on user role
    if request.user.is_superuser:
        total_clients = Client.objects.count()
        total_calls = Call.objects.count()
        total_meetings = Meeting.objects.count()
        total_sales = Sale.objects.count()
    else:
        # For regular users, show only their assigned data
        total_clients = Client.objects.filter(relationship_manager=request.user).count()
        total_calls = Call.objects.filter(relationship_manager=request.user).count()
        total_meetings = Meeting.objects.filter(relationship_manager=request.user).count()
        total_sales = Sale.objects.filter(relationship_manager=request.user).count()

    context = {
        'total_clients': total_clients,
        'total_calls': total_calls,
        'total_meetings': total_meetings,
        'total_sales': total_sales,
    }

    return render(request, 'crm/home.html', context)

@login_required
def client_list(request):
    relationship_managers = User.objects.filter(groups__name='Relationship Managers')

    if request.user.is_superuser:
        clients = Client.objects.all()
    else:
        clients = Client.objects.filter(relationship_manager=request.user)

    # Get total counts for stats
    total_clients = clients.count()
    total_rms = relationship_managers.count()

    rm_id = request.GET.get('rm_id')
    if request.user.is_superuser and rm_id:
        clients = clients.filter(relationship_manager__id=rm_id)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        clients = clients.filter(Q(name__icontains=search_query) | Q(pan__icontains=search_query))

    status_filter = request.GET.get('status')
    # Annotate with last connected call datetime
    latest_call_subquery = Call.objects.filter(
        client=OuterRef('pk'),
        call_status='connected'
    ).order_by('-call_start_time')

    clients = clients.annotate(
        last_connected_call=Subquery(latest_call_subquery.values('call_start_time')[:1])
    )

    # Prepare filtered list based on status_filter
    clients_with_status = []
    active_clients = 0
    never_connected = 0

    for client in clients:
        last_call = client.last_connected_call
        if last_call:
            days_ago = (now() - last_call).days
            if days_ago <= 30:
                status = "Connected (within 30 days)"
                active_clients += 1
            else:
                status = "Connected (over 30 days ago)"
        else:
            status = "Never Connected"
            never_connected += 1

        # Filter on status if filter applied
        if status_filter and status_filter != 'all' and status != status_filter:
            continue

        clients_with_status.append((client, status))

    # Pagination
    paginator = Paginator(clients_with_status, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'relationship_managers': relationship_managers,
        'selected_rm_id': rm_id,
        'selected_status': status_filter or 'all',
        'total_clients': total_clients,
        'active_clients': active_clients,
        'never_connected': never_connected,
        'total_rms': total_rms,
    }
    return render(request, 'crm/client_list.html', context)


@login_required
def export_clients_csv(request):
    rm_id = request.GET.get('rm_id')

    if request.user.is_superuser:
        clients = Client.objects.all()
        if rm_id:
            clients = clients.filter(relationship_manager__id=rm_id)
    else:
        clients = Client.objects.filter(relationship_manager=request.user)

    # Optional: Apply search filter if needed
    search_query = request.GET.get('search', '').strip()
    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) | Q(pan__icontains=search_query)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clients_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'PAN', 'Relationship Manager'])

    for client in clients:
        writer.writerow([
            client.name,
            client.email,
            client.phone,
            client.pan,
            client.relationship_manager.get_full_name() if client.relationship_manager else 'Not Assigned'
        ])

    return response



#add single client




@login_required
def add_client(request):
    # Allow access only for superusers
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == "POST":
        form = AddClientForm(request.POST)
        if form.is_valid():
            # Get form data
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            pan = form.cleaned_data.get('pan', '')  # Optional PAN field
            manager = form.cleaned_data.get('relationship_manager')  # This will be a User object
            sourced_by = form.cleaned_data.get('sourced_by')
            # Create the client object
            Client.objects.create(
                name=name,
                email=email,
                phone=phone,
                pan=pan,  # Save PAN
                relationship_manager=manager,
                sourced_by=sourced_by,# Pass the User object directly if your model supports it
            )
            return redirect('success_page')  # Replace with a success URL or client list page

    else:
        form = AddClientForm()

    return render(request, 'crm/add_client.html', {'form': form})
#@login_required


#update meeting remark
@login_required
def add_meeting(request, client_id):
    # Allow superusers to access all clients
    if request.user.is_superuser:
        client = get_object_or_404(Client, id=client_id)
    else:
        client = get_object_or_404(Client, id=client_id, relationship_manager=request.user)

    if request.method == 'POST':
        date = request.POST.get('date')
        notes = request.POST.get('notes')
        remark = request.POST.get('remark')

        Meeting.objects.create(
            client=client,
            relationship_manager=request.user,
            date=date,
            notes=notes,
            remark=remark,
        )
        return redirect('client_list')  # Redirect to client list or another page

    return render(request, 'crm/add_meeting.html', {'client': client})
@login_required
def update_meeting_remark(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id, relationship_manager=request.user)
    if request.method == 'POST':
        remark = request.POST.get('remark')
        if remark in ['Completed', 'Pending']:
            meeting.remark = remark
            meeting.save()
        return redirect('client_list')
    return render(request, 'crm/update_meeting_remark.html', {'meeting': meeting})

#update meeting
@login_required
def update_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if request.method == 'POST':
        meeting.date = request.POST.get('date', meeting.date)
        meeting.notes = request.POST.get('notes', meeting.notes)
        meeting.remark = request.POST.get('remark', meeting.remark)
        meeting.save()
        return redirect('meetings_list')  # Replace with the appropriate redirect
    return render(request, 'crm/update_meeting.html', {'meeting': meeting})


#delete Meeting
@login_required
def delete_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if request.method == 'POST':
        meeting.delete()
        return redirect('meetings_list')  # Replace with the appropriate redirect
    return render(request, 'crm/confirm_delete.html', {'meeting': meeting})


@login_required
def add_sale(request, client_id):

    if request.user.is_superuser:
        client = get_object_or_404(Client, id=client_id)
    else:
        client = get_object_or_404(Client, id=client_id, relationship_manager=request.user)

    if request.method == 'POST':
        products = request.POST.getlist('product[]')  # Retrieve all products
        fund_names = request.POST.getlist('fund_name[]')  # Retrieve all fund names
        amounts = request.POST.getlist('amount[]')  # Retrieve all amounts
        sale_dates = request.POST.getlist('sale_date[]')  # Retrieve all sale dates

        # Iterate through the submitted entries and create Sale objects
        for product, fund_name, amount, sale_date in zip(products, fund_names, amounts, sale_dates):
            if all([product, fund_name, amount, sale_date]):  # Ensure all fields are populated
                Sale.objects.create(client=client, product=product, fund_name=fund_name, amount=amount,
                                    sale_date=sale_date, relationship_manager=client.relationship_manager)
                # Update open leads for this client
                Lead.objects.filter(client=client, status='open').update(status='closed')

                # Optionally, also update leads that might still be using temp_client_name
                Lead.objects.filter(temp_client_name=client.name, status='open').update(status='closed')
        return redirect('client_list')  # Redirect after saving all entries

    return render(request, 'crm/add_sales.html', {'client': client})




@login_required
def update_sale(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)

    if request.method == 'POST':
        sale.product = request.POST['product']  # Directly assign selected choice (string)
        sale.fund_name = request.POST['fund_name']
        sale.amount = request.POST['amount']
        sale.sale_date = parse_datetime(request.POST['sale_date'])  # Convert to datetime
        sale.save()
        return redirect('sales_list')

    return render(request, 'crm/update_sales.html', {'sale': sale})
@login_required
def delete_sale(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)

    if request.method == 'POST':  # Confirm before deleting
        sale.delete()
        return redirect('sales_list')

    return render(request, 'crm/confirm_delete.html', {'sale': sale})

  # Adjust as per your app

from django.utils.dateparse import parse_date
from django.core.paginator import Paginator

@login_required
def meetings_list(request, client_id=None):
    # Get existing filters
    filter_remark = request.GET.get('remark', '').strip()
    search_query = request.GET.get('search', '').strip()

    # Get date filters
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    # Parse dates
    start_date = parse_date(start_date_str) if start_date_str else None
    end_date = parse_date(end_date_str) if end_date_str else None

    # Role-based query
    if request.user.is_superuser:
        meetings = Meeting.objects.select_related('client', 'relationship_manager').all()
        client = None
    else:
        if client_id:
            client = get_object_or_404(Client, id=client_id, relationship_manager=request.user)
            meetings = Meeting.objects.filter(client=client, relationship_manager=request.user).select_related('relationship_manager')
        else:
            client = None
            meetings = Meeting.objects.filter(relationship_manager=request.user).select_related('client')

    # Apply search filter
    if search_query:
        meetings = meetings.filter(
            Q(client__name__icontains=search_query) |
            Q(relationship_manager__first_name__icontains=search_query) |
            Q(relationship_manager__last_name__icontains=search_query)
        )

    # Apply remark filter
    if filter_remark in ['Completed', 'Pending']:
        meetings = meetings.filter(remark=filter_remark)

    # Apply date range filter
    if start_date:
        meetings = meetings.filter(date__gte=start_date)
    if end_date:
        meetings = meetings.filter(date__lte=end_date)

    # Order by most recent date
    meetings = meetings.order_by('-date')

    # Pagination
    paginator = Paginator(meetings, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Pass filters back to template for persistent UI
    context = {
        'page_obj': page_obj,
        'client': client,
        'filter_remark': filter_remark,
        'search_query': search_query,
        'start_date': start_date_str,
        'end_date': end_date_str,
    }
    return render(request, 'crm/meetings_list.html', context)

@login_required
def sales_list(request):
    is_relationship_manager = (
        not request.user.is_superuser and
        request.user.groups.filter(name="Relationship Managers").exists()
    )

    if request.user.is_superuser:
        # Superusers see all sales
        sales = Sale.objects.select_related('client', 'relationship_manager').all()
    else:
        # Normal users see only sales they created (or were assigned to)
        sales = Sale.objects.filter(relationship_manager=request.user).select_related('client', 'relationship_manager')

    # Apply filters
    relationship_manager = request.GET.get('relationship_manager')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    product = request.GET.get('product')
    client_name = request.GET.get('client_name')  # New filter for client name

    if relationship_manager:
        first_name, *last_name = relationship_manager.split()
        sales = sales.filter(client__relationship_manager__first_name__icontains=first_name)
        if last_name:
            sales = sales.filter(client__relationship_manager__last_name__icontains=' '.join(last_name))
    if start_date and end_date:
        sales = sales.filter(sale_date__range=[start_date, end_date])
    elif start_date:
        sales = sales.filter(sale_date__gte=start_date)
    elif end_date:
        sales = sales.filter(sale_date__lte=end_date)
    if product:
        sales = sales.filter(product__icontains=product)
    if client_name:  # Apply the client name filter
        sales = sales.filter(client__name__icontains=client_name)
    sales = sales.order_by('-sale_date')

    # Pagination
    paginator = Paginator(sales, 10)  # Show 20 sales per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'crm/sales_list.html', {
        'page_obj': page_obj,
        'is_relationship_manager': is_relationship_manager,
        'relationship_manager': relationship_manager,
        'start_date': start_date,
        'end_date': end_date,
        'product': product,
        'client_name': client_name,  # Pass the client name to the template
    })


@login_required
def export_meetings_to_excel(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Create an Excel workbook and sheet
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Meetings"

    # Add headers
    headers = ["Client Name", "Relationship Manager", "Date", "Notes", "Remark"]
    sheet.append(headers)

    # Add data
    meetings = Meeting.objects.select_related('client', 'relationship_manager').all()
    for meeting in meetings:
        sheet.append([
            meeting.client.name,
            meeting.relationship_manager.get_full_name() if meeting.relationship_manager else "Not Assigned",
            meeting.date.strftime('%Y-%m-%d') if meeting.date else "N/A",  # Format the date
            meeting.notes,
            meeting.remark,
        ])

    # Prepare HTTP response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="meetings.xlsx"'
    workbook.save(response)
    return response
#export sales data to excel


@login_required
def export_sales_to_excel(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Create an Excel workbook and sheet
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales"

    # Add headers
    headers = ["Client Name", "Relationship Manager", "Product", "Fund Name", "Amount", "Sale Date"]
    sheet.append(headers)

    # Add data
    sales = Sale.objects.select_related('client', 'client__relationship_manager').all()
    for sale in sales:
        sheet.append([
            sale.client.name,
            sale.client.relationship_manager.get_full_name() if sale.client.relationship_manager else "Not Assigned",
            dict(Sale.PRODUCT_CHOICES).get(sale.product, sale.product),  # Get full product name
            sale.fund_name if sale.product == "SIP" else "N/A",  # Include fund name for SIP, otherwise N/A
            float(sale.amount),  # Convert Decimal to float for Excel
            sale.sale_date.strftime('%Y-%m-%d') if sale.sale_date else "N/A",  # Format date as string
        ])

    # Prepare HTTP response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="sales.xlsx"'
    workbook.save(response)
    return response

#update client



@login_required
def update_client(request, client_id):
    # Allow access only for superusers
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Get the client object or return 404 if not found
    client = get_object_or_404(Client, id=client_id)

    if request.method == "POST":
        form = UpdateClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()  # Update the client details
            return redirect('client_list')  # Redirect to the client list after updating
    else:
        form = UpdateClientForm(instance=client)

    return render(request, 'crm/update_client.html', {'form': form, 'client': client})



@login_required
def delete_client(request, client_id):
    # Allow access only for superusers
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    client = get_object_or_404(Client, id=client_id)

    if request.method == "POST":
        client.delete()
        return redirect('client_list')  # Redirect to client list after deletion

    # For GET, show a confirmation page
    return render(request, 'crm/confirm_delete.html', {'client': client})

def success_page(request):
    return render(request, 'crm/success.html')


#bulk transfer client to rm
@login_required
def bulk_rm_transfer(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == 'POST':
        form = BulkRMTransferForm(request.POST)
        if form.is_valid():
            old_rm = form.cleaned_data['old_rm']
            new_rm = form.cleaned_data['new_rm']

            clients_to_update = Client.objects.filter(relationship_manager=old_rm)
            count = clients_to_update.count()

            with transaction.atomic():
                # Update client RMs
                clients_to_update.update(relationship_manager=new_rm)

                # Update ClientRMHistory for each client
                for client in clients_to_update:
                    # Close previous RM history
                    ClientRMHistory.objects.filter(client=client, relationship_manager=old_rm,
                                                   end_date__isnull=True).update(end_date=datetime.date.today())

                    # Add new RM history entry
                    ClientRMHistory.objects.create(
                        client=client,
                        relationship_manager=new_rm,
                        start_date=datetime.date.today(),
                        end_date=None
                    )

            messages.success(request,
                             f'Successfully transferred {count} clients from {old_rm.get_full_name()} to {new_rm.get_full_name()}.')
            return redirect('bulk_rm_transfer')
    else:
        form = BulkRMTransferForm()

    return render(request, 'crm/bulk_rm_transfer.html', {'form': form})

#dashbord


#call details


@login_required
def add_call(request, client_id):
    """Add a new call record for a specific client"""
    if request.user.is_superuser:
        client = get_object_or_404(Client, id=client_id)
    else:
        client = get_object_or_404(Client, id=client_id, relationship_manager=request.user)

    if request.method == 'POST':
        form = AddCallForm(request.POST)
        if form.is_valid():
            call = form.save(commit=False)
            call.client = client
            call.relationship_manager = request.user

            # Auto-calculate duration if both start and end times are provided
            if call.call_start_time and call.call_end_time:
                duration = call.call_end_time - call.call_start_time
                call.duration_minutes = int(duration.total_seconds() / 60)

            call.save()
            messages.success(request, f'Call record added for {client.name}')
            return redirect('calls_list')
    else:
        # Pre-fill phone number from client data
        initial_data = {'phone_number': client.phone}
        form = AddCallForm(initial=initial_data)

    return render(request, 'crm/add_call.html', {'form': form, 'client': client})


@login_required
def calls_list(request):
    """List all calls with filters and search"""
    # Base queryset based on user permissions
    if request.user.is_superuser:
        calls = Call.objects.select_related('client', 'relationship_manager').all()
    else:
        calls = Call.objects.filter(relationship_manager=request.user).select_related('client')

    # Apply filters
    filter_form = CallFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['relationship_manager'] and request.user.is_superuser:
            calls = calls.filter(relationship_manager=filter_form.cleaned_data['relationship_manager'])

        if filter_form.cleaned_data['call_type']:
            calls = calls.filter(call_type=filter_form.cleaned_data['call_type'])

        if filter_form.cleaned_data['call_status']:
            calls = calls.filter(call_status=filter_form.cleaned_data['call_status'])

        if filter_form.cleaned_data['call_purpose']:
            calls = calls.filter(call_purpose=filter_form.cleaned_data['call_purpose'])

        if filter_form.cleaned_data['start_date']:
            calls = calls.filter(call_start_time__date__gte=filter_form.cleaned_data['start_date'])

        if filter_form.cleaned_data['end_date']:
            calls = calls.filter(call_start_time__date__lte=filter_form.cleaned_data['end_date'])

        if filter_form.cleaned_data['client_name']:
            calls = calls.filter(client__name__icontains=filter_form.cleaned_data['client_name'])

    # Order by most recent calls
    calls = calls.order_by('-call_start_time')

    # Pagination
    paginator = Paginator(calls, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'crm/calls_list.html', {
        'page_obj': page_obj,
        'filter_form': filter_form,
    })


@login_required
def call_detail(request, call_id):
    """View detailed information about a specific call"""
    if request.user.is_superuser:
        call = get_object_or_404(Call, id=call_id)
    else:
        call = get_object_or_404(Call, id=call_id, relationship_manager=request.user)

    return render(request, 'crm/call_detail.html', {'call': call})


@login_required
def update_call(request, call_id):
    """Update an existing call record"""
    if request.user.is_superuser:
        call = get_object_or_404(Call, id=call_id)
    else:
        call = get_object_or_404(Call, id=call_id, relationship_manager=request.user)

    if request.method == 'POST':
        form = AddCallForm(request.POST, instance=call)
        if form.is_valid():
            updated_call = form.save(commit=False)

            # Auto-calculate duration if both start and end times are provided
            if updated_call.call_start_time and updated_call.call_end_time:
                duration = updated_call.call_end_time - updated_call.call_start_time
                updated_call.duration_minutes = int(duration.total_seconds() / 60)

            updated_call.save()
            messages.success(request, 'Call record updated successfully')
            return redirect('call_detail', call_id=call.id)
    else:
        form = AddCallForm(instance=call)

    return render(request, 'crm/update_call.html', {'form': form, 'call': call})


@login_required
def delete_call(request, call_id):
    """Delete a call record"""
    if request.user.is_superuser:
        call = get_object_or_404(Call, id=call_id)
    else:
        call = get_object_or_404(Call, id=call_id, relationship_manager=request.user)

    if request.method == 'POST':
        call.delete()
        messages.success(request, 'Call record deleted successfully')
        return redirect('calls_list')

    return render(request, 'crm/confirm_delete.html', {'call': call})


@login_required
def client_calls(request, client_id):
    """View all calls for a specific client"""
    if request.user.is_superuser:
        client = get_object_or_404(Client, id=client_id)
    else:
        client = get_object_or_404(Client, id=client_id, relationship_manager=request.user)

    calls = Call.objects.filter(client=client).order_by('-call_start_time')

    # Pagination
    paginator = Paginator(calls, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'crm/client_calls.html', {
        'client': client,
        'page_obj': page_obj,
    })


@login_required
def calls_analytics(request):
    """Analytics dashboard for call performance"""
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Get filter parameters
    rm_id = request.GET.get('rm_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Base queryset
    calls = Call.objects.all()

    # Apply filters
    if rm_id:
        calls = calls.filter(relationship_manager__id=rm_id)
    if start_date:
        calls = calls.filter(call_start_time__date__gte=start_date)
    if end_date:
        calls = calls.filter(call_start_time__date__lte=end_date)

    # Calculate analytics
    analytics_data = {
        'total_calls': calls.count(),
        'connected_calls': calls.filter(call_status='connected').count(),
        'avg_duration': calls.filter(duration_minutes__isnull=False).aggregate(
            avg=Avg('duration_minutes')
        )['avg'] or 0,
        'avg_connection_time': calls.filter(connection_time_seconds__isnull=False).aggregate(
            avg=Avg('connection_time_seconds')
        )['avg'] or 0,
    }

    from django.db.models import ExpressionWrapper, FloatField, F, Case, When, Value

    rm_performance = calls.values(
        'relationship_manager__first_name',
        'relationship_manager__last_name',
        'relationship_manager__id'
    ).annotate(
        total_calls=Count('id'),
        connected_calls=Count('id', filter=Q(call_status='connected')),
        avg_duration=Avg('duration_minutes'),
        avg_connection_time=Avg('connection_time_seconds'),
    ).annotate(
        success_rate=ExpressionWrapper(
            Case(
                When(total_calls=0, then=Value(0)),
                default=F('connected_calls') * 100.0 / F('total_calls'),
                output_field=FloatField(),
            ),
            output_field=FloatField()
        )
    )

    # Call status distribution
    status_distribution = calls.values('call_status').annotate(count=Count('id'))

    from django.contrib.auth.models import User
    relationship_managers = User.objects.filter(groups__name='Relationship Managers')

    return render(request, 'crm/calls_analytics.html', {
        'analytics_data': analytics_data,
        'rm_performance': rm_performance,
        'status_distribution': status_distribution,
        'relationship_managers': relationship_managers,
        'selected_rm_id': rm_id,
        'start_date': start_date,
        'end_date': end_date,
    })


@login_required
def export_calls_csv(request):
    """Export calls to CSV"""
    # Filter based on user permissions
    if request.user.is_superuser:
        calls = Call.objects.select_related('client', 'relationship_manager').all()
    else:
        calls = Call.objects.filter(relationship_manager=request.user).select_related('client')

    # Apply same filters as in calls_list
    filter_form = CallFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['relationship_manager'] and request.user.is_superuser:
            calls = calls.filter(relationship_manager=filter_form.cleaned_data['relationship_manager'])

        if filter_form.cleaned_data['call_type']:
            calls = calls.filter(call_type=filter_form.cleaned_data['call_type'])

        if filter_form.cleaned_data['call_status']:
            calls = calls.filter(call_status=filter_form.cleaned_data['call_status'])

        if filter_form.cleaned_data['call_purpose']:
            calls = calls.filter(call_purpose=filter_form.cleaned_data['call_purpose'])

        if filter_form.cleaned_data['start_date']:
            calls = calls.filter(call_start_time__date__gte=filter_form.cleaned_data['start_date'])

        if filter_form.cleaned_data['end_date']:
            calls = calls.filter(call_start_time__date__lte=filter_form.cleaned_data['end_date'])

        if filter_form.cleaned_data['client_name']:
            calls = calls.filter(client__name__icontains=filter_form.cleaned_data['client_name'])

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="calls_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Client Name', 'Phone Number', 'Relationship Manager', 'Call Type',
        'Call Status', 'Call Purpose', 'Start Time', 'End Time',
        'Duration (Minutes)', 'Connection Time (Seconds)', 'Notes',
        'Follow-up Required', 'Follow-up Date'
    ])

    for call in calls:
        writer.writerow([
            call.client.name,
            call.phone_number,
            call.relationship_manager.get_full_name(),
            call.get_call_type_display(),
            call.get_call_status_display(),
            call.get_call_purpose_display(),
            call.call_start_time.strftime('%Y-%m-%d %H:%M:%S'),
            call.call_end_time.strftime('%Y-%m-%d %H:%M:%S') if call.call_end_time else '',
            call.duration_minutes or '',
            call.connection_time_seconds or '',
            call.notes,
            'Yes' if call.follow_up_required else 'No',
            call.follow_up_date.strftime('%Y-%m-%d') if call.follow_up_date else '',
        ])

    return response




@login_required
def crm_dashboard(request):
    user = request.user
    rm_id = request.GET.get('relationship_manager_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    is_bdm = user.groups.filter(name='Business Development Manager').exists()
    is_rm = user.groups.filter(name='Relationship Managers').exists()
    is_admin = not (is_bdm or is_rm)

    bdm_instance = getattr(user, 'bdm_profile', None)

    sales_data = Sale.objects.all()
    meetings_data = Meeting.objects.all()
    leads_data = Lead.objects.all()

    if is_rm:
        sales_data = sales_data.filter(relationship_manager=user)
        meetings_data = meetings_data.filter(relationship_manager=user)
        leads_data = leads_data.filter(client__relationship_manager=user)
    elif is_bdm:
        if bdm_instance:
            leads_data = leads_data.filter(generated_by=bdm_instance)
            sales_data = sales_data.filter(bdm=bdm_instance)
        else:
            leads_data = leads_data.none()
            sales_data = sales_data.none()
        meetings_data = meetings_data.none()
    elif is_admin:
        if rm_id:
            sales_data = sales_data.filter(relationship_manager_id=rm_id)
            meetings_data = meetings_data.filter(relationship_manager_id=rm_id)
            leads_data = leads_data.filter(client__relationship_manager_id=rm_id)
    else:
        sales_data = sales_data.none()
        meetings_data = meetings_data.none()
        leads_data = leads_data.none()

    if start_date:
        sales_data = sales_data.filter(sale_date__gte=start_date)
        meetings_data = meetings_data.filter(date__gte=start_date)
        leads_data = leads_data.filter(created_at__date__gte=start_date)
    if end_date:
        sales_data = sales_data.filter(sale_date__lte=end_date)
        meetings_data = meetings_data.filter(date__lte=end_date)
        leads_data = leads_data.filter(created_at__date__lte=end_date)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Sales by product (for product breakdown)
        sales_by_product = sales_data.values('product').annotate(total_sales=Sum('amount'))
        
        # Sales by relationship manager (for pie chart)
        sales_summary = sales_data.values(
            'relationship_manager__id',
            'relationship_manager__first_name',
            'relationship_manager__last_name'
        ).annotate(total_sales=Sum('amount'))
        meetings_summary = meetings_data.values(
            'relationship_manager__id',
            'relationship_manager__first_name',
            'relationship_manager__last_name'
        ).annotate(total_meetings=Count('id'))

        product_sales_per_manager = sales_data.values(
            'relationship_manager__id',
            'relationship_manager__first_name',
            'relationship_manager__last_name',
            'product'
        ).annotate(total_sales=Sum('amount')).order_by(
            'relationship_manager__first_name',
            'relationship_manager__last_name'
        )

        bdm_performance = []
        if is_admin:
            bdms = BusinessDevelopmentManager.objects.select_related('user')
            for bdm in bdms:
                # Filter open and closed leads by date
                open_leads_qs = Lead.objects.filter(generated_by=bdm, status='open')
                closed_leads_qs = Lead.objects.filter(generated_by=bdm, status='closed')

                if start_date:
                    open_leads_qs = open_leads_qs.filter(created_at__date__gte=start_date)
                    closed_leads_qs = closed_leads_qs.filter(created_at__date__gte=start_date)
                if end_date:
                    open_leads_qs = open_leads_qs.filter(created_at__date__lte=end_date)
                    closed_leads_qs = closed_leads_qs.filter(created_at__date__lte=end_date)

                open_leads_count = open_leads_qs.count()
                closed_leads_count = closed_leads_qs.count()

                # Filter sales by date
                sales_by_product_qs = Sale.objects.filter(bdm=bdm)
                if start_date:
                    sales_by_product_qs = sales_by_product_qs.filter(sale_date__gte=start_date)
                if end_date:
                    sales_by_product_qs = sales_by_product_qs.filter(sale_date__lte=end_date)

                sales_by_product = sales_by_product_qs.values('product').annotate(total_amount=Sum('amount'))
                sales_dict = {item['product']: item['total_amount'] for item in sales_by_product}

                bdm_performance.append({
                    'id': bdm.id,
                    'name': bdm.user.get_full_name(),
                    'open_leads': open_leads_count,
                    'closed_leads': closed_leads_count,
                    'sales_by_product': sales_dict
                })
        elif is_bdm and bdm_instance:
            open_leads_qs = Lead.objects.filter(generated_by=bdm_instance, status='open')
            closed_leads_qs = Lead.objects.filter(generated_by=bdm_instance, status='closed')

            if start_date:
                open_leads_qs = open_leads_qs.filter(created_at__date__gte=start_date)
                closed_leads_qs = closed_leads_qs.filter(created_at__date__gte=start_date)
            if end_date:
                open_leads_qs = open_leads_qs.filter(created_at__date__lte=end_date)
                closed_leads_qs = closed_leads_qs.filter(created_at__date__lte=end_date)

            open_leads_count = open_leads_qs.count()
            closed_leads_count = closed_leads_qs.count()

            sales_by_product_qs = Sale.objects.filter(bdm=bdm_instance)
            if start_date:
                sales_by_product_qs = sales_by_product_qs.filter(sale_date__gte=start_date)
            if end_date:
                sales_by_product_qs = sales_by_product_qs.filter(sale_date__lte=end_date)

            sales_by_product = sales_by_product_qs.values('product').annotate(total_amount=Sum('amount'))
            sales_dict = {item['product']: item['total_amount'] for item in sales_by_product}

            bdm_performance.append({
                'id': bdm_instance.id,
                'name': user.get_full_name(),
                'open_leads': open_leads_count,
                'closed_leads': closed_leads_count,
                'sales_by_product': sales_dict
            })

        # Get redemptions data for net sales calculation
        redemptions_data = Redemption.objects.all()
        if is_rm:
            redemptions_data = redemptions_data.filter(relationship_manager=user)
        elif is_admin and rm_id:
            redemptions_data = redemptions_data.filter(relationship_manager_id=rm_id)
        
        if start_date:
            redemptions_data = redemptions_data.filter(redemption_date__gte=start_date)
        if end_date:
            redemptions_data = redemptions_data.filter(redemption_date__lte=end_date)
        
        # Redemptions per manager per product
        product_redemptions_per_manager = redemptions_data.values(
            'relationship_manager__id',
            'relationship_manager__first_name',
            'relationship_manager__last_name',
            'product'
        ).annotate(total_redemptions=Sum('amount')).order_by(
            'relationship_manager__first_name',
            'relationship_manager__last_name'
        )

        return JsonResponse({
            'sales_data': list(sales_summary),
            'meetings_data': {
                'total_meetings': meetings_data.count(),
                'summary': list(meetings_summary),
            },
            'product_sales_per_manager': list(product_sales_per_manager),
            'product_redemptions_per_manager': list(product_redemptions_per_manager),
            'bdm_performance': bdm_performance,
        })

    relationship_managers = User.objects.filter(groups__name='Relationship Managers')
    return render(request, 'crm/admin_dashboard.html', {
        'relationship_managers': relationship_managers,
        'selected_manager_id': rm_id,
        'start_date': start_date,
        'end_date': end_date,
        'is_bdm': is_bdm,
        'is_rm': is_rm,
        'is_admin': is_admin,
        'show_bdm_performance': is_admin or is_bdm,
    })


def add_lead(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            existing_client = form.cleaned_data.get('existing_client')

            # Determine client
            if existing_client:
                client = existing_client
                temp_name = None
                temp_email = None
                temp_phone = None
            else:
                client = None
                temp_name = form.cleaned_data.get('name')
                temp_email = form.cleaned_data.get('email')
                temp_phone = form.cleaned_data.get('phone')

            # Create the lead
            Lead.objects.create(
                client=client,
                lead_info=form.cleaned_data['lead_info'],
                status='open',  # Always set default status here
                temp_client_name=temp_name,
                temp_client_email=temp_email,
                temp_client_phone=temp_phone,
                generated_by=request.user.businessdevelopmentmanager if hasattr(request.user,'businessdevelopmentmanager') else None,
                relationship_manager=form.cleaned_data.get('relationship_manager')  # Include if present in form
            )

            messages.success(request, "Lead added successfully.")
            return redirect('leads_list')
    else:
        form = LeadForm()

    return render(request, 'crm/add_lead.html', {'form': form})





@login_required
@permission_required('crm.view_lead', raise_exception=True)
def leads_list(request):
    user = request.user
    search_query = request.GET.get('search', '').strip()
    rm_filter = request.GET.get('rm', '')
    bdm_filter = request.GET.get('bdm', '')
    status_filter = request.GET.get('status', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    if user.is_superuser:
        leads = Lead.objects.select_related('client', 'generated_by', 'relationship_manager')
    elif user.groups.filter(name='Relationship Managers').exists():
        leads = Lead.objects.filter(relationship_manager=user).select_related(
            'client', 'generated_by', 'relationship_manager'
        )
    else:
        try:
            bdm_profile = user.bdm_profile
            leads = Lead.objects.filter(generated_by=bdm_profile).select_related(
                'client', 'generated_by', 'relationship_manager'
            )
        except BusinessDevelopmentManager.DoesNotExist:
            leads = Lead.objects.none()

    # Search filter
    if search_query:
        leads = leads.filter(
            Q(client__name__icontains=search_query)
            | Q(client__email__icontains=search_query)
            | Q(client__phone__icontains=search_query)
            | Q(temp_client_name__icontains=search_query)
            | Q(temp_client_email__icontains=search_query)
            | Q(temp_client_phone__icontains=search_query)
            | Q(lead_info__icontains=search_query)
        )

    # Updated filters with safe handling
    if rm_filter:
        if rm_filter.isdigit():
            leads = leads.filter(relationship_manager__id=int(rm_filter))
        else:
            leads = leads.filter(
                Q(relationship_manager__first_name__icontains=rm_filter)
                | Q(relationship_manager__last_name__icontains=rm_filter)
                | Q(relationship_manager__username__icontains=rm_filter)
            )

    if bdm_filter:
        if bdm_filter.isdigit():
            leads = leads.filter(generated_by__id=int(bdm_filter))
        else:
            leads = leads.filter(
                Q(generated_by__user__first_name__icontains=bdm_filter)
                | Q(generated_by__user__last_name__icontains=bdm_filter)
                | Q(generated_by__user__username__icontains=bdm_filter)
            )

    if status_filter:
        leads = leads.filter(status=status_filter)

    # Date filters
    if start_date:
        leads = leads.filter(created_at__date__gte=start_date)
    if end_date:
        leads = leads.filter(created_at__date__lte=end_date)

    leads = leads.order_by('-created_at')

    paginator = Paginator(leads, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    open_leads_count = leads.filter(status='open').count()
    closed_leads_count = leads.filter(status='closed').count()

    return render(
        request,
        'crm/leads_list.html',
        {
            'page_obj': page_obj,
            'relationship_managers': User.objects.filter(groups__name="Relationship Managers"),
            'bdms': BusinessDevelopmentManager.objects.all(),
            'search_query': search_query,
            'rm_filter': rm_filter,
            'bdm_filter': bdm_filter,
            'status_filter': status_filter,
            'start_date': start_date,
            'end_date': end_date,
            'status_choices': Lead.STATUS_CHOICES,
            'open_leads_count': open_leads_count,
            'closed_leads_count': closed_leads_count,
        },
    )

@login_required
def edit_lead(request, pk):
    lead = get_object_or_404(Lead, pk=pk)

    if request.method == 'POST':
        form = LeadModelForm(request.POST, instance=lead)

        # Adjust querysets for restricted users so form fields contain current values
        if not request.user.is_superuser:
            if lead.generated_by:
                form.fields['generated_by'].queryset = BusinessDevelopmentManager.objects.filter(pk=lead.generated_by.pk)
            if lead.relationship_manager:
                form.fields['relationship_manager'].queryset = User.objects.filter(pk=lead.relationship_manager.pk)

        if form.is_valid():
            lead = form.save(commit=False)

            # Preserve generated_by if missing from form submission
            new_bdm = form.cleaned_data.get('generated_by')
            if new_bdm is None:
                lead.generated_by = Lead.objects.get(pk=lead.pk).generated_by

            # Preserve relationship_manager if missing from form submission
            new_rm = form.cleaned_data.get('relationship_manager')
            if new_rm is None:
                lead.relationship_manager = Lead.objects.get(pk=lead.pk).relationship_manager

            # Handle temp client info
            temp_name = form.cleaned_data.get("temp_client_name")
            temp_email = form.cleaned_data.get("temp_client_email")
            temp_phone = form.cleaned_data.get("temp_client_phone")

            if lead.client:
                client = lead.client
                client.name = temp_name or client.name
                client.email = temp_email or client.email
                client.phone = temp_phone or client.phone
                client.save()
            else:
                lead.temp_client_name = temp_name
                lead.temp_client_email = temp_email
                lead.temp_client_phone = temp_phone

            lead.save()
            return redirect('leads_list')
    else:
        form = LeadModelForm(instance=lead)

        # Adjust querysets similarly on GET
        if not request.user.is_superuser:
            if lead.generated_by:
                form.fields['generated_by'].queryset = BusinessDevelopmentManager.objects.filter(pk=lead.generated_by.pk)
            if lead.relationship_manager:
                form.fields['relationship_manager'].queryset = User.objects.filter(pk=lead.relationship_manager.pk)

    return render(request, 'crm/edit_lead.html', {'form': form, 'lead': lead, 'user': request.user})

@login_required
@permission_required('crm.delete_lead', raise_exception=True)
def delete_lead(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)

    if request.method == 'POST':
        lead.delete()
        messages.success(request, "Lead deleted successfully.")
        return redirect('leads_list')

    # For safety, render a confirmation page on GET
    return render(request, 'crm/confirm_delete.html', {'object': lead, 'type': 'Lead'})



import csv

def leads_export(request):
    # Apply same filters as leads_list if needed
    leads = Lead.objects.select_related('client', 'generated_by', 'client__relationship_manager').all()

    # Create HTTP response with CSV content
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'

    writer = csv.writer(response)
    # Write CSV header row
    writer.writerow(['Lead ID', 'Client Name', 'Client Email', 'Lead Info', 'Status', 'Generated By (BDM)', 'Relationship Manager', 'Created At'])

    # Write lead data rows
    for lead in leads:
        writer.writerow([
            lead.id,
            lead.client.name if lead.client else lead.temp_client_name or '',
            lead.client.email if lead.client else lead.temp_client_email or '',
            lead.lead_info,
            lead.get_status_display(),
            lead.generated_by.user.get_full_name() if lead.generated_by else '',
            lead.client.relationship_manager.get_full_name() if lead.client and lead.client.relationship_manager else '',
            lead.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response




@login_required
@permission_required('crm.change_lead', raise_exception=True)
def transfer_lead_to_client(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)

    if not lead.client:
        client = Client.objects.create(
            name=lead.temp_client_name,
            email=lead.temp_client_email,
            phone=lead.temp_client_phone,
            relationship_manager=request.user  # optional: assign RM dynamically
        )
        lead.client = client
        lead.save(update_fields=['client'])  # status remains 'open'

    messages.success(request, "Lead successfully transferred to Client.")
    return redirect('leads_list')



from django.urls import reverse

@login_required
def upload_clients(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            data = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)

            for _, row in data.iterrows():
                name = row['Name']
                email = row['Email']
                phone = row['Phone']
                pan = row.get('PAN', '')
                manager_first_name = row['Relationship Manager First Name']
                manager_last_name = row['Relationship Manager Last Name']

                manager = User.objects.filter(
                    first_name=manager_first_name,
                    last_name=manager_last_name
                ).first()

                Client.objects.create(
                    name=name,
                    email=email,
                    phone=phone,
                    pan=pan,
                    relationship_manager=manager
                )
            messages.success(request, f'Successfully uploaded clients.')
            return redirect('client_list')
    else:
        form = FileUploadForm()

    upload_config = {
        'icon': '👥',
        'title': 'Clients',
        'subtitle': 'Upload a CSV or Excel file with client information',
        'requirements': [
            'Supported formats: CSV, Excel (.xlsx, .xls)',
            'Required columns: Name, Email, Phone, PAN',
            'Required columns: Relationship Manager First Name, Relationship Manager Last Name',
            'Maximum file size: 10MB'
        ],
        'template_content': 'Name,Email,Phone,PAN,Relationship Manager First Name,Relationship Manager Last Name\nJohn Doe,john@example.com,9876543210,ABCDE1234F,Raj,Kumar',
        'template_filename': 'client_upload_template.csv',
        'back_url': reverse('client_list'),
        'back_text': 'Client List'
    }

    return render(request, 'crm/generic_upload.html', {
        'upload_config': upload_config,
        'form': form
    })


@login_required
def upload_sales(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            data = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)

            for _, row in data.iterrows():
                client_name = row.get('Client Name')
                product = row.get('Product')
                fund_name = row.get('Fund Name', '')
                amount = row.get('Amount')
                sale_date = row.get('Sale Date')

                client = Client.objects.filter(name__iexact=client_name).first()
                if client:
                    Sale.objects.create(
                        client=client,
                        product=product,
                        fund_name=fund_name if fund_name else None,
                        amount=amount,
                        sale_date=pd.to_datetime(sale_date),
                        relationship_manager=client.relationship_manager,
                    )
            messages.success(request, f'Successfully uploaded sales.')
            return redirect('sales_list')
    else:
        form = FileUploadForm()

    upload_config = {
        'icon': '💰',
        'title': 'Sales',
        'subtitle': 'Upload a CSV or Excel file with sales transaction data',
        'requirements': [
            'Supported formats: CSV, Excel (.xlsx, .xls)',
            'Required columns: Client Name, Product, Amount, Sale Date',
            'Optional: Fund Name',
            'Maximum file size: 10MB'
        ],
        'template_content': 'Client Name,Product,Fund Name,Amount,Sale Date\nJohn Doe,MF,HDFC Equity Fund,50000,2025-01-15',
        'template_filename': 'sales_upload_template.csv',
        'back_url': reverse('sales_list'),
        'back_text': 'Sales List'
    }

    return render(request, 'crm/generic_upload.html', {
        'upload_config': upload_config,
        'form': form
    })


@login_required
def upload_meetings(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            data = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)

            for _, row in data.iterrows():
                client_name = row.get('Client Name')
                rm_name = row.get('Relationship Manager')
                date = row.get('Date')
                notes = row.get('Notes', '')
                remark = row.get('Remark', '')

                client = Client.objects.filter(name__iexact=client_name).first()
                if client:
                    Meeting.objects.create(
                        client=client,
                        relationship_manager=client.relationship_manager,
                        date=pd.to_datetime(date),
                        notes=notes,
                        remark=remark,
                    )
            messages.success(request, f'Successfully uploaded meetings.')
            return redirect('meetings_list')
    else:
        form = FileUploadForm()

    upload_config = {
        'icon': '📅',
        'title': 'Meetings',
        'subtitle': 'Upload a CSV or Excel file with meeting information',
        'requirements': [
            'Supported formats: CSV, Excel (.xlsx, .xls)',
            'Required columns: Client Name, Date, Notes, Remark',
            'Date format: YYYY-MM-DD HH:MM',
            'Maximum file size: 10MB'
        ],
        'template_content': 'Client Name,Date,Notes,Remark\nJohn Doe,2025-01-15 10:00,Discussed portfolio,Pending',
        'template_filename': 'meetings_upload_template.csv',
        'back_url': reverse('meetings_list'),
        'back_text': 'Meetings List'
    }

    return render(request, 'crm/generic_upload.html', {
        'upload_config': upload_config,
        'form': form
    })


@login_required
def upload_calls(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    if request.method == "POST":
        form = BulkCallUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            try:
                data = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)

                success_count = 0
                error_count = 0

                for _, row in data.iterrows():
                    try:
                        client_name = row['Client Name']
                        rm_first_name = row['Relationship Manager First Name']
                        rm_last_name = row['Relationship Manager Last Name']

                        client = Client.objects.filter(name__iexact=client_name).first()
                        rm = User.objects.filter(
                            first_name=rm_first_name,
                            last_name=rm_last_name
                        ).first()

                        if client and rm:
                            call_start_time = pd.to_datetime(row['Call Start Time'])
                            call_end_time = pd.to_datetime(row['Call End Time']) if pd.notna(
                                row.get('Call End Time')) else None

                            Call.objects.create(
                                client=client,
                                relationship_manager=rm,
                                call_type=row.get('Call Type', 'outgoing'),
                                call_status=row['Call Status'],
                                call_purpose=row.get('Call Purpose', 'follow_up'),
                                phone_number=row['Phone Number'],
                                call_start_time=call_start_time,
                                call_end_time=call_end_time,
                                duration_minutes=row.get('Duration Minutes') if pd.notna(
                                    row.get('Duration Minutes')) else None,
                                connection_time_seconds=row.get('Connection Time Seconds') if pd.notna(
                                    row.get('Connection Time Seconds')) else None,
                                notes=row.get('Notes', ''),
                                follow_up_required=bool(row.get('Follow-up Required', False)),
                                follow_up_date=pd.to_datetime(row['Follow-up Date']).date() if pd.notna(
                                    row.get('Follow-up Date')) else None,
                            )
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        error_count += 1

                messages.success(request, f'Successfully uploaded {success_count} calls. {error_count} errors.')
                return redirect('calls_list')

            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
    else:
        form = BulkCallUploadForm()

    upload_config = {
        'icon': '📞',
        'title': 'Calls',
        'subtitle': 'Upload a CSV or Excel file with call records',
        'requirements': [
            'Supported formats: CSV, Excel (.xlsx, .xls)',
            'Required columns: Client Name, Relationship Manager First Name, Relationship Manager Last Name',
            'Required columns: Call Status, Phone Number, Call Start Time',
            'Optional: Call Type, Call Purpose, Call End Time, Duration Minutes, Notes, Follow-up Required, Follow-up Date',
            'Maximum file size: 10MB'
        ],
        'template_content': 'Client Name,Relationship Manager First Name,Relationship Manager Last Name,Call Type,Call Status,Call Purpose,Phone Number,Call Start Time,Call End Time,Duration Minutes,Connection Time Seconds,Notes,Follow-up Required,Follow-up Date\nJohn Doe,Raj,Kumar,outgoing,completed,follow_up,9876543210,2025-01-15 14:30,2025-01-15 14:45,15,5,Discussed new products,True,2025-01-20',
        'template_filename': 'calls_upload_template.csv',
        'back_url': reverse('calls_list'),
        'back_text': 'Calls List'
    }

    return render(request, 'crm/generic_upload.html', {
        'upload_config': upload_config,
        'form': form
    })


@login_required
def bulk_leads_upload(request):
    if request.method == 'POST':
        form = BulkLeadUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            try:
                try:
                    decoded_file = uploaded_file.read().decode('utf-8')
                except UnicodeDecodeError:
                    uploaded_file.seek(0)
                    decoded_file = uploaded_file.read().decode('latin1')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)

                for row in reader:
                    client_name = row.get('client_name', '').strip()
                    client_email = row.get('client_email', '').strip()
                    client_phone = row.get('client_phone', '').strip()
                    lead_info = row.get('lead_info', '').strip()
                    status = row.get('status', 'open').strip().lower()
                    bdm_username = row.get('bdm_username', '').strip()

                    client = Client.objects.filter(
                        name=client_name,
                        email=client_email,
                        phone=client_phone
                    ).first()

                    bdm = None
                    if bdm_username:
                        bdm = BusinessDevelopmentManager.objects.filter(
                            user__username=bdm_username
                        ).first()

                    Lead.objects.create(
                        client=client,
                        lead_info=lead_info,
                        status=status or 'open',
                        generated_by=bdm,
                        temp_client_name=client_name if not client else None,
                        temp_client_email=client_email if not client else None,
                        temp_client_phone=client_phone if not client else None
                    )

                messages.success(request, "Leads imported successfully from CSV.")
                return redirect('leads_list')
            except Exception as e:
                messages.error(request, f"Error processing file: {e}")
    else:
        form = BulkLeadUploadForm()

    upload_config = {
        'icon': '🎯',
        'title': 'Leads',
        'subtitle': 'Upload a CSV or Excel file with lead information',
        'requirements': [
            'Supported formats: CSV, Excel (.xlsx, .xls)',
            'Required columns: client_name, client_email, client_phone, lead_info, status',
            'Optional: bdm_username',
            'Status values: open, in_progress, closed',
            'Maximum file size: 10MB'
        ],
        'template_content': 'client_name,client_email,client_phone,lead_info,status,bdm_username\nJohn Doe,john@example.com,9876543210,Interested in MF,open,bdm_user1',
        'template_filename': 'leads_upload_template.csv',
        'back_url': reverse('leads_list'),
        'back_text': 'Leads List'
    }

    return render(request, 'crm/generic_upload.html', {
        'upload_config': upload_config,
        'form': form
    })

def custom_logout_view(request):
    logout(request)
    return redirect('/')  # Redirect to the homepage


# RM Performance Dashboard View
@login_required
def rm_performance(request, rm_id):
    """View detailed performance analytics for a specific Relationship Manager"""
    # Only admin/superuser can access this page
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Get the RM user
    rm_user = get_object_or_404(User, id=rm_id)

    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    month = request.GET.get('month')

    # Handle month filter - convert to date range
    if month:
        try:
            year, month_num = month.split('-')
            import calendar
            first_day = datetime.date(int(year), int(month_num), 1)
            last_day = datetime.date(int(year), int(month_num), calendar.monthrange(int(year), int(month_num))[1])
            start_date = first_day.strftime('%Y-%m-%d')
            end_date = last_day.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            pass

    # Base querysets for this RM
    clients = Client.objects.filter(relationship_manager=rm_user)
    sales = Sale.objects.filter(relationship_manager=rm_user)
    meetings = Meeting.objects.filter(relationship_manager=rm_user)
    calls = Call.objects.filter(relationship_manager=rm_user)
    leads = Lead.objects.filter(client__relationship_manager=rm_user)

    # Apply date filters
    if start_date:
        sales = sales.filter(sale_date__gte=start_date)
        meetings = meetings.filter(date__gte=start_date)
        calls = calls.filter(call_start_time__date__gte=start_date)
        leads = leads.filter(created_at__date__gte=start_date)
    if end_date:
        sales = sales.filter(sale_date__lte=end_date)
        meetings = meetings.filter(date__lte=end_date)
        calls = calls.filter(call_start_time__date__lte=end_date)
        leads = leads.filter(created_at__date__lte=end_date)

    # Calculate statistics
    total_clients = clients.count()
    total_sales_amount = sales.aggregate(total=Sum('amount'))['total'] or 0
    total_meetings = meetings.count()
    completed_meetings = meetings.filter(remark='Completed').count()
    pending_meetings = meetings.filter(remark='Pending').count()
    total_calls = calls.count()
    connected_calls = calls.filter(call_status='connected').count()
    total_leads = leads.count()
    open_leads = leads.filter(status='open').count()
    closed_leads = leads.filter(status='closed').count()

    # Product-wise sales breakdown
    product_sales = sales.values('product').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    # Meeting status breakdown
    meeting_status = meetings.values('remark').annotate(count=Count('id'))

    # Call status breakdown
    call_status_breakdown = calls.values('call_status').annotate(count=Count('id'))

    # Call purpose breakdown
    call_purpose_breakdown = calls.values('call_purpose').annotate(count=Count('id'))

    # Recent activities (last 10 of each)
    recent_sales = sales.select_related('client').order_by('-sale_date')[:10]
    recent_meetings = meetings.select_related('client').order_by('-date')[:10]
    recent_calls = calls.select_related('client').order_by('-call_start_time')[:10]

    # Monthly sales trend (last 6 months)
    six_months_ago = datetime.date.today() - datetime.timedelta(days=180)
    monthly_sales = sales.filter(sale_date__gte=six_months_ago).values(
        'sale_date__year', 'sale_date__month'
    ).annotate(
        total_amount=Sum('amount'),
        count=Count('id')
    ).order_by('sale_date__year', 'sale_date__month')

    # Generate month options for filter dropdown
    current_date = datetime.date.today()
    month_options = []
    for i in range(12):
        month_date = current_date - datetime.timedelta(days=30 * i)
        month_options.append({
            'value': month_date.strftime('%Y-%m'),
            'label': month_date.strftime('%B %Y')
        })

    # Handle AJAX request for chart data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'rm_name': rm_user.get_full_name(),
            'total_clients': total_clients,
            'total_sales_amount': float(total_sales_amount),
            'total_meetings': total_meetings,
            'completed_meetings': completed_meetings,
            'pending_meetings': pending_meetings,
            'total_calls': total_calls,
            'connected_calls': connected_calls,
            'total_leads': total_leads,
            'open_leads': open_leads,
            'closed_leads': closed_leads,
            'product_sales': list(product_sales),
            'meeting_status': list(meeting_status),
            'call_status_breakdown': list(call_status_breakdown),
            'call_purpose_breakdown': list(call_purpose_breakdown),
            'monthly_sales': list(monthly_sales),
        })

    context = {
        'rm_user': rm_user,
        'total_clients': total_clients,
        'total_sales_amount': total_sales_amount,
        'total_meetings': total_meetings,
        'completed_meetings': completed_meetings,
        'pending_meetings': pending_meetings,
        'total_calls': total_calls,
        'connected_calls': connected_calls,
        'total_leads': total_leads,
        'open_leads': open_leads,
        'closed_leads': closed_leads,
        'product_sales': product_sales,
        'meeting_status': meeting_status,
        'call_status_breakdown': call_status_breakdown,
        'call_purpose_breakdown': call_purpose_breakdown,
        'recent_sales': recent_sales,
        'recent_meetings': recent_meetings,
        'recent_calls': recent_calls,
        'monthly_sales': monthly_sales,
        'start_date': start_date or '',
        'end_date': end_date or '',
        'month': month or '',
        'month_options': month_options,
        'product_choices': Sale.PRODUCT_CHOICES,
    }

    return render(request, 'crm/rm_performance.html', context)


# BDM Performance Dashboard View
@login_required
def bdm_performance(request, bdm_id):
    """View detailed performance analytics for a specific Business Development Manager"""
    # Only admin/superuser can access this page
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this page.")

    # Get the BDM
    bdm = get_object_or_404(BusinessDevelopmentManager, id=bdm_id)
    bdm_user = bdm.user

    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    month = request.GET.get('month')

    # Handle month filter - convert to date range
    if month:
        try:
            year, month_num = month.split('-')
            import calendar
            first_day = datetime.date(int(year), int(month_num), 1)
            last_day = datetime.date(int(year), int(month_num), calendar.monthrange(int(year), int(month_num))[1])
            start_date = first_day.strftime('%Y-%m-%d')
            end_date = last_day.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            pass

    # Base querysets for this BDM
    leads = Lead.objects.filter(generated_by=bdm)
    sales = Sale.objects.filter(bdm=bdm)

    # Apply date filters
    if start_date:
        leads = leads.filter(created_at__date__gte=start_date)
        sales = sales.filter(sale_date__gte=start_date)
    if end_date:
        leads = leads.filter(created_at__date__lte=end_date)
        sales = sales.filter(sale_date__lte=end_date)

    # Calculate statistics
    total_leads = leads.count()
    open_leads = leads.filter(status='open').count()
    closed_leads = leads.filter(status='closed').count()
    total_sales_amount = sales.aggregate(total=Sum('amount'))['total'] or 0
    total_sales_count = sales.count()

    # Conversion rate
    conversion_rate = (closed_leads / total_leads * 100) if total_leads > 0 else 0

    # Product-wise sales breakdown
    product_sales = sales.values('product').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    # Lead status breakdown
    lead_status_breakdown = leads.values('status').annotate(count=Count('id'))

    # Recent leads (last 10)
    recent_leads = leads.select_related('client').order_by('-created_at')[:10]
    
    # Recent sales (last 10)
    recent_sales = sales.select_related('client').order_by('-sale_date')[:10]

    # Monthly leads trend (last 6 months)
    six_months_ago = datetime.date.today() - datetime.timedelta(days=180)
    monthly_leads = leads.filter(created_at__date__gte=six_months_ago).values(
        'created_at__year', 'created_at__month'
    ).annotate(
        count=Count('id')
    ).order_by('created_at__year', 'created_at__month')

    # Generate month options for filter dropdown
    current_date = datetime.date.today()
    month_options = []
    for i in range(12):
        month_date = current_date - datetime.timedelta(days=30 * i)
        month_options.append({
            'value': month_date.strftime('%Y-%m'),
            'label': month_date.strftime('%B %Y')
        })

    # Handle AJAX request for chart data
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'bdm_name': bdm_user.get_full_name(),
            'total_leads': total_leads,
            'open_leads': open_leads,
            'closed_leads': closed_leads,
            'conversion_rate': round(conversion_rate, 1),
            'total_sales_amount': float(total_sales_amount),
            'total_sales_count': total_sales_count,
            'product_sales': list(product_sales),
            'lead_status_breakdown': list(lead_status_breakdown),
            'monthly_leads': list(monthly_leads),
        })

    context = {
        'bdm': bdm,
        'bdm_user': bdm_user,
        'total_leads': total_leads,
        'open_leads': open_leads,
        'closed_leads': closed_leads,
        'conversion_rate': round(conversion_rate, 1),
        'total_sales_amount': total_sales_amount,
        'total_sales_count': total_sales_count,
        'product_sales': product_sales,
        'lead_status_breakdown': lead_status_breakdown,
        'recent_leads': recent_leads,
        'recent_sales': recent_sales,
        'monthly_leads': monthly_leads,
        'start_date': start_date or '',
        'end_date': end_date or '',
        'month': month or '',
        'month_options': month_options,
        'product_choices': Sale.PRODUCT_CHOICES,
    }

    return render(request, 'crm/bdm_performance.html', context)


# ==================== REDEMPTIONS VIEWS ====================

@login_required
def redemptions_list(request):
    """List all redemptions with filters"""
    user = request.user
    
    if user.is_superuser:
        redemptions = Redemption.objects.select_related('client', 'relationship_manager')
    elif user.groups.filter(name='Relationship Managers').exists():
        redemptions = Redemption.objects.filter(relationship_manager=user).select_related('client', 'relationship_manager')
    else:
        redemptions = Redemption.objects.none()
    
    # Apply filters
    search = request.GET.get('search', '')
    product = request.GET.get('product', '')
    redemption_type = request.GET.get('redemption_type', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if search:
        redemptions = redemptions.filter(
            Q(client__name__icontains=search) | Q(fund_name__icontains=search)
        )
    if product:
        redemptions = redemptions.filter(product=product)
    if redemption_type:
        redemptions = redemptions.filter(redemption_type=redemption_type)
    if start_date:
        redemptions = redemptions.filter(redemption_date__gte=start_date)
    if end_date:
        redemptions = redemptions.filter(redemption_date__lte=end_date)
    
    paginator = Paginator(redemptions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'product': product,
        'redemption_type': redemption_type,
        'start_date': start_date,
        'end_date': end_date,
        'product_choices': Sale.PRODUCT_CHOICES,
        'redemption_type_choices': Redemption.REDEMPTION_TYPE_CHOICES,
    }
    return render(request, 'crm/redemptions_list.html', context)


@login_required
def add_redemption(request, client_id):
    """Add a new redemption for a client"""
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        product = request.POST.get('product')
        redemption_type = request.POST.get('redemption_type')
        fund_name = request.POST.get('fund_name', '')
        amount = request.POST.get('amount')
        redemption_date = request.POST.get('redemption_date')
        notes = request.POST.get('notes', '')
        
        Redemption.objects.create(
            client=client,
            product=product,
            redemption_type=redemption_type,
            fund_name=fund_name,
            amount=amount,
            redemption_date=redemption_date,
            relationship_manager=request.user,
            notes=notes
        )
        
        messages.success(request, 'Redemption added successfully!')
        return redirect('client_list')
    
    context = {
        'client': client,
        'product_choices': Sale.PRODUCT_CHOICES,
        'redemption_type_choices': Redemption.REDEMPTION_TYPE_CHOICES,
    }
    return render(request, 'crm/add_redemption.html', context)


@login_required
def update_redemption(request, redemption_id):
    """Update a redemption"""
    redemption = get_object_or_404(Redemption, id=redemption_id)
    
    if request.method == 'POST':
        redemption.product = request.POST.get('product')
        redemption.redemption_type = request.POST.get('redemption_type')
        redemption.fund_name = request.POST.get('fund_name', '')
        redemption.amount = request.POST.get('amount')
        redemption.redemption_date = request.POST.get('redemption_date')
        redemption.notes = request.POST.get('notes', '')
        redemption.save()
        
        messages.success(request, 'Redemption updated successfully!')
        return redirect('redemptions_list')
    
    context = {
        'redemption': redemption,
        'product_choices': Sale.PRODUCT_CHOICES,
        'redemption_type_choices': Redemption.REDEMPTION_TYPE_CHOICES,
    }
    return render(request, 'crm/update_redemption.html', context)


@login_required
def delete_redemption(request, redemption_id):
    """Delete a redemption"""
    redemption = get_object_or_404(Redemption, id=redemption_id)
    
    if request.method == 'POST':
        redemption.delete()
        messages.success(request, 'Redemption deleted successfully!')
        return redirect('redemptions_list')
    
    return render(request, 'crm/confirm_delete.html', {'object': redemption, 'type': 'Redemption'})


# ==================== 360-DEGREE APPRAISAL VIEWS ====================

@login_required
def appraisal_list(request):
    """List all appraisals for current user"""
    user = request.user
    
    # Get active appraisal period
    active_period = AppraisalPeriod.objects.filter(is_active=True).first()
    
    # Get all years for filter
    all_years = AppraisalPeriod.objects.values_list('year', flat=True).distinct().order_by('-year')
    selected_year = request.GET.get('year', '')
    
    if user.is_superuser:
        # Admin sees all reviews
        reviews = AppraisalReview.objects.select_related('employee', 'manager', 'period').all()
    else:
        # Employee sees their own reviews
        reviews = AppraisalReview.objects.filter(employee=user).select_related('employee', 'manager', 'period')
        
        # Manager sees reviews of their subordinates
        try:
            subordinate_ids = EmployeeAssignment.objects.filter(manager=user).values_list('employee_id', flat=True)
            subordinate_reviews = AppraisalReview.objects.filter(
                employee_id__in=subordinate_ids
            ).select_related('employee', 'manager', 'period')
            reviews = reviews | subordinate_reviews
        except:
            pass
    
    # Filter by year if selected
    if selected_year:
        reviews = reviews.filter(period__year=selected_year)
    
    # Group reviews by year for display with answers prefetched
    reviews_by_year = {}
    reviews_with_answers = reviews.distinct().prefetch_related('answers__question').order_by('-period__year', '-period__start_date')
    for review in reviews_with_answers:
        year = review.period.year
        if year not in reviews_by_year:
            reviews_by_year[year] = []
        reviews_by_year[year].append(review)
    
    # Check if user needs to create a self-review for active period
    needs_self_review = False
    can_edit_review = None  # Review that can be edited
    if active_period and not user.is_superuser:
        try:
            assignment = EmployeeAssignment.objects.get(employee=user)
            existing_review = AppraisalReview.objects.filter(employee=user, period=active_period).first()
            if not existing_review:
                needs_self_review = True
            elif existing_review.status in ['draft', 'submitted']:
                # Can edit if status is draft or submitted (not yet manager reviewed)
                can_edit_review = existing_review
        except EmployeeAssignment.DoesNotExist:
            pass
    
    # Get subordinates for manager view (with review status)
    subordinates_data = []
    is_manager = False
    if not user.is_superuser:
        subordinates = EmployeeAssignment.objects.filter(manager=user).select_related('employee')
        if subordinates.exists():
            is_manager = True
            for sub in subordinates:
                sub_review = None
                sub_status = 'not_started'
                can_review = False
                can_update = False
                
                if active_period:
                    sub_review = AppraisalReview.objects.filter(
                        employee=sub.employee,
                        period=active_period
                    ).first()
                    
                    if sub_review:
                        sub_status = sub_review.status
                        # Manager can review if employee submitted
                        if sub_review.status == 'submitted':
                            can_review = True
                        # Manager can update if already reviewed but not completed
                        elif sub_review.status == 'manager_reviewed':
                            can_update = True
                
                subordinates_data.append({
                    'employee': sub.employee,
                    'employee_type': sub.get_employee_type_display(),
                    'review': sub_review,
                    'status': sub_status,
                    'can_review': can_review,
                    'can_update': can_update,
                })
    
    context = {
        'reviews': reviews.distinct().order_by('-period__start_date'),
        'reviews_by_year': reviews_by_year,
        'all_years': all_years,
        'selected_year': selected_year,
        'active_period': active_period,
        'needs_self_review': needs_self_review,
        'can_edit_review': can_edit_review,
        'is_admin': user.is_superuser,
        'is_manager': is_manager,
        'subordinates_data': subordinates_data,
    }
    return render(request, 'crm/appraisal_list.html', context)


@login_required
def appraisal_self_review(request, period_id):
    """Employee self-review form"""
    user = request.user
    period = get_object_or_404(AppraisalPeriod, id=period_id, is_active=True)
    
    # Get or create review
    try:
        assignment = EmployeeAssignment.objects.get(employee=user)
    except EmployeeAssignment.DoesNotExist:
        messages.error(request, 'You are not assigned for appraisal. Please contact HR.')
        return redirect('appraisal_list')
    
    review, created = AppraisalReview.objects.get_or_create(
        employee=user,
        period=period,
        defaults={'manager': assignment.manager}
    )
    
    # Prevent editing only if completed
    if review.status == 'completed':
        messages.error(request, "This review is locked because it has been finalized.")
        return redirect('appraisal_list')
    
    # Get questions
    questions = AppraisalQuestion.objects.filter(question_type='self', is_active=True)
    
    if request.method == 'POST':
        # Save answers
        for question in questions:
            answer_text = request.POST.get(f'answer_{question.id}', '')
            rating = request.POST.get(f'rating_{question.id}', None)
            
            AppraisalAnswer.objects.update_or_create(
                review=review,
                question=question,
                defaults={'answer_text': answer_text, 'rating': rating if rating else None}
            )
        
        # Save overall rating and comments
        review.self_overall_rating = request.POST.get('self_overall_rating', None)
        review.self_comments = request.POST.get('self_comments', '')
        
        # Manager rating by employee
        review.manager_rating_by_employee = request.POST.get('manager_rating', None)
        review.manager_comments_by_employee = request.POST.get('manager_comments', '')
        
        # Check if submitting or saving draft
        if 'submit' in request.POST:
            review.status = 'submitted'
            review.self_submitted_at = timezone.now()
            messages.success(request, 'Your self-review has been submitted successfully!')
        else:
            messages.success(request, 'Draft saved successfully!')
        
        review.save()
        return redirect('appraisal_list')
    
    # Get existing answers as dictionary
    existing_answers_dict = {a.question_id: a for a in review.answers.all()}
    
    # Attach existing answers to questions
    questions_with_answers = []
    for question in questions:
        answer = existing_answers_dict.get(question.id)
        questions_with_answers.append({
            'question': question,
            'answer_text': answer.answer_text if answer else '',
            'rating': answer.rating if answer else None,
        })
    
    context = {
        'review': review,
        'period': period,
        'questions_with_answers': questions_with_answers,
        'manager': assignment.manager,
    }
    return render(request, 'crm/appraisal_self_review.html', context)


@login_required
def appraisal_manager_review(request, review_id):
    """Manager review form - can see employee self-review"""
    user = request.user
    review = get_object_or_404(AppraisalReview, id=review_id)
    
    # Check if user is the manager for this review
    if not user.is_superuser and review.manager != user:
        return HttpResponseForbidden("You are not authorized to view this review.")
    
    # Get employee's self answers
    employee_answers = review.answers.select_related('question').all()
    
    if request.method == 'POST' and review.status in ['submitted', 'manager_reviewed']:
        review.manager_rating = request.POST.get('manager_rating', None)
        review.manager_comments = request.POST.get('manager_comments', '')
        
        # Only update status if it was submitted
        if review.status == 'submitted':
            review.status = 'manager_reviewed'
            review.manager_reviewed_at = timezone.now()
            
        review.save()
        
        messages.success(request, 'Your review has been saved successfully!')
        return redirect('appraisal_list')
    
    context = {
        'review': review,
        'employee_answers': employee_answers,
        # Note: We don't pass manager_rating_by_employee - manager shouldn't see this
    }
    return render(request, 'crm/appraisal_manager_review.html', context)


@login_required
def appraisal_admin_view(request):
    """Admin view - see all reviews with all ratings including employee's manager rating"""
    # Check if user is superuser or in "HR All Access" group
    is_hr_admin = request.user.groups.filter(name='HR All Access').exists()
    
    if not (request.user.is_superuser or is_hr_admin):
        return HttpResponseForbidden("Only admin or authorized HR can access this page.")
    
    # Get unique years for filter
    years = AppraisalPeriod.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    # Filter options
    year_filter = request.GET.get('year', '')
    period_id = request.GET.get('period', '')
    status_filter = request.GET.get('status', '')
    
    # Get periods filtered by year
    periods = AppraisalPeriod.objects.all()
    if year_filter:
        periods = periods.filter(year=year_filter)
    
    # Get selected period or active period
    selected_period_obj = None
    if period_id:
        selected_period_obj = AppraisalPeriod.objects.filter(id=period_id).first()
    elif year_filter:
        # If year is selected, pick the first period of that year
        selected_period_obj = periods.first()
    else:
        selected_period_obj = AppraisalPeriod.objects.filter(is_active=True).first()
    
    # Get all employees with assignments
    all_assignments = EmployeeAssignment.objects.select_related('employee', 'manager').all()
    
    # Build employee data with review status
    employee_data = []
    for assignment in all_assignments:
        review = None
        review_status = 'not_started'
        
        if selected_period_obj:
            review = AppraisalReview.objects.filter(
                employee=assignment.employee,
                period=selected_period_obj
            ).select_related('period').first()
            
            if review:
                review_status = review.status
        
        # Apply status filter
        if status_filter:
            if status_filter == 'not_started' and review_status != 'not_started':
                continue
            elif status_filter != 'not_started' and review_status != status_filter:
                continue
        
        employee_data.append({
            'assignment': assignment,
            'employee': assignment.employee,
            'manager': assignment.manager,
            'employee_type': assignment.get_employee_type_display(),
            'review': review,
            'status': review_status,
            'self_overall_rating': review.self_overall_rating if review else None,
            'manager_rating_by_employee': review.manager_rating_by_employee if review else None,
            'manager_rating': review.manager_rating if review else None,
            'final_rating': review.final_rating if review else None,
        })
    
    # Extended status choices including 'not_started'
    status_choices = [('not_started', 'Not Started')] + list(AppraisalReview.STATUS_CHOICES)
    
    context = {
        'employee_data': employee_data,
        'years': years,
        'periods': periods,
        'selected_year': year_filter,
        'selected_period': period_id,
        'selected_period_obj': selected_period_obj,
        'selected_status': status_filter,
        'status_choices': status_choices,
    }
    return render(request, 'crm/appraisal_admin_view.html', context)


@login_required
def appraisal_admin_finalize(request, review_id):
    """Admin finalizes a review with final rating"""
    # Check if user is superuser or in "HR All Access" group
    is_hr_admin = request.user.groups.filter(name='HR All Access').exists()
    
    if not (request.user.is_superuser or is_hr_admin):
        return HttpResponseForbidden("Only admin can finalize reviews.")
    
    review = get_object_or_404(AppraisalReview, id=review_id)
    
    if request.method == 'POST':
        review.final_rating = request.POST.get('final_rating', None)
        review.final_comments = request.POST.get('final_comments', '')
        review.status = 'completed'
        review.completed_at = timezone.now()
        review.save()
        
        messages.success(request, 'Final review saved successfully!')
        return redirect('appraisal_admin_view')
    
    # Get all answers
    employee_answers = review.answers.select_related('question').all()
    
    context = {
        'review': review,
        'employee_answers': employee_answers,
    }
    return render(request, 'crm/appraisal_admin_finalize.html', context)


@login_required
def appraisal_employee_final(request, review_id):
    """Employee views their final rating (only visible after admin completes)"""
    review = get_object_or_404(AppraisalReview, id=review_id)
    
    # Only the employee can see their final review
    if review.employee != request.user:
        return HttpResponseForbidden("You can only view your own appraisal.")
    
    if review.status != 'completed':
        messages.info(request, 'Your appraisal is still being reviewed.')
        return redirect('appraisal_list')
    
    context = {
        'review': review,
    }
    return render(request, 'crm/appraisal_employee_final.html', context)


@login_required
def download_db(request):
    """Download the sqlite database file (Admin only)"""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Only admin can download the database.")
    
    db_path = settings.DATABASES['default']['NAME']
    return FileResponse(open(db_path, 'rb'), as_attachment=True, filename='db.sqlite3')
