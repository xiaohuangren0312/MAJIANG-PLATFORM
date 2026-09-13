"""Run via the development Python, after pg_dump. Default is a dry run."""
import os,sys,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','hql.settings')
import django
django.setup()
from django.db import transaction
from django.contrib.auth import get_user_model
from league.models import HistoricalArchive,HistoryImport,Audit
from league.history_reconciliation import reconcile,VERSION
from league.history_review import fingerprint,report
apply='--apply' in sys.argv
with transaction.atomic():
    for key in ['s2','s3']:
        archive=HistoricalArchive.objects.select_for_update().get(key=key)
        link=HistoryImport.objects.select_for_update().select_related('event').get(archive=archive)
        event=type(link.event).objects.select_for_update().get(pk=link.event_id)
        if archive.payload.get('reconciliation',{}).get('version')==VERSION:
            print(key,'already repaired');continue
        assert event.document['historySnapshot']==archive.payload,'source/event diverged'
        assert not event.document.get('historyCurrent'),'manual corrections need explicit merge'
        revised=reconcile(archive.payload)
        print(key,'teams',len(revised['teams']),'players',len(revised['players']),'grouped questions',len(report(revised)['issues']))
        if not apply:continue
        before=copy.deepcopy(event.document)
        document=copy.deepcopy(before)
        document.setdefault('historyOriginalSnapshot',copy.deepcopy(before['historySnapshot']))
        document['historySnapshot']=revised
        digest=fingerprint(revised)
        document['historySource']['fingerprint']=digest
        document['historySource']['repairReason']='用户统一确认三组别名合并、楠哥为银河蘸酱独立选手、2PT为迟到罚分及缺失字段保留未知；维护脚本批量应用。'
        event.document=document;event.revision+=1;event.save(update_fields=['document','revision'])
        Audit.objects.create(event=event,actor=get_user_model().objects.get(username='hql-admin'),revision=event.revision,action='history-import-repair',reason=document['historySource']['repairReason'],before=before,after=document)
        archive.payload=revised;archive.save(update_fields=['payload'])
        link.fingerprint=digest;link.save(update_fields=['fingerprint'])
if apply:
    # Keep bootstrap/demo regeneration consistent with the repaired source.
    path=Path('/data/majiang/dev/app/design/prototypes/public-v1/site/data.json')
    seed=json.loads(path.read_text())
    for i,item in enumerate(seed['tournaments']):
        if item['id'] in ['s2','s3']:seed['tournaments'][i]=HistoricalArchive.objects.get(key=item['id']).payload
    path.write_text(json.dumps(seed,ensure_ascii=False,indent=2))
