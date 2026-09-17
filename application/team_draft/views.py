from django.http import JsonResponse
from django.shortcuts import render,get_object_or_404
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from league.views import body
from functools import wraps
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from league.domain import Invalid

def api(fn):
    @wraps(fn)
    def wrapped(request,*args,**kwargs):
        try:return fn(request,*args,**kwargs)
        except PermissionDenied as e:return JsonResponse({'error':str(e)},status=403 if request.user.is_authenticated else 401)
        except (Invalid,ValueError,TypeError,KeyError,ValidationError,ObjectDoesNotExist,signing.BadSignature) as e:return JsonResponse({'error':str(e) if isinstance(e,Invalid) else '请求格式错误或预览已失效'},status=400)
    return wrapped
from league.models import Event
from league.domain import require
from .models import DraftActivity
from .services import create,mutate,projection,manager,own_team,event_manager

@ensure_csrf_cookie
@require_GET
def home(request): return render(request,'team_draft/home.html')

@ensure_csrf_cookie
@require_GET
def page(request,id):
    get_object_or_404(DraftActivity,pk=id)
    return render(request,'team_draft/activity.html',{'activity_id':str(id)})

@api
def activities(request):
    if request.method=='POST':
        activity=create(request.user,body(request).get('name'))
        return JsonResponse({'id':str(activity.pk),'name':activity.name},status=201)
    require(request.method=='GET','请求方法不支持')
    rows=[]
    for activity in DraftActivity.objects.select_related('event').all():
        if manager(activity,request.user) or own_team(activity,request.user) or activity.document.get('public',False):
            rows.append(dict(id=str(activity.pk),name=activity.name,eventName=activity.event.name if activity.event_id else None,status=activity.status))
    events=[dict(id=str(e.pk),name=e.name) for e in Event.objects.filter(kind='team') if event_manager(e,request.user) and not e.document.get('archive') and not e.document.get('historySnapshot') and not any(m.get('state')!='cancelled' for m in e.document.get('matches',[]))]
    response=JsonResponse({'activities':rows,'events':events,'canCreate':bool(request.user.is_superuser or (request.user.is_authenticated and Event.objects.filter(editors=request.user).exists()))})
    response['Cache-Control']='no-store';return response

@api
def detail(request,id):
    activity=get_object_or_404(DraftActivity,pk=id)
    projection(activity,request.user)
    if request.method=='POST':
        data=body(request);action=data.get('action')
        if action=='preview':
            from .lifecycle import preview
            return JsonResponse({'preview':preview(id,request.user,data.get('revision'),data.get('operation'))})
        if action=='configure':
            require(manager(activity,request.user),'只有管理员可以配置')
            require(isinstance(data.get('teams'),list),'请配置队伍')
            for row in data['teams']:
                require(isinstance(row,dict),'队伍配置格式错误')
                if row.get('coachUsername'):
                    account=get_user_model().objects.filter(username=row['coachUsername'],is_active=True).first()
                    require(account is not None,'教练账号不存在或已停用')
                    row['coachUserId']=account.pk
        if action=='link':get_object_or_404(Event,pk=data.get('eventId'))
        activity=mutate(id,request.user,data.get('revision'),action,data)
    else: require(request.method=='GET','请求方法不支持')
    response=JsonResponse(projection(activity,request.user));response['Cache-Control']='no-store';return response
