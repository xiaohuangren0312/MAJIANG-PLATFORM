"""Scoped coach lineups. Publication is clock-based, never dependent on a worker job."""
import copy, datetime
from zoneinfo import ZoneInfo
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Event, Audit
from .domain import require, find, live_stage, validate_lineup, validate_qualification
from .views import api, body

CST=ZoneInfo('Asia/Shanghai')
def start(m):
    return datetime.datetime.fromisoformat(m['date']+'T'+m['time']).replace(tzinfo=CST)
def release_at(d,m,entry):
    if entry.get('mode')=='default':
        matches=[x for x in d['matches'] if x['date']==m['date'] and x['state']!='cancelled']
        return min(start(x) for x in matches)-datetime.timedelta(hours=2)
    return min(datetime.datetime.fromisoformat(entry['publishAt']),start(m))
def visible(d,m,seat,now=None):
    if m['state']=='published' or m.get('lineupPublished'):return True
    entry=m.get('coachLineups',{}).get(seat.get('teamId'))
    return bool(entry and seat.get('playerId') and release_at(d,m,entry)<=(now or timezone.now()))
def manager(e,user):return user.is_superuser or e.editors.filter(pk=user.pk).exists()
def team_ids(e,user):
    if manager(e,user):return {t['id'] for t in e.document.get('teams',[])}
    account=e.document.get('coachAccounts',{}).get(str(user.pk))
    if account is not None:
        if not account.get('active',True):return set()
        if 'teamId' in account:return {account['teamId']} if account['teamId'] else set()
    # Existing linked draft coaches retain their assigned event team.
    return {t['teamId'] for a in e.draft_activities.all() for t in a.document.get('teams',[]) if t.get('coachUserId')==user.pk}
def writable(e):
    return e.kind=='team' and not any(e.document.get(k) for k in ['archive','archiveRevision','historySnapshot'])
def assigned_team(d,player,stage):
    return player.get('bondStages',{}).get(stage) if player.get('bond') else player.get('teamId')
def projection(e,user,now=None):
    now=now or timezone.now();d=e.document;ids=team_ids(e,user);rows=[]
    for m in sorted(d.get('matches',[]),key=lambda x:(x['date'],x['time'],x['number'])):
        if m['state']!='draft' or m['date']<now.astimezone(CST).date().isoformat():continue
        stage=find(d['stages'],m['stageId'])
        for seat in m['seats']:
            tid=seat['teamId']
            if tid not in ids:continue
            entry=m.get('coachLineups',{}).get(tid)
            options=[dict(id=p['id'],name=p['name'],bond=p.get('bond',False)) for p in d['players'] if p['active'] and assigned_team(d,p,m['stageId'])==tid]
            rows.append(dict(matchId=m['id'],teamId=tid,teamName=find(d['teams'],tid)['name'],date=m['date'],time=m['time'],number=m['number'],stageName=stage['name'],playerId=seat.get('playerId'),players=options,mode=(entry or {}).get('mode','default'),defaultPublishAt=release_at(d,m,{'mode':'default'}).isoformat(),publishAt=release_at(d,m,entry or {'mode':'default'}).isoformat(),published=bool(seat.get('playerId') and visible(d,m,seat,now)),scheduled=bool(entry),locked=bool(stage.get('locked') or start(m)<=now or any('score' in s for s in m['seats']) or m.get('penalties') or m.get('yakuman'))))
    return dict(id=str(e.pk),name=e.name,revision=e.revision,rows=rows)

@login_required
@ensure_csrf_cookie
def page(request):return render(request,'coach-lineups.html')

@api
def events(request):
    require(request.method=='GET','请求方法不支持')
    values=[dict(id=str(e.pk),name=e.name) for e in Event.objects.filter(kind='team').prefetch_related('editors','draft_activities') if writable(e) and team_ids(e,request.user)]
    response=JsonResponse({'events':values});response['Cache-Control']='no-store';return response

@api
@transaction.atomic
def detail(request,id):
    e=get_object_or_404(Event.objects.select_for_update(),pk=id)
    ids=team_ids(e,request.user)
    if not ids:raise PermissionDenied('仅可管理自己队伍的出战名单')
    require(writable(e),'该赛事目前不可安排出战名单')
    if request.method=='GET':
        response=JsonResponse(projection(e,request.user));response['Cache-Control']='no-store';return response
    require(request.method=='POST','请求方法不支持');b=body(request)
    if b.get('revision')!=e.revision:return JsonResponse({'error':'赛程或名单已更新，请刷新后重试'},status=409)
    rows=b.get('rows');require(isinstance(rows,list) and 0<len(rows)<=500,'请选择待保存的出战名单')
    old=copy.deepcopy(e.document);d=e.document;now=timezone.now();seen=set()
    for row in rows:
        require(isinstance(row,dict),'出战名单格式错误')
        tid=row.get('teamId')
        if tid not in ids:raise PermissionDenied('不能修改其他队伍的出战名单')
        m=find(d['matches'],row.get('matchId'));live_stage(d,m['stageId'])
        require((m['id'],tid) not in seen,'同场队伍名单重复');seen.add((m['id'],tid))
        require(m['state']=='draft' and start(m)>now,'本场已开赛、完赛或取消，不能修改')
        require(not any('score' in s for s in m['seats']) and not m.get('penalties') and not m.get('yakuman'),'本场已录入成绩或事件，请由赛事管理员处理')
        seat=next((s for s in m['seats'] if s['teamId']==tid),None);require(seat is not None,'本场没有该队伍')
        was_public=bool(seat.get('playerId') and visible(d,m,seat,now))
        if row.get('withdraw'):
            require(not was_public,'名单已公开，不能撤回；开赛前可更换选手')
            seat.clear();seat.update(teamId=tid,playerId=None);m.get('coachLineups',{}).pop(tid,None)
            continue
        pid=row.get('playerId');require(bool(pid),'请选择出战选手')
        seat.clear();seat.update(teamId=tid,playerId=pid)
        m['seats']=validate_lineup(d,'team',m['seats'],False,stage_id=m['stageId'])
        validate_qualification(d,'team',m['stageId'],m['seats'])
        # No player can occupy two tables at the same scheduled start.
        require(not any(x['id']!=m['id'] and x['state']!='cancelled' and (x['date'],x['time'])==(m['date'],m['time']) and any(s.get('playerId')==pid for s in x['seats']) for x in d['matches']),'选手同一时间已有其他出战安排')
        mode=row.get('mode','default');require(mode in ['default','custom'],'发布时间模式错误')
        entry={'mode':mode}
        if mode=='custom':
            try:
                value=datetime.datetime.fromisoformat(row.get('publishAt',''))
                if value.tzinfo is None:value=value.replace(tzinfo=CST)
            except (ValueError,TypeError):require(False,'发布时间格式错误')
            require(value<=start(m),'发布时间不能晚于本场开赛时间')
            entry['publishAt']=value.isoformat()
        if was_public:entry={'mode':'custom','publishAt':now.isoformat()}
        m.setdefault('coachLineups',{})[tid]=entry
    e.revision+=1;e.save(update_fields=['document','revision'])
    Audit.objects.create(event=e,actor=request.user,revision=e.revision,action='coach-lineup',before={'document':old},after={'document':d})
    response=JsonResponse(projection(e,request.user));response['Cache-Control']='no-store';return response
