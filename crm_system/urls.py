from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('crm.urls')),
]

# Add the static files URL mapping outside of the urlpatterns list
if settings.DEBUG:  # Serve static files only in development
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)