"""Private draft roster and atomic final import; snapshots never reach public projection."""
import copy
from league.domain import require
from league.models import Audit

def staged(activity):
    return '_roster' in activity.document

def working(activity):
    return activity.document.get('_roster',activity.event.document)

def check_baseline(activity):
    base=activity.document['_baseline']
    require(activity.event.document==base['document'] and activity.event.revision==base['revision'],'原赛事已被修改，请先核对后再导入；不会覆盖外部修改')

def write_event(activity,user,document,action):
    event=activity.event
    before=copy.deepcopy(event.document)
    event.document=copy.deepcopy(document);event.revision+=1
    event.save(update_fields=['document','revision'])
    Audit.objects.create(event=event,actor=user,revision=event.revision,action=action,before=before,after=event.document)

def restore_working(activity,previous):
    baseline=copy.deepcopy(activity.document['_baseline'])
    restored=copy.deepcopy(previous['document'])
    restored['_roster']=copy.deepcopy(restored.get('_roster',previous['eventDocument']))
    restored['_baseline']=baseline
    restored.pop('_import',None)
    activity.document=restored;activity.status=previous['status']

def import_roster(activity,user):
    check_baseline(activity)
    before=copy.deepcopy(activity.event.document)
    write_event(activity,user,working(activity),'draft-import')
    activity.document['_import']=dict(before=before,after=copy.deepcopy(activity.event.document),revision=activity.event.revision)

def import_rollback_review(activity):
    require(activity.status=='complete' and staged(activity) and activity.document.get('_import'),'没有可回滚的整批导入')
    record=activity.document['_import'];event=activity.event
    require(event is not None,'赛事已解除关联')
    require(event.document==record['after'] and event.revision==record['revision'],'导入后原赛事已修改，不能直接回滚覆盖')
    require(not event.document.get('archive') and not event.document.get('archiveRevision') and not any(m.get('state')!='cancelled' for m in event.document.get('matches',[])),'赛事已安排比赛或归档，不能回滚导入')
    old={p['id']:p for p in record['before']['players']}
    changes=[dict(player=p['name'],fromTeam=p.get('teamId'),toTeam=old.get(p['id'],{}).get('teamId')) for p in event.document['players'] if p.get('teamId')!=old.get(p['id'],{}).get('teamId')]
    return dict(operation='rollback-import',action='rollback-import',phase='review-ready',rosterChanges=changes,balances=[dict(teamId=t['teamId'],balance=t['balance']) for t in activity.document['teams']],message='一次性恢复导入前的原赛事名单；大会内选人结果与金额保留，返回最终检查，可修改后重新导入。')

def rollback_import(activity,user):
    import_rollback_review(activity)
    write_event(activity,user,activity.document['_import']['before'],'draft-import-rollback')
    activity.document['_baseline']=dict(document=copy.deepcopy(activity.event.document),revision=activity.event.revision)
    for key in ['_import','completion','eventSnapshot','eventIdentity']:activity.document.pop(key,None)
    activity.document['phase']='review-ready';activity.document.pop('lot',None);activity.status='active'


def enable_staging(activity,user):
    """Convert an active legacy activity without discarding its selection results.

    Caller must hold both activity and event locks in a transaction.
    """
    from .models import DraftAudit
    from .services import snapshot
    require(activity.status=='active' and not staged(activity),'仅转换进行中的旧版活动')
    event=activity.event
    require(event is not None and not event.document.get('archive') and not event.document.get('archiveRevision') and not any(m.get('state')!='cancelled' for m in event.document.get('matches',[])),'赛事已安排比赛或归档，不能转换')
    latest=DraftAudit.objects.filter(activity=activity).order_by('-revision').first()
    require(latest and latest.after.get('eventRevision')==event.revision and latest.after.get('eventDocument')==event.document,'赛事有外部修改，请先核对')
    start=DraftAudit.objects.filter(activity=activity,action='start').order_by('revision').first()
    require(start and start.before.get('eventId')==str(event.pk),'缺少选人开始前的原赛事快照')
    old={p['id']:p for p in start.before['eventDocument']['players']}
    roster=copy.deepcopy(event.document);baseline=copy.deepcopy(event.document)
    ids={c['playerId'] for c in activity.document['candidates']}|{t['coachPlayerId'] for t in activity.document['teams']}
    require(ids.issubset(old),'选手名单与原始快照不一致')
    before=snapshot(activity)
    for p in baseline['players']:
        if p['id'] not in ids:continue
        for key in ['teamId','nonPlayingCoach']:
            if key in old[p['id']]:p[key]=copy.deepcopy(old[p['id']][key])
            else:p.pop(key,None)
    write_event(activity,user,baseline,'draft-enable-staging')
    activity.document['_roster']=roster
    activity.document['_baseline']=dict(document=copy.deepcopy(baseline),revision=event.revision)
    activity.revision+=1;activity.save(update_fields=['document','revision'])
    DraftAudit.objects.create(activity=activity,actor=user,revision=activity.revision,action='enable-staging',before=before,after=snapshot(activity))
