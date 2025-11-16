"""
URL configuration for _formis project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Administration Django
    path('admin/', admin.site.urls),

    # API
    # path('api/', include('api.v1.urls')),
    #
    # # Applications principales
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('establishments/', include('apps.establishments.urls')),
    path('academic/', include('apps.academic.urls')),
    path('courses/', include('apps.courses.urls')),
    path('enrollment/', include('apps.enrollment.urls')),
    path('payments/', include('apps.payments.urls')),
    path('evaluation/', include('apps.evaluations.urls')),
    # path('resources/', include('apps.resources.urls')),
    # path('documents/', include('apps.documents.urls')),
    #
    # # Dashboard selon les rôles
    path('dashboard/', include('apps.core.dashboard_urls')),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
