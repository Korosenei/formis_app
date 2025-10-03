from django.shortcuts import render

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

# Create your views here.

@login_required
@require_POST
def mark_all_notifications_read(request):
    """Marque toutes les notifications comme lues"""
    request.user.notifications.filter(read=False).update(read=True)
    return JsonResponse({'status': 'success'})