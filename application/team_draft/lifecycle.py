"""Conservative, signed lifecycle operations; selection completion is not event archival."""
import copy
from django.core import signing
from django.db import transaction
from league.domain import require, find
from league.models import Event, Audit
from .models import DraftActivity, DraftAudit
from .roster import staged, working, check_baseline, restore_working, import_roster, import_rollback_review, rollback_import

UNDO_ACTIONS={'configure','start','nominate','admin-nominate','reveal','roll','continue','draw','draw-third','open-bidding','bid','pass','confirm-lot','assign-third','assign-second','admin-third','mark-unsold','edit-candidates','next-lot'}

def finish_review(activity):
    d=activity.document
    require(activity.status=='active','只有进行中的活动可以结束')
    require(d.get('phase') in {'auction-ready','third-ready','review-ready'} or (d.get('phase')=='auction' and (d.get('lot',{}).get('state')=='settled' or (d.get('lot',{}).get('state') in {'preview','awaiting-confirm'} and not d.get('lot',{}).get('leader')))),'请先完成当前一选或竞拍，再检查结束')
    event=activity.event
    require(event is not None,'活动未关联赛事')
    if staged(activity):check_baseline(activity)
    doc=working(activity)
    require(not doc.get('archive') and not any(m.get('state')!='cancelled' for m in doc.get('matches',[])),'赛事已安排比赛或归档，请先核对选人状态')
    rows=[]
    for t in d['teams']:
        team=find(doc['teams'],t['teamId'])
        require(team.get('active',True),'队伍已停用，请先核对')
        members=[p for p in doc['players'] if p.get('teamId')==t['teamId'] and not p.get('bond')]
        require(len(members)<=t['capacity'],'名单超过人数上限')
        require(any(p['id']==t['coachPlayerId'] for p in members),'教练归属已变化，请先核对')
        expected=t['budget']-t['coachPrice']-sum(a['price'] for a in d['allocations'] if a['teamId']==t['teamId'])
        require(t['balance']==expected and expected>=0,'预算记录不一致，请先核对')
        rows.append(dict(teamId=t['teamId'],name=team['name'],members=[p['name'] for p in members],count=len(members),capacity=t['capacity'],balance=t['balance']))
    ids=[]
    for allocation in d['allocations']:
        player=find(doc['players'],allocation['playerId'])
        require(player.get('teamId')==allocation['teamId'] and player.get('active',True) and not player.get('bond'),'已选队员归属或状态被外部修改，请先核对')
        ids.append(player['id'])
    require(len(ids)==len(set(ids)),'发现重复入队记录')
    remaining=[]
    for c in d['candidates']:
        p=find(doc['players'],c['playerId'])
        if c['state']=='allocated':
            require(c['playerId'] in ids,'候选和成交记录不一致')
        else:
            require(not p.get('teamId') and p.get('active',True) and not p.get('bond'),'未分派候选已被外部修改，请先核对')
            remaining.append(dict(playerId=p['id'],name=p['name']))
    require(not remaining or all(r['count']==r['capacity'] for r in rows),'仍有候选且队伍有空位，请完成第三轮分派；无有效报价时允许以0点分派')
    vacancies=sum(t['capacity']-t['count'] for t in rows)
    return dict(operation='finish',teams=rows,unassigned=remaining,vacancies=vacancies,message=('确认后一次性导入原赛事队伍，可整批回滚导入。' if staged(activity) else '仅结束选人活动，不归档赛事。')+('所有名额已满，以下候选保持未分队。' if remaining else '全部候选已处理。')+(f' 队伍合计仍缺{vacancies}人，请核对后再结束。' if vacancies else ''))

def undo_review(activity):
    require(activity.status!='complete','已结束活动只读，不能撤销')
    audit=DraftAudit.objects.filter(activity=activity).order_by('-revision').first()
    require(audit is not None and audit.action in UNDO_ACTIONS,'当前最后一步不支持撤销；只能撤销最近一次选人操作')
    before=audit.before;after=audit.after
    require('eventDocument' in before and 'eventDocument' in after,'此旧操作没有完整恢复快照，不能安全撤销')
    require(after['eventId']==str(activity.event_id) and before['eventId']==after['eventId'],'关联已变化，不能撤销')
    event=activity.event
    require(event.revision==after['eventRevision'] and event.document==after['eventDocument'],'赛事有外部变更或后续依赖，不能撤销；请先核对名单')
    require(not event.document.get('archive') and not any(m.get('state')!='cancelled' for m in event.document.get('matches',[])),'赛事已安排比赛或归档，不能撤销')
    changes=[]
    old={p['id']:p for p in before['document'].get('_roster',before['eventDocument']).get('players',[])}
    for p in after['document'].get('_roster',after['eventDocument']).get('players',[]):
        if p.get('teamId')!=old.get(p['id'],{}).get('teamId'):
            changes.append(dict(player=p['name'],fromTeam=p.get('teamId'),toTeam=old.get(p['id'],{}).get('teamId')))
    balances=[dict(teamId=t['teamId'],balance=t['balance']) for t in before['document'].get('teams',[])]
    return dict(operation='undo',action=audit.action,auditRevision=audit.revision,rosterChanges=changes,balances=balances,phase=before['document'].get('phase','setup'),message='只撤销最后一次操作；保留审计，不支持连续回退或回退历史步骤。')


def stage(document):
    phase=document.get('phase','setup')
    if phase=='setup':return 0
    if phase in {'nomination','revealed'}:return 1
    if phase=='auction-ready' or (phase=='auction' and document.get('lot',{}).get('stage',2)==2):return 2
    if phase in {'third-ready','auction','review-ready'}:return 3
    return 4

