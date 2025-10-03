from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    # path('notifications/', views.notifications_list, name='notifications_list'),
    # path('messages/', views.messages_list, name='messages_list'),
    # path('search/', views.search_view, name='search_view'),
    
]