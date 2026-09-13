import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import HistoricalArchive,HistoryReview,HistoryReviewAudit
from .history_review import report

class HistoryReviewTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user(username='history-admin',is_superuser=True)
        self.user=get_user_model().objects.create_user(username='ordinary')
        self.payload={'id':'fixture','name':'历史测试','type':'team','teams':[],'players':[],'stages':[{'id':'final','name':'决赛'}],'results':[{'id':'r1','stageId':'final','seats':[{'points':195,'teamPoints':195} for _ in range(4)]}]}
        self.archive=HistoricalArchive.objects.create(key='fixture',payload=self.payload)
        self.url='/api/history-reviews/fixture/'
        self.client.force_login(self.admin)
    def request_body(self):
        d=self.client.get(self.url).json()
        return dict(fingerprint=d['fingerprint'],revision=d['revision'],issue=d['report']['issues'][0]['id'],status='retain',note='原表未记名，保留队伍积分')
    def test_missing_not_reconstructed(self):
        original=copy.deepcopy(self.payload);r=report(self.payload)
        self.assertEqual(self.payload,original);self.assertEqual(r['stages'][0]['matches'],1)
        self.assertIn('选手',r['issues'][0]['message']);self.assertIn('终局点数',r['issues'][0]['message'])
    def test_save_audit_and_source_unchanged(self):
        b=self.request_body();self.assertEqual(self.client.post(self.url,b,content_type='application/json').status_code,200)
        self.archive.refresh_from_db();self.assertEqual(self.archive.payload,self.payload)
        self.assertEqual(HistoryReviewAudit.objects.count(),1)
        self.assertEqual(self.client.get(self.url).json()['decisions'][b['issue']]['note'],b['note'])
    def test_conflict_and_source_change(self):
        b=self.request_body();self.client.post(self.url,b,content_type='application/json')
        self.assertEqual(self.client.post(self.url,b,content_type='application/json').status_code,409)
        self.archive.payload['name']='新版本';self.archive.save()
        self.assertEqual(self.client.post(self.url,{**b,'revision':1},content_type='application/json').status_code,409)
        d=self.client.get(self.url).json();self.assertTrue(d['sourceChanged']);self.assertEqual(d['decisions'],{})
    def test_permissions(self):
        self.client.force_login(self.user)
        for url in [self.url,'/api/history-reviews/','/manage/history/']:self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(self.url,{},content_type='application/json').status_code,403)
        self.client.logout();self.assertEqual(self.client.get(self.url).status_code,401)
    def test_invalid_decision(self):
        b=self.request_body()
        for patch in [{'note':''},{'issue':'other-event'},{'status':'approved'},{'note':'x'*1001}]:
            self.assertEqual(self.client.post(self.url,{**b,**patch},content_type='application/json').status_code,400)
        self.assertFalse(HistoryReviewAudit.objects.exists())
    def test_score_discrepancy_is_advisory(self):
        p=copy.deepcopy(self.payload)
        p['results'][0]['seats']=[{'score':v,'base':0} for v in [40000,30000,20000,10000]]
        self.assertIn('计分差异',[i['category'] for i in report(p)['issues']])


class HistoryImportTests(HistoryReviewTests):
    def import_body(self):
        b=self.request_body();return {'fingerprint':b['fingerprint'],'revision':b['revision'],'reason':'保留原表导入'}
    def do_import(self):
        return self.client.post(self.url+'import/',self.import_body(),content_type='application/json')
    def test_import_snapshot_idempotent_and_private(self):
        from .models import Event,HistoryImport,Audit
        response=self.do_import();self.assertEqual(response.status_code,201)
        e=Event.objects.get(pk=response.json()['id']);self.assertFalse(e.public)
        self.assertEqual(e.document['historySnapshot'],self.payload)
        self.assertEqual(self.do_import().json()['id'],str(e.id))
        self.assertEqual(HistoryImport.objects.count(),1);self.assertEqual(Audit.objects.filter(event=e).count(),1)
        self.assertEqual(self.client.get('/api/events/').json()['events'][0]['id'],str(e.id))
    def test_publish_requires_review_and_preserves_payload(self):
        from .models import Event
        e=Event.objects.get(pk=self.do_import().json()['id']);url=f'/api/events/{e.id}/'
        cmd={'revision':1,'action':'visibility','public':True}
        self.assertEqual(self.client.post(url,cmd,content_type='application/json').status_code,400)
        self.assertTrue(HistoricalArchive.objects.get(pk='fixture').public)
        self.client.post(self.url,self.request_body(),content_type='application/json')
        self.assertEqual(self.client.post(url,cmd,content_type='application/json').status_code,200)
        self.assertFalse(HistoricalArchive.objects.get(pk='fixture').public)
        data=self.client.get('/data.json').json()['tournaments'];self.assertEqual(len(data),1);self.assertEqual(data[0],self.payload)
        self.assertEqual(self.client.post(url,{'revision':2,'action':'visibility','public':False},content_type='application/json').status_code,200)
        self.assertEqual(self.client.get('/data.json').json()['tournaments'],[])
    def test_history_mutations_blocked(self):
        e=self.do_import().json()['id']
        r=self.client.post(f'/api/events/{e}/',{'revision':1,'action':'stage','name':'invalid'},content_type='application/json')
        self.assertEqual(r.status_code,403)
    def test_import_permissions_and_stale_source(self):
        b=self.import_body();self.archive.payload['name']='changed';self.archive.save()
        self.assertEqual(self.client.post(self.url+'import/',b,content_type='application/json').status_code,409)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.url+'import/',b,content_type='application/json').status_code,403)