def rollback_snapshot(activity):
    require(activity.event_id is not None,'活动未关联赛事')
    event=activity.event
    require(not event.document.get('archive') and not event.document.get('archiveRevision') and not any(m.get('state')!='cancelled' for m in event.document.get('matches',[])),'赛事已安排比赛或归档，不能回退')
    audits=list(DraftAudit.objects.filter(activity=activity).order_by('-revision'))
    require(audits and audits[0].after.get('eventDocument')==event.document and audits[0].after.get('eventRevision')==event.revision,'赛事已被外部修改，请先核对名单')
    require(not(staged(activity) and activity.status=='complete'),'请先回滚导入，再回退选人阶段')
    current=stage(activity.document);limit=activity.revision
    for audit in audits:
        if audit.revision>limit:continue
        if audit.action=='rollback':
            limit=audit.after['document']['rollbackSourceRevision']-1
            continue
        if audit.action=='undo':
            limit=audit.revision-2
            continue
        before=audit.before
        if before.get('eventId')!=str(activity.event_id):break
        if before.get('document',{}).get('phase') and stage(before['document'])<current:
            return audit,before
    require(False,'没有可安全回退的上一阶段快照')

def rollback_review(activity):
    audit,before=rollback_snapshot(activity)
    old={p['id']:p for p in before['document'].get('_roster',before['eventDocument'])['players']}
    changes=[dict(player=p['name'],fromTeam=p.get('teamId'),toTeam=old.get(p['id'],{}).get('teamId')) for p in working(activity)['players'] if p.get('teamId')!=old.get(p['id'],{}).get('teamId')]
    return dict(operation='rollback',action='rollback',phase=before['document']['phase'],rosterChanges=changes,balances=[dict(teamId=t['teamId'],balance=t['balance']) for t in before['document']['teams']],message='回退到上一阶段结束时的状态，撤销其后的指名、竞拍和分配，恢复队伍归属及余额；保留最新选手定价、介绍和审计记录。')

@transaction.atomic
def preview(activity_id,user,revision,operation):
    from .services import authorize
    a=DraftActivity.objects.select_for_update().get(pk=activity_id)
    authorize(a,user)
    require(type(revision)is int and a.revision==revision,'活动已更新，请刷新后重新预览')
    if a.event_id:a.event=Event.objects.select_for_update().get(pk=a.event_id)
    require(operation in {'finish','undo','rollback','rollback-import'},'未知预览操作')
    result=({'finish':finish_review,'undo':undo_review,'rollback':rollback_review,'rollback-import':import_rollback_review}[operation])(a)
    result['token']=signing.dumps(dict(id=str(a.pk),revision=a.revision,eventRevision=a.event.revision,operation=operation,user=user.pk),salt='draft-control')
    return result

def apply_control(activity,user,action,payload):
    if action=='publish':
        require(type(payload.get('public'))is bool,'公开状态格式错误')
        activity.document['public']=payload['public']
        return
    if action=='unlink':
        require(activity.status in {'setup','complete'},'进行中的活动不能解除关联，请先结束')
        require(activity.event_id is not None,'活动尚未关联赛事')
        activity.document['eventIdentity']=dict(id=str(activity.event_id),name=activity.event.name)
        if activity.status!='complete':activity.document['eventSnapshot']=copy.deepcopy(activity.event.document)
        activity.event=None
        if activity.status=='setup':activity.document={'public':False}
        return
    require(activity.event_id is not None,'活动已解除关联，请重新打开活动')
    token=signing.loads(payload.get('previewToken',''),salt='draft-control',max_age=1800)
    require(token==dict(id=str(activity.pk),revision=activity.revision,eventRevision=activity.event.revision,operation=action,user=user.pk),'预览已过期，请重新检查')
    if action=='finish':
        review=finish_review(activity)
        if staged(activity):import_roster(activity,user)
        activity.document['completion']=review
        activity.document['eventSnapshot']=copy.deepcopy(activity.event.document)
        activity.document['eventIdentity']=dict(id=str(activity.event_id),name=activity.event.name)
        activity.document['phase']='complete'
        activity.status='complete'
    elif action=='rollback-import':
        rollback_import(activity,user)
    elif action=='rollback':
        audit,previous=rollback_snapshot(activity)
        event=activity.event
        if not staged(activity):
            prior=copy.deepcopy(event.document)
            event.document=copy.deepcopy(previous['eventDocument'])
            event.revision+=1
            event.save(update_fields=['document','revision'])
            Audit.objects.create(event=event,actor=user,revision=event.revision,action='draft-rollback',before=prior,after=event.document)
        latest={c['playerId']:c for c in activity.document.get('candidates',[])}
        visibility=activity.document.get('public',False)
        if staged(activity):restore_working(activity,previous)
        else:activity.document=copy.deepcopy(previous['document'])
        for c in activity.document.get('candidates',[]):
            if c['playerId'] in latest:
                c.update({k:latest[c['playerId']][k] for k in ['startPrice','description']})
        activity.document.update(public=visibility,rollbackSourceRevision=audit.revision)
        activity.status=previous['status']
    elif action=='undo':
        undo_review(activity)
        audit=DraftAudit.objects.get(activity=activity,revision=activity.revision)
        previous=audit.before
        event=activity.event
        if not staged(activity) and event.document!=previous['eventDocument']:
            prior=copy.deepcopy(event.document)
            event.document=copy.deepcopy(previous['eventDocument'])
            event.revision+=1
            event.save(update_fields=['document','revision'])
            Audit.objects.create(event=event,actor=user,revision=event.revision,action='draft-undo',before=prior,after=event.document)
        if staged(activity):restore_working(activity,previous)
        else:activity.document=copy.deepcopy(previous['document'])
        activity.status=previous['status']
