from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


#add BDM
class BusinessDevelopmentManager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bdm_profile')
    contact_number = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    joining_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Client(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=10)
    pan = models.CharField(max_length=10, blank=True, null=True)  # Added PAN field
    relationship_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='clients'
    )
    sourced_by = models.ForeignKey(
        BusinessDevelopmentManager,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sourced_clients',
        help_text="BDM who sourced the client"
    )
    def __str__(self):
        return self.name

    def clean(self):
        import re
        from django.core.exceptions import ValidationError

        # Validate PAN format if provided
        if self.pan and not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', self.pan):
            raise ValidationError("Invalid PAN format.")


class Meeting(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='meetings')
    relationship_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='meetings')
    date = models.DateTimeField()
    notes = models.TextField()
    remark = models.CharField(
        max_length=255,
        choices=[('Completed', 'Completed'), ('Pending', 'Pending')],
        default='Pending'
    )
    updated_time = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"Meeting with {self.client.name} on {self.date}"


from django.db import models

class Sale(models.Model):
    PRODUCT_CHOICES = [
        ('SIP', 'SIP'),
        ('LUMP', 'Lumpsum'),
        ('HI', 'Health Insurance'),
        ('TI', 'Term Insurance'),
        ('PMS', 'PMS'),
        ('AIF', 'AIF'),
        ('WILL', 'Will'),
        ('GI', 'General Insurance'),
        ('SIF', 'Specialised Investment Funds')
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sales')
    product = models.CharField(choices=PRODUCT_CHOICES, max_length=10)
    fund_name = models.CharField(max_length=255, blank=True, null=True)  # Optional field for SIP
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    sale_date = models.DateField()
    relationship_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales')
    bdm = models.ForeignKey(
        BusinessDevelopmentManager,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales'
    )

    def save(self, *args, **kwargs):
        # If BDM not explicitly set, assign from client sourcing BDM
        if not self.bdm and self.client.sourced_by:
            self.bdm = self.client.sourced_by
        super().save(*args, **kwargs)

        # After saving Sale, close any open lead for this client
        Lead.objects.filter(client=self.client, status='open').update(status='closed')

    def clean(self):
        from django.core.exceptions import ValidationError

        # If the product is SIP, fund_name must be provided
        if self.product == 'SIP' and not self.fund_name:
            raise ValidationError("Fund Name is required for Systematic Investment Plan (SIP).")

        # Validate amount
        if self.amount <= 0:
            raise ValidationError("Sale amount must be greater than zero.")

    def __str__(self):
        product_name = dict(self.PRODUCT_CHOICES).get(self.product, self.product)
        if self.product == 'SIP' and self.fund_name:
            return f"{product_name} ({self.fund_name}) for {self.client.name}"
        return f"{product_name} for {self.client.name}"

class ClientRMHistory(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='rm_history')
    relationship_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='client_history')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Null means current RM

    class Meta:
        ordering = ['client', 'start_date']
        verbose_name = "Client RM History"
        verbose_name_plural = "Client RM Histories"

    def __str__(self):
        end = self.end_date if self.end_date else "Present"
        return f"{self.client.name} - {self.relationship_manager.get_full_name()} ({self.start_date} to {end})"


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# Add this new Call model to your existing models.py

class Call(models.Model):
    CALL_TYPE_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('missed', 'Missed'),
    ]

    CALL_STATUS_CHOICES = [
        ('connected', 'Connected'),
        ('busy', 'Busy'),
        ('no_answer', 'No Answer'),
        ('disconnected', 'Disconnected'),
        ('failed', 'Failed'),
    ]

    CALL_PURPOSE_CHOICES = [
        ('follow_up', 'Follow Up'),
        ('new_business', 'New Business'),
        ('service_request', 'Service Request'),
        ('complaint', 'Complaint'),
        ('information', 'Information'),
        ('portfolio_review', 'Portfolio Review'),
        ('other', 'Other'),
    ]

    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='calls')
    relationship_manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calls_made')
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES, default='outgoing')
    call_status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES)
    call_purpose = models.CharField(max_length=50, choices=CALL_PURPOSE_CHOICES, default='follow_up')

    # Time tracking
    call_start_time = models.DateTimeField(default=timezone.now)
    call_end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True, help_text="Duration in minutes")

    # Call details
    phone_number = models.CharField(max_length=20, help_text="Phone number used for the call")
    notes = models.TextField(blank=True, help_text="Call conversation notes")
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)

    # Performance tracking
    connection_time_seconds = models.IntegerField(null=True, blank=True, help_text="Time taken to connect in seconds")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-call_start_time']

    def __str__(self):
        return f"{self.client.name} - {self.call_type} - {self.call_start_time.strftime('%Y-%m-%d %H:%M')}"

    def get_duration_display(self):
        """Return formatted duration"""
        if self.duration_minutes:
            hours = self.duration_minutes // 60
            minutes = self.duration_minutes % 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "N/A"

    def get_connection_time_display(self):
        """Return formatted connection time"""
        if self.connection_time_seconds:
            if self.connection_time_seconds >= 60:
                minutes = self.connection_time_seconds // 60
                seconds = self.connection_time_seconds % 60
                return f"{minutes}m {seconds}s"
            return f"{self.connection_time_seconds}s"
        return "N/A"


