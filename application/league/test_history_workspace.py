import copy,json
from pathlib import Path
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from .models import Event,Audit
from .domain import initial
from .projection import public_event

class HistoryWorkspaceTests(TestCase):
    def setUp(self):
        User=get_user_model();self.root=User.objects.create_user('workspace-root',is_superuser=True)
        self.child=User.objects.create_user('workspace-child');self.viewer=User.objects.create_user('workspace-viewer')
        d=initial();d['historySnapshot']=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
        self.e=Event.objects.create(name='S1验收',kind='team',document=d);self.e.editors.add(self.child)
        self.normal=f'/api/events/{self.e.pk}/';self.workspace=f'/api/history-backfill/events/{self.e.pk}/'
    def test_backfill_is_root_only_and_regular_endpoint_cannot_bypass(self):
        for user in [self.child,self.viewer]:
            self.client.force_login(user)
            for url in ['/manage/history-backfill/','/api/history-backfill/events/',self.workspace]:
                self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.client.post(self.workspace,{'action':'history-player-add','revision':1,'name':'越权'},content_type='application/json').status_code,403)
        self.client.force_login(self.root)
        self.assertEqual(self.client.get('/manage/history-backfill/').status_code,200)
        self.assertEqual(self.client.get('/api/history-backfill/events/').json()['events'][0]['id'],str(self.e.pk))
        for user in [self.root,self.child]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.normal,{'action':'history-player-add','revision':1,'name':'越权'},content_type='application/json').status_code,403)
        self.assertEqual(Audit.objects.count(),0)
    def test_unified_read_model_preserves_scores_source_and_missing_fields(self):
        self.client.force_login(self.child);before=copy.deepcopy(self.e.document);public=public_event(self.e)
        response=self.client.get(self.normal);self.assertEqual(response.status_code,200)
        d=response.json()['managementDocument']
        self.assertFalse(any(k.startswith('history') for k in d))
        self.assertEqual(len(d['players']),49);self.assertEqual(len(d['teams']),8);self.assertEqual(len(d['matches']),98)
        self.assertEqual(sum(m['hasResult'] for m in d['matches']),92)
        byid={m['id']:m for m in d['matches']}
        for m in public['results']:self.assertEqual(byid[m['id']]['seats'],m['seats'])
        self.e.refresh_from_db();self.assertEqual(self.e.document,before);self.assertEqual(Audit.objects.count(),0)
        page=self.client.get('/manage/');self.assertNotContains(page,'history-editor.js');self.assertNotContains(page,'历史补录')
    def test_root_backfill_persists_in_normal_view_and_survives_switch_off(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.post(self.workspace,{'action':'history-player-add','revision':1,'name':'补录验收'},content_type='application/json').status_code,200)
        with override_settings(HISTORY_BACKFILL_ENABLED=False):
            self.assertNotContains(self.client.get('/manage/'),'历史补录')
            for url in ['/manage/history-backfill/','/api/history-backfill/events/',self.workspace,'/manage/history/','/api/history-reviews/','/assets/history-editor.js','/assets/history-backfill.js']:
                self.assertEqual(self.client.get(url).status_code,404,url)
            self.assertEqual(self.client.post(self.workspace,{'action':'history-player-add','revision':2,'name':'不能新增'},content_type='application/json').status_code,404)
            response=self.client.get(self.normal);self.assertEqual(response.status_code,200)
            self.assertIn('补录验收',[p['name'] for p in response.json()['managementDocument']['players']])
            self.assertEqual(self.client.get(self.normal+'archive.csv').status_code,200)
    def test_permanent_identity_update_works_without_backfill(self):
        player=self.e.document['historySnapshot']['players'][0];before=copy.deepcopy(self.e.document)
        self.client.force_login(self.child)
        with override_settings(HISTORY_BACKFILL_ENABLED=False):
            response=self.client.post(self.normal,{'action':'player-update','revision':1,'id':player['id'],'name':'统一管理更名','number':'101','active':True,'bio':'简介'},content_type='application/json')
            self.assertEqual(response.status_code,200,response.content)
        self.e.refresh_from_db();self.assertEqual(self.e.document['historySnapshot'],before['historySnapshot'])
        self.assertEqual(self.e.document['historyCurrent']['results'],before['historySnapshot']['results'])
        self.assertEqual(self.e.document['historyCurrent']['players'][0]['name'],'统一管理更名')
    def test_new_events_never_appear_in_backfill(self):
        other=Event.objects.create(name='新赛事',kind='team',document=initial());self.client.force_login(self.root)
        self.assertEqual(self.client.get(f'/api/history-backfill/events/{other.pk}/').status_code,404)

    def test_team_identity_and_missing_number_edits_preserve_source(self):
        self.client.force_login(self.child);source=copy.deepcopy(self.e.document['historySnapshot'])
        p=source['players'][0]
        r=self.client.post(self.normal,{'action':'player-update','revision':1,'id':p['id'],'name':p['name'],'number':'','active':False},content_type='application/json')
        self.assertEqual(r.status_code,200,r.content)
        t=source['teams'][0]
        r=self.client.post(self.normal,{'action':'team-update','revision':2,'id':t['id'],'name':'队伍资料维护','active':True,'color':t['color']},content_type='application/json')
        self.assertEqual(r.status_code,200,r.content)
        self.e.refresh_from_db();current=self.e.document['historyCurrent']
        self.assertFalse(current['players'][0]['active']);self.assertFalse(current['players'][0].get('number'))
        self.assertEqual(current['results'],source['results']);self.assertEqual(current['snapshots'],source['snapshots'])
        self.assertEqual(self.e.document['historySnapshot'],source)
