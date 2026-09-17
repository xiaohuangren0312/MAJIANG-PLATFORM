from .domain import optional_note
"""Final standings snapshot and isolated, backed-up test tournament cleanup."""
import copy,json,hashlib
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .domain import require,label,eligible_ids
from .projection import statistics,public_event
from .models import Event,Audit,HistoryImport,EventCleanup

def archive_preview(event):
    d=event.document
    require(not d.get('historySnapshot'),'历史导入赛事保留原表归档，本流程用于新建赛事')
    require(not d.get('archive'),'赛事已归档')
    require(bool(d['stages']),'请先创建比赛阶段')
    require(all(s.get('locked') for s in d['stages'][:-1]),'请先完成此前各阶段结算')
    require(not any(m['state']=='draft' for m in d['matches']),'还有未发布或未取消的对局')
    final=d['stages'][-1];kind='team' if event.kind=='team' else 'player'
    eligible=eligible_ids(d,event.kind,final['id'])
    rows=[r for r in statistics(d,final['id'],True,kind) if r['id'] in eligible and r['games']>0]
    require(bool(rows),'最后阶段没有已发布成绩')
    for i,row in enumerate(rows):row['rank']=rows[i-1]['rank'] if i and rows[i-1]['total']==row['total'] else i+1
    return dict(stageId=final['id'],stageName=final['name'],kind=kind,rows=rows,matches=sum(m['state']=='published' for m in d['matches']),personalOverall=statistics(d,'all',False,'player'))

def archive_event(event,reason,actor):
    preview=archive_preview(event);d=copy.deepcopy(event.document)
    payload=public_event(event);at=timezone.now().isoformat()
    payload.update(archived=True,archivedAt=at,finalStandings=copy.deepcopy(preview))
    for stage in d['stages']:stage['locked']=True
    d['archive']=dict(at=at,actor=actor,reason=optional_note(reason),standings=preview,publicPayload=payload)
    from .archive_export import csv_text
    d['archive']['csvExport']=csv_text(d,event.name,event.kind)
    return d

def cleanup_preview(event):
    require(event.is_test,'仅允许清理创建时标记的测试赛事')
    require(not event.document.get('historySnapshot') and not HistoryImport.objects.filter(event=event).exists(),'历史导入赛事不可清理')
    require(bool(event.document.get('archive')),'请先结束并归档测试赛事')
    require(not event.draft_activities.exists(),'赛事仍关联选人活动，请先在选人活动页面结束并解除关联；选人审计会保留')
    d=event.document
    return dict(eventId=str(event.pk),name=event.name,counts=dict(teams=len(d['teams']),players=len(d['players']),matches=len(d['matches']),audits=Audit.objects.filter(event=event).count()),public=event.public)

def cleanup_event(event_id,revision,name,reason,actor):
    with transaction.atomic():
        e=Event.objects.select_for_update().get(pk=event_id)
        require(e.revision==revision,'清理预览已过期，请重新预览')
        preview=cleanup_preview(e);require(name==e.name,'请输入完整赛事名称确认清理');reason=optional_note(reason)
        audits=list(Audit.objects.filter(event=e).order_by('revision').values())
        backup=dict(event=dict(id=str(e.pk),name=e.name,kind=e.kind,public=e.public,isTest=e.is_test,revision=e.revision,document=e.document,editors=list(e.editors.values_list('pk',flat=True))),audits=audits)
        raw=json.dumps(backup,ensure_ascii=False,default=str,sort_keys=True).encode()
        folder=settings.ENV_ROOT/'backups'/'test-cleanup';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(str(e.pk)+'-r'+str(e.revision)+'.json')
        # Complete a durable backup before removing active rows; failed writes abort deletion.
        import os
        with path.open('wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        path.chmod(0o600)
        EventCleanup.objects.create(event_id=e.pk,event_name=e.name,actor=actor,reason=reason,backup_path=str(path),backup_sha256=hashlib.sha256(raw).hexdigest(),counts=preview['counts'])
        Audit.objects.filter(event=e).delete();e.delete()
    return preview
