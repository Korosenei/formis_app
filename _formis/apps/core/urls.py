from django.urls import path
from apps.accounts.views import LoginView

app_name = 'core'

urlpatterns = [
    path('', LoginView.as_view(), name='login'),
]
