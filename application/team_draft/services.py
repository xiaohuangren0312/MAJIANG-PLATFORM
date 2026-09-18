"""Django adapter: independent activity storage with atomic event roster writes."""
import copy
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.core import signing
from league.models import Event, Audit
from league.domain import require, label
from .models import DraftActivity, DraftAudit
from .history import validate_links, candidate_history, history_options
from .domain import configuration, first_pick, auction, AUCTION_ACTIONS


def event_manager(event, user):
    return bool(user.is_authenticated and user.is_active and (user.is_superuser or event.editors.filter(pk=user.pk).exists()))


def manager(activity, user):
    if not user.is_authenticated or not user.is_active: return False
    if activity.event_id: return event_manager(activity.event, user)
    return user.is_superuser or (activity.creator_id == user.pk and Event.objects.filter(editors=user).exists())


def own_team(activity, user):
    if not user.is_authenticated or not user.is_active: return None
    if activity.event_id and (activity.event.document.get('archive') or activity.event.document.get('archiveRevision')):return None
    if activity.event_id and activity.event.document.get('coachAccounts',{}).get(str(user.pk),{}).get('active') is False:return None
    return next((r['teamId'] for r in activity.document.get('teams', []) if r['coachUserId'] == user.pk), None)


def authorize(activity, user):
    if not manager(activity, user): raise PermissionDenied('当前账号无权管理此选人活动')


def snapshot(activity):
    return dict(name=activity.name, eventId=str(activity.event_id) if activity.event_id else None, status=activity.status, document=copy.deepcopy(activity.document), eventRevision=activity.event.revision if activity.event_id else None, eventDocument=copy.deepcopy(activity.event.document) if activity.event_id else None)


def eligible_event(event, user):
    if not event_manager(event, user): raise PermissionDenied('未获得关联赛事管理授权')
    require(event.kind == 'team' and not event.document.get('archive') and not event.document.get('archiveRevision') and not event.document.get('historySnapshot'), '请选择未归档的普通团体赛事')
    require(not any(m.get('state') != 'cancelled' for m in event.document.get('matches', [])), '请关联尚未安排比赛的赛事')


@transaction.atomic
def create(user, name):
    if not user.is_authenticated or not user.is_active or not (user.is_superuser or Event.objects.filter(editors=user).exists()):
        raise PermissionDenied('只有管理员可以创建选人活动')
    activity=DraftActivity.objects.create(name=label(name), creator=user)
    DraftAudit.objects.create(activity=activity, actor=user, revision=1, action='create', before={}, after=snapshot(activity))
    return activity


