import copy,json,tempfile,hashlib
from pathlib import Path
from django.conf import settings
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from .models import Event,Audit,EventCleanup,HistoricalArchive
from .domain import initial,apply,Invalid
from .lifecycle import archive_preview

class LifecycleTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.admin=User.objects.create_user(username='lifecycle-root',is_superuser=True)
        self.member=User.objects.create_user(username='lifecycle-manager')
        self.outside=User.objects.create_user(username='lifecycle-outside')
        self.tmp=self.enterContext(tempfile.TemporaryDirectory(dir=settings.ENV_ROOT/'tmp'))
        self.enterContext(override_settings(ENV_ROOT=Path(self.tmp)))
        self.client.force_login(self.admin)
        self.unrelated=Event.objects.create(name='Do not touch',kind='team',document=initial())
        self.archive=HistoricalArchive.objects.create(key='protected-fixture',payload={'id':'protected-fixture'})
    def create(self,kind='team',test=True):
        r=self.client.post('/api/events/',dict(name='生命周期验收',kind=kind,isTest=test),content_type='application/json')
        self.assertEqual(r.status_code,201,r.content);self.eid=r.json()['id'];self.url='/api/events/'+self.eid+'/'
        self.state=self.client.get(self.url).json()
    def command(self,action,expected=200,**data):
        r=self.client.post(self.url,dict(action=action,revision=self.state['revision'],**data),content_type='application/json')
        self.assertEqual(r.status_code,expected,r.content)
        if r.status_code==200 and not r.json().get('deleted'):self.state=self.client.get(self.url).json()
        return r.json()
    def setup_event(self,kind='team',test=True):
        self.create(kind,test)
        self.command('stage-update',id=self.state['document']['stages'][0]['id'],name='预选赛')
        self.command('stage',name='决赛')
        if kind=='team':
            for i in range(5):self.command('team',name='队伍'+str(i))
        for i in range(5):
            teams=self.state['document']['teams'];self.command('player',name='选手'+str(i),number=str(i),teamId=teams[i]['id'] if teams else None)
        d=self.state['document'];self.source=d['stages'][0]['id'];self.target=d['stages'][1]['id']
        self.seats=[dict(playerId=p['id'],teamId=p['teamId']) for p in d['players']]
        self.ids=[s['teamId' if kind=='team' else 'playerId'] for s in self.seats[:4]]
        return kind
    def match(self,stage,number=1,seats=None):
        seats=seats or self.seats[:4]
        self.command('match',stageId=stage,date='2026-09-09',number=number,time='19:30',seats=seats)
        return self.state['document']['matches'][-1]['id']
    def publish(self,mid,kind='team'):
        self.command('lineup',id=mid,seats=self.seats[:4])
        self.command('score',id=mid,scores=[40000,30000,20000,10000],penalties=[dict(playerId=self.seats[0]['playerId'],amount=20,scope='both' if kind=='team' else 'personal',explanation='迟到')],yakuman=[dict(playerId=self.seats[0]['playerId'],types=['国士无双'],multiplier=1,round='东一局',method='自摸')])
        self.command('publish',id=mid)
    def advance(self):
        p=self.command('settlement-preview',source=self.source,target=self.target,ids=self.ids)
        self.command('settlement-commit',token=p['token'],overrides={self.ids[0]:{'value':300,'reason':'验收手动带入30PT'}})
    def finish(self,kind='team'):
        self.setup_event(kind);self.publish(self.match(self.source),kind);self.advance();self.publish(self.match(self.target,2),kind)
        return self.command('archive-preview')
    def flow(self,kind):
        self.setup_event(kind)
        self.command('grant',username=self.member.username,role='admin',reason='验收授权')
        self.command('visibility',public=True)
        self.client.force_login(self.member)
        self.command('match',expected=400,stageId=self.target,date='2026-09-09',number=1,seats=self.seats[:4])
        mid=self.match(self.source,seats=[dict(teamId=s['teamId'],playerId=None) for s in self.seats[:4]] if kind=='team' else self.seats[:4])
        if kind=='team':
            payload=next(x for x in self.client.get('/data.json').json()['tournaments'] if x['id']==self.eid)
            self.assertTrue(all(s['playerId'] is None for s in payload['schedule'][0]['players']))
        self.publish(mid,kind)
        self.advance()
        self.command('score',expected=400,id=mid,scores=[25000]*4)
        self.command('match',expected=400,stageId=self.target,date='2026-09-09',number=2,seats=self.seats[1:])
        final=self.match(self.target,2);self.command('lineup',expected=400,id=final,seats=self.seats[1:]);self.publish(final,kind)
        p=self.command('archive-preview');self.assertEqual(len(p['preview']['rows']),4)
        self.assertEqual(p['preview']['rows'][0]['total'],880)
        self.command('archive-commit',token=p['token'],reason='')
        csv_response=self.client.get('/api/events/'+self.eid+'/archive.csv')
        self.assertEqual(csv_response.status_code,200)
        self.assertTrue(csv_response.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn('赛程与逐场战果',csv_response.content.decode('utf-8-sig'))
        self.client.force_login(self.outside)
        self.assertEqual(self.client.get('/api/events/'+self.eid+'/archive.csv').status_code,404)
        self.client.force_login(self.member)
        frozen=self.client.get('/data.json').json()
        event_payload=next(x for x in frozen['tournaments'] if x['id']==self.eid)
        self.assertTrue(event_payload['archived']);self.assertEqual(event_payload['finalStandings']['rows'],p['preview']['rows'])
        for action,body in [('rule',{}),('stage',{'name':'不应新增'}),('correct',{'id':final}),('settlement-preview',{}),('cleanup-preview',{})]:self.command(action,expected=403,**body)
        self.client.force_login(self.outside);self.assertEqual(self.client.get(self.url).status_code,404)
        self.assertEqual(self.client.post(self.url,dict(action='cleanup-preview',revision=self.state['revision']),content_type='application/json').status_code,404)
        self.client.force_login(self.admin)
        self.command('visibility',public=False);self.command('visibility',public=True)
        self.assertEqual(next(x for x in self.client.get('/data.json').json()['tournaments'] if x['id']==self.eid),event_payload)
        p=self.command('cleanup-preview');self.command('cleanup-commit',expected=400,token=p['token'],confirmName='错误名称',reason='清理')
        self.command('cleanup-commit',token=p['token'],confirmName='生命周期验收',reason='')
        self.assertFalse(Event.objects.filter(pk=self.eid).exists());self.assertFalse(Audit.objects.filter(event_id=self.eid).exists())
        self.assertFalse(Event.editors.through.objects.filter(event_id=self.eid).exists())
        receipt=EventCleanup.objects.get(event_id=self.eid);raw=Path(receipt.backup_path).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt.backup_sha256)
        self.assertTrue(json.loads(raw)['event']['document']['archive'])
        self.assertTrue(Event.objects.filter(pk=self.unrelated.pk).exists());self.assertTrue(HistoricalArchive.objects.filter(pk=self.archive.pk).exists())
        self.assertNotIn(self.eid,[x['id'] for x in self.client.get('/data.json').json()['tournaments']])
    def test_team_full_lifecycle(self):self.flow('team')
    def test_personal_full_lifecycle(self):self.flow('personal')
    def test_incomplete_cannot_archive(self):
        self.setup_event();self.command('archive-preview',expected=400)
        self.publish(self.match(self.source));self.command('archive-preview',expected=400)
        self.advance();self.match(self.target,2);self.command('archive-preview',expected=400)
    def test_only_test_events_cleanable_and_flag_cannot_be_changed(self):
        p=self.finish();self.command('archive-commit',token=p['token'],reason='完成')
        e=Event.objects.get(pk=self.eid);e.is_test=False;e.save(update_fields=['is_test']);self.state=self.client.get(self.url).json()
        self.command('cleanup-preview',expected=403)
        self.command('isTest',expected=403,isTest=True)
        e.refresh_from_db();self.assertFalse(e.is_test)
    def test_archive_tokens_are_revision_and_event_bound(self):
        p=self.finish();self.command('visibility',public=False)
        self.command('archive-commit',expected=400,token=p['token'],reason='过期')
        other=self.unrelated;other.document=copy.deepcopy(self.state['document']);other.revision=self.state['revision'];other.save()
        self.assertEqual(self.client.post('/api/events/'+str(other.id)+'/',dict(action='archive-commit',revision=other.revision,token=p['token'],reason='其他赛事'),content_type='application/json').status_code,400)
    def test_cleanup_token_stale_and_backup_failure_preserves_event(self):
        p=self.finish();self.command('archive-commit',token=p['token'],reason='完成')
        p=self.command('cleanup-preview');self.command('visibility',public=False)
        self.command('cleanup-commit',expected=400,token=p['token'],confirmName='生命周期验收',reason='过期')
        from unittest.mock import patch
        from .lifecycle import cleanup_event
        with patch('pathlib.Path.open',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):cleanup_event(self.eid,self.state['revision'],'生命周期验收','测试',self.admin)
        self.assertTrue(Event.objects.filter(pk=self.eid).exists());self.assertFalse(EventCleanup.objects.filter(event_id=self.eid).exists())
    def test_cleanup_requires_archive_and_rejects_history(self):
        self.create();self.command('cleanup-preview',expected=403)
        e=Event.objects.get(pk=self.eid);e.document.update(historySnapshot={},archive={'at':'fixture'});e.save()
        from .lifecycle import cleanup_preview
        e.document['historySnapshot']={'id':'s2'}
        with self.assertRaises(Invalid):cleanup_preview(e)

    def test_single_stage_final_rank_excludes_nonplayers(self):
        self.setup_event()
        e=Event.objects.get(pk=self.eid);e.document['stages']=e.document['stages'][:1];e.save()
        self.state=self.client.get(self.url).json();self.publish(self.match(self.source))
        p=self.command('archive-preview')['preview']
        self.assertEqual([r['rank'] for r in p['rows']],[1,2,3,4])
        self.assertEqual(len(p['rows']),4)
