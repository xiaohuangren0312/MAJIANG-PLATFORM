"""Removable S1/S2/S3 backfill workspace; never used by the delivery management UI."""
from django.conf import settings
from django.http import Http404,JsonResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import render,get_object_or_404
from .models import Event
from . import views
from .permissions import actions_for

def check(request):
    if not settings.HISTORY_BACKFILL_ENABLED:raise Http404
    if not request.user.is_authenticated or not request.user.is_superuser:raise PermissionDenied('仅总管理员可使用历史补录区')

def candidates():
    rows=[e for e in Event.objects.all() if e.document.get('historySnapshot',{}).get('id','').lower() in ['s1','s2','s3']]
    return sorted(rows,key=lambda e:e.document['historySnapshot']['id'].lower())

@login_required
@ensure_csrf_cookie
def page(request):
    check(request)
    return render(request,'history-backfill.html')

@views.api
def events(request):
    check(request)
    return JsonResponse({'events':[views.summary(e,request.user) for e in candidates()]})

@views.api
def detail(request,id):
    check(request)
    e=get_object_or_404(Event,pk=id)
    if e.pk not in {x.pk for x in candidates()}:raise Http404
    if request.method=='GET':
        from .projection import public_event
        return JsonResponse({**views.summary(e,request.user),'actions':actions_for(e,request.user,backfill=True),'document':e.document,'historyDisplay':public_event(e)})
    request.history_backfill=True
    return views.event_detail(request,id)