@transaction.atomic
def mutate(activity_id, user, revision, action, payload):
    # All plugin writes lock activity first, followed by the linked event.
    activity=DraftActivity.objects.select_for_update().get(pk=activity_id)
    require(type(revision) is int and revision == activity.revision, '活动已更新，请刷新后重试')
    if action in {'nominate', 'bid', 'pass'}:
        tid=own_team(activity,user);require(tid is not None,'当前账号不是本活动教练')
    else: authorize(activity,user);tid=None
    if activity.event_id:
        activity.event=Event.objects.select_for_update().get(pk=activity.event_id)
        if action in {'nominate','bid','pass'}:
            tid=own_team(activity,user);require(tid is not None,'当前账号不是本活动启用的教练')
        else:authorize(activity,user)
    if activity.event_id:
        require(user.is_superuser or not (activity.event.document.get('archive') or activity.event.document.get('archiveRevision')), '赛事已归档，只有总管理员可以修改')
    before=snapshot(activity)
    require(activity.status != 'complete' or action in {'publish','unlink'}, '活动已结束，选人记录只读')
    if action in {'finish','undo','unlink','publish'}:
        from .lifecycle import apply_control
        apply_control(activity,user,action,payload)
        activity.revision+=1
        activity.save(update_fields=['event','document','status','revision'])
        DraftAudit.objects.create(activity=activity,actor=user,revision=activity.revision,action=action,before=before,after=snapshot(activity))
        return activity
    if action == 'link':
        require(activity.status == 'setup', '选人已开始，关联赛事已锁定')
        event_id=payload.get('eventId')
        require(event_id, '请手动选择关联赛事')
        event=Event.objects.select_for_update().get(pk=event_id)
        eligible_event(event,user)
        require(not DraftActivity.objects.filter(event=event,status__in=['setup','active']).exclude(pk=activity.pk).exists(), '该赛事已有未结束的选人活动')
        if activity.event_id != event.pk:
            activity.event=event
            activity.document={}
    else:
        require(activity.event_id is not None, '请先关联赛事')
        event=Event.objects.select_for_update().get(pk=activity.event_id)
        if action not in {'nominate', 'bid', 'pass'}: eligible_event(event,user)
        doc=copy.deepcopy(event.document)
        if activity.document.get('phase'): doc['draft']=copy.deepcopy(activity.document)
        if action == 'configure':
            require(activity.status == 'setup', '选人开始后不可修改配置')
            result=configuration(doc,event.kind,payload)
            result['draft']['historyLinks']=validate_links(payload.get('candidates',[]),user)
            ids={r['coachUserId'] for r in result['draft']['teams']}
            require(set(get_user_model().objects.filter(pk__in=ids,is_active=True).values_list('pk',flat=True))==ids, '教练账号不存在或已停用')
        else:
            if action == 'start':
                ids={r['coachUserId'] for r in activity.document.get('teams',[])}
                require(set(get_user_model().objects.filter(pk__in=ids,is_active=True).values_list('pk',flat=True))==ids, '教练账号已停用，请重新配置')
            result=(auction if action in AUCTION_ACTIONS else first_pick)(doc,action,payload,tid)
        visibility=activity.document.get('public',False)
        activity.document=result.pop('draft')
        activity.document['public']=visibility
        if activity.document['phase'] != 'setup': activity.status='active'
        # Draft state remains exclusively in plugin tables; only changed roster is synchronized.
        if result != event.document:
            changed=Event.objects.filter(pk=event.pk,revision=event.revision).update(document=result,revision=F('revision')+1)
            require(changed==1,'赛事名单已更新，请刷新后重试')
            Audit.objects.create(event=event,actor=user,revision=event.revision+1,action='draft-roster',before=event.document,after=result)
            event.refresh_from_db()
        activity.event=event
    activity.revision+=1
    activity.save(update_fields=['event','document','status','revision'])
    DraftAudit.objects.create(activity=activity,actor=user,revision=activity.revision,action=action,before=before,after=snapshot(activity))
    return activity


def projection(activity,user):
    admin=manager(activity,user);own=own_team(activity,user)
    if not admin and not own and not activity.document.get('public',False): raise PermissionDenied('此活动未公开，请使用获授权的管理员或教练账号登录')
    draft=copy.deepcopy(activity.document) if activity.document.get('phase') else None
    if draft:
        draft.pop('eventSnapshot',None)
        draft.pop('eventIdentity',None)
        choices=draft.pop('nominations',{})
        draft['submitted']=list(choices);draft['myPick']=choices.get(own)
        if admin:
            accounts=dict(get_user_model().objects.filter(pk__in=[r['coachUserId'] for r in draft['teams']]).values_list('pk','username'))
            for row in draft['teams']:row['coachUsername']=accounts.get(row['coachUserId'],'')
        else:
            for row in draft['teams']:row.pop('coachUserId',None)
    event=activity.event
    doc=activity.document.get('eventSnapshot',{}) if activity.status=='complete' or not event else event.document
    return dict(history=candidate_history(activity.document),historyOptions=history_options() if admin and activity.status=='setup' else [],public=activity.document.get('public',False), id=str(activity.pk),name=activity.name,revision=activity.revision,status=activity.status,eventId=str(event.pk) if event else None,eventName=event.name if event else activity.document.get('eventIdentity',{}).get('name'),manager=admin,myTeam=own,draft=draft,players=[dict(id=p['id'],name=p['name'],teamId=p.get('teamId'),active=p.get('active',True),bond=p.get('bond',False)) for p in doc.get('players',[])],teams=[dict(id=t['id'],name=t['name'],active=t.get('active',True),logo=t.get('imageUrl')) for t in doc.get('teams',[])])