class Lead(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]
    relationship_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='leads',
        null=True,       # allow client to be empty
        blank=True       # allow form/admin to leave it blank
    )
    lead_info = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        BusinessDevelopmentManager,
        on_delete=models.SET_NULL,
        null=True,
        related_name='leads_generated'
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    # Optional: store client info temporarily if no Client exists
    temp_client_name = models.CharField(max_length=255, blank=True, null=True)
    temp_client_email = models.EmailField(blank=True, null=True)
    temp_client_phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        if self.client:
            return f"Lead for {self.client.name}"
        return f"Lead for {self.temp_client_name or 'Unknown Client'}"


class Redemption(models.Model):
    """Track redemptions/withdrawals to calculate net sales"""
    PRODUCT_CHOICES = Sale.PRODUCT_CHOICES  # Same products as Sale
    
    REDEMPTION_TYPE_CHOICES = [
        ('SIP_STOP', 'SIP Stop'),
        ('PARTIAL', 'Partial Redemption'),
        ('FULL', 'Full Redemption'),
        ('SWITCH_OUT', 'Switch Out'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='redemptions')
    product = models.CharField(choices=PRODUCT_CHOICES, max_length=10)
    redemption_type = models.CharField(max_length=20, choices=REDEMPTION_TYPE_CHOICES)
    fund_name = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    redemption_date = models.DateField()
    relationship_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='redemptions')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-redemption_date']

    def __str__(self):
        return f"{self.get_redemption_type_display()} - {self.client.name} - ₹{self.amount}"


# 360-Degree Appraisal System Models

class AppraisalPeriod(models.Model):
    """Defines an appraisal period (e.g., Q1 2026, Annual 2025)"""
    name = models.CharField(max_length=100)  # e.g., "Q1 2026"
    year = models.IntegerField(default=2026)  # Year for easy filtering
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-start_date']

    def __str__(self):
        return f"{self.name} ({self.year})"


class AppraisalQuestion(models.Model):
    """Questions for appraisal (added by admin)"""
    QUESTION_TYPE_CHOICES = [
        ('self', 'Self Assessment'),
        ('manager', 'Manager Assessment'),
    ]
    question_text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE_CHOICES, default='self')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.question_text[:50]}..."


class EmployeeAssignment(models.Model):
    """Assigns a manager to each employee for appraisal purposes"""
    EMPLOYEE_TYPE_CHOICES = [
        ('RM', 'Relationship Manager'),
        ('BDM', 'Business Development Manager'),
        ('MANAGER', 'Manager'),
        ('HR', 'HR'),
    ]
    employee = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_assignment')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    employee_type = models.CharField(max_length=10, choices=EMPLOYEE_TYPE_CHOICES, default='RM')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        manager_name = self.manager.get_full_name() if self.manager else "No Manager"
        return f"{self.employee.get_full_name()} → {manager_name}"


class AppraisalReview(models.Model):
    """Main appraisal review record"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_reviewed', 'Manager Reviewed'),
        ('completed', 'Completed'),
    ]
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    period = models.ForeignKey(AppraisalPeriod, on_delete=models.CASCADE, related_name='reviews')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appraisals')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_appraisals')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Self assessment
    self_overall_rating = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    self_comments = models.TextField(blank=True)
    self_submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Rating for manager (by employee) - hidden from manager
    manager_rating_by_employee = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    manager_comments_by_employee = models.TextField(blank=True)
    
    # Manager review of employee
    manager_rating = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    manager_comments = models.TextField(blank=True)
    manager_reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Final rating by admin/superuser
    final_rating = models.IntegerField(null=True, blank=True, choices=RATING_CHOICES)
    final_comments = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['period', 'employee']
        ordering = ['-period__start_date', 'employee__first_name']

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.period.name}"


class AppraisalAnswer(models.Model):
    """Answers to appraisal questions"""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    review = models.ForeignKey(AppraisalReview, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(AppraisalQuestion, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['review', 'question']

    def __str__(self):
        return f"Answer for {self.question.question_text[:30]}..."
