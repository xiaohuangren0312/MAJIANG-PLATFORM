"""Personalization access is scoped separately from roster competition commands."""
import copy
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render,get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Event,Audit
from .domain import require,find
from .views import api,body
from .coach_lineups import team_ids,manager,assigned_team
from .permissions import authorize

def source(e):return e.document.get('historyCurrent',e.document.get('historySnapshot',e.document))
def permitted(e,user,kind,id):
    if manager(e,user):
        authorize(e,user,'history-image' if e.document.get('historySnapshot') else kind+'-update')
        return find(source(e)['teams' if kind=='team' else 'players'],id)
    if any(e.document.get(k) for k in ['archive','archiveRevision','historySnapshot']):raise PermissionDenied('当前赛事不可修改队伍资料')
    ids=team_ids(e,user);d=e.document
    row=find(d['teams' if kind=='team' else 'players'],id)
    stage=d.get('stages',[])[-1]['id'] if d.get('stages') else None
    tid=id if kind=='team' else assigned_team(d,row,stage)
    if tid not in ids:raise PermissionDenied('只能编辑本队资料')
    return row

def listing(e,user):
    d=source(e);teams=[];players=[]
    for kind,out in [('team',teams),('player',players)]:
        for row in d.get('teams' if kind=='team' else 'players',[]):
            try:permitted(e,user,kind,row['id'])
            except PermissionDenied:continue
            out.append({k:row.get(k) for k in ['id','name','color','bio','imageUrl','teamId','bond']})
    return dict(id=str(e.pk),name=e.name,revision=e.revision,teams=teams,players=players)

@login_required
@ensure_csrf_cookie
def page(request):return render(request,'coach-profile.html')

@api
def events(request):
    require(request.method=='GET','请求方法不支持')
    rows=[]
    for e in Event.objects.prefetch_related('editors','draft_activities'):
        if e.document.get('archive') or (e.document.get('archiveRevision') and not request.user.is_superuser):continue
        if manager(e,request.user) or (not e.document.get('historySnapshot') and team_ids(e,request.user)):
            rows.append({'id':str(e.pk),'name':e.name})
    response=JsonResponse({'events':rows});response['Cache-Control']='no-store';return response

@api
@transaction.atomic
def detail(request,id):
    e=get_object_or_404(Event.objects.select_for_update(),pk=id)
    if not manager(e,request.user) and not team_ids(e,request.user):raise PermissionDenied('未获得本队资料权限')
    if request.method=='GET':
        response=JsonResponse(listing(e,request.user));response['Cache-Control']='no-store';return response
    require(request.method=='POST','请求方法不支持');data=body(request)
    require(set(data)<= {'revision','kind','entityId','bio','color'},'仅可修改简介和代表色')
    if data.get('revision')!=e.revision:return JsonResponse({'error':'资料已更新，请刷新后重试'},status=409)
    kind=data.get('kind');require(kind in ['team','player'],'资料对象错误')
    permitted(e,request.user,kind,data.get('entityId'))
    before=copy.deepcopy(e.document)
    if e.document.get('historySnapshot') and not e.document.get('historyCurrent'):e.document['historyCurrent']=copy.deepcopy(e.document['historySnapshot'])
    d=source(e);row=find(d['teams' if kind=='team' else 'players'],data['entityId'])
    bio=data.get('bio','');require(isinstance(bio,str) and len(bio)<=500,'简介最多500字');row['bio']=bio.strip()
    if kind=='team' and 'color' in data:
        import re
        color=data['color'];require(isinstance(color,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',color),'代表色格式错误')
        require(not any(t['id']!=row['id'] and t['color'].lower()==color.lower() for t in d['teams']),'代表色已被其他队伍使用')
        row['color']=color
    e.revision+=1;e.save(update_fields=['document','revision'])
    Audit.objects.create(event=e,actor=request.user,revision=e.revision,action='team-profile',before={'document':before},after={'document':e.document})
    return JsonResponse({'revision':e.revision})
