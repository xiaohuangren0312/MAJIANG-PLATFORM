from .roles import venue_admin
"""Read-only, manager-scoped lineup poster data. Never publishes a lineup."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Event
from .views import api, allowed
from .permissions import role_for
from .coach_lineups import visible

def response(data):
    r=JsonResponse(data)
    r["Cache-Control"]="private, no-store"
    return r

@login_required
@require_GET
@never_cache
def page(request):
    if not venue_admin(request.user) and not allowed(request.user).exists():
        raise PermissionDenied("仅赛事管理员可生成海报")
    return render(request,"posters.html")

@api
@require_GET
def events(request):
    return response({"events":[{"id":str(e.pk),"name":e.name} for e in allowed(request.user).order_by("-created_at")]})

@api
@require_GET
def detail(request,id):
    e=get_object_or_404(Event,pk=id)
    role_for(e,request.user)
    d=e.document
    # Archived revisions must keep the last published lineup snapshot.
    snapshot=next((d[k].get("publicPayload") for k in ("archiveRevision","archive") if d.get(k)),None)
    if snapshot is None and d.get("historySnapshot"):
        snapshot=d.get("historyCurrent",d["historySnapshot"])
    source=snapshot or d
    teams={t["id"]:t for t in source.get("teams",[])}
    players={p["id"]:p for p in source.get("players",[])}
    stages={s["id"]:s["name"] for s in source.get("stages",[])}
    matches=sorted(source.get("schedule" if snapshot is not None else "matches",[]),key=lambda m:(m["date"],m["time"],m.get("number",0),m["id"]))
    counts={};rows=[]
    for m in matches:
        if m["state"]=="cancelled":continue
        key=(m["date"],m.get("stageId"),str(m.get("table",m.get("number",1))))
        counts[key]=counts.get(key,0)+1
        seats=m.get("players",[]) if snapshot is not None else m.get("seats",[])
        roster=[];private=False
        known=bool(m.get('seatDraw') or m['state']=='published') if snapshot is None else (m.get('seatOrderKnown') is not False and len(seats)==4 and {s.get('wind') for s in seats}==set('东南西北'))
        resources=m.get('resources',{}) if snapshot is not None else d.get('matchResources',{}).get(m['id'],m.get('resources',{}))
        for i,s in enumerate(seats):
            player=players.get(s.get("playerId"));team=teams.get(s.get("teamId"),{})
            disclosed=bool(s.get("lineupPublished",m.get("lineupPublished",False)) or m["state"]=="completed") if snapshot is not None else visible(d,m,s)
            private=private or bool(player and not disclosed)
            roster.append({"wind":(s.get("wind") if snapshot is not None else "东南西北"[i]) if known and i<4 else None,"name":player["name"] if player else "待定","playerId":player["id"] if player else None,"imageUrl":(player or {}).get("imageUrl") or "/assets/player-default.png","teamName":team.get("name",""),"color":team.get("color","")})
        rows.append({"id":m["id"],"date":m["date"],"time":m["time"],"table":str(m.get("table",m.get("number",1))),"stageName":stages.get(m.get("stageId"),""),"game":counts[key],"players":sorted(roster,key=lambda p:"东南西北".index(p["wind"]) if p["wind"] else 4),"seatOrderKnown":known,"commentators":resources.get("commentators",[]),"private":private,"complete":len(roster)==4 and all(r["playerId"] for r in roster)})
    return response({"id":str(e.pk),"name":e.name,"revision":e.revision,"matches":rows})


@api
@require_GET
def daily(request,id):
    from .projection import public_event
    from .domain import require
    from datetime import date
    e=get_object_or_404(Event,pk=id)
    role_for(e,request.user)
    payload=public_event(e)
    days=sorted(set(m['date'] for m in payload.get('results',[])))
    selected=request.GET.get('date') or (days[-1] if days else date.today().isoformat())
    try: date.fromisoformat(selected)
    except (ValueError,TypeError): require(False,'请选择有效日期')
    results=payload.get('results',[])
    today=[m for m in results if m['date']==selected]
    team_details={t['id']:t for t in payload.get('teams',[])}
    teams={k:v['name'] for k,v in team_details.items()}
    player_details={p['id']:p for p in payload.get('players',[])}
    players={p['id']:p['name'] for p in payload.get('players',[])}
    matches=[]
    for m in today:
        matches.append(dict(commentators=m.get('resources',{}).get('commentators',[]),id=m['id'],time=m.get('time',''),table=m.get('table',m.get('number','')),stageId=m['stageId'],seats=[dict(name=players.get(s.get('playerId'),'未知选手'),team=teams.get(s.get('teamId'),''),wind=s.get('wind') if s.get('wind') and s.get('wind') in '东南西北' else None,rank=s.get('rank'),score=s.get('score'),points=s.get('points'),teamImageUrl=team_details.get(s.get('teamId'),{}).get('imageUrl'),teamColor=team_details.get(s.get('teamId'),{}).get('color')) for s in sorted(m.get('seats',[]),key=lambda s:'东南西北'.index(s['wind']) if s.get('wind') and s.get('wind') in '东南西北' else 4)]))
    stages=[]
    kind='team' if e.kind=='team' else 'player'
    key='teamPoints' if kind=='team' else 'points'
    for stage in payload.get('stages',[]):
        sid=stage['id']
        if not any(m['stageId']==sid for m in today):continue
        rows=payload.get('statistics',{}).get(sid,{}).get('competitive',{}).get(kind,[])
        records=[s|{'date':m['date']} for m in results if m['stageId']==sid for s in m.get('seats',[])]
        # Count distinct half-games per team, not seats or the event-wide total.
        # Public results alone determine games played by the report date.
        stage_results=[m for m in results if m['stageId']==sid]
        stage_schedule=[m for m in payload.get('schedule',[]) if m.get('stageId')==sid and m.get('state')!='cancelled']
        board=[];complete=bool(rows)
        for r in rows:
            seats=[s for s in records if s.get(kind+'Id')==r['id']]
            if any(not isinstance(s.get(key),(int,float)) for s in seats) or sum(s.get(key,0) for s in seats)!=r.get('raw'):
                complete=False;break
            prior=r.get('carry',0)+sum(s[key] for s in seats if s['date']<selected)
            change=sum(s[key] for s in seats if s['date']==selected)
            entity=(team_details if kind=='team' else player_details).get(r['id'],{})
            progress={}
            if kind=='team':
                played={m['id'] for m in stage_results if m['date']<=selected and any(s.get('teamId')==r['id'] for s in m.get('seats',[]))}
                planned={m.get('resultId') or m['id'] for m in stage_schedule if any(s.get('teamId')==r['id'] for s in m.get('players',[]))}
                planned.update(m['id'] for m in stage_results if any(s.get('teamId')==r['id'] for s in m.get('seats',[])))
                progress=dict(playedGames=len(played),stageGames=len(planned) if stage_schedule else None)
            board.append(dict(**progress,id=r['id'],name=r['name'],before=prior,delta=change,total=prior+change,imageUrl=entity.get('imageUrl'),color=entity.get('color')))
        if complete:
            for field,label in [('before','beforeRank'),('total','rank')]:
                ordered=sorted(board,key=lambda r:-r[field])
                for i,r in enumerate(ordered):r[label]=ordered[i-1][label] if i and r[field]==ordered[i-1][field] else i+1
            board.sort(key=lambda r:(r['rank'],r['name']))
        else:board=[]
        stages.append(dict(name=stage['name'],id=sid,advanceCount=stage.get('advanceCount',0),rows=board,notice='' if complete else '历史记录不完整，暂不展示排名变动'))
    return response(dict(id=str(e.pk),name=payload.get('name',e.name),date=selected,days=days,matches=matches,stages=stages,kind=kind))
