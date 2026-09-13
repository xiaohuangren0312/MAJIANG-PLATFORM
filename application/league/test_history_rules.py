import copy
from django.test import TestCase
from . import test_history_scores as fixtures
from .models import Event,Audit
from .domain import apply
from .history_correction import preview,commit

class HistoryRuleTests(TestCase):
    setUp=fixtures.HistoryScoreTests.setUp
    body=fixtures.HistoryScoreTests.body
    def rule_body(self):
        return dict(action='rule',revision=1,name='自定义规则',start=25000,**{'return':25000},bonuses=[300,100,-100,-300],reason='历史规则依据')
    def test_member_create_no_score_change_and_audit(self):
        old=copy.deepcopy(self.e.document)
        r=self.client.post(self.url,self.rule_body(),content_type='application/json');self.assertEqual(r.status_code,200)
        self.e.refresh_from_db();self.assertEqual(self.e.document['historySnapshot'],old['historySnapshot'])
        self.assertNotIn('historyCurrent',self.e.document);self.assertEqual(len(self.e.document['rules']),2)
        self.assertEqual(self.e.document['rules'][0],old['rules'][0])
        self.assertEqual(Audit.objects.get(event=self.e).reason,'历史规则依据')
    def test_ordinary_and_cross_event_denied(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,self.rule_body(),content_type='application/json').status_code,404)
        self.client.force_login(self.child)
        other=Event.objects.create(name='隔离赛事',kind='team',document=self.doc)
        self.assertEqual(self.client.post(f'/api/events/{other.id}/',self.rule_body(),content_type='application/json').status_code,404)
    def test_revoked_member_denied(self):
        self.e.editors.remove(self.child)
        self.assertEqual(self.client.post(self.url,self.rule_body(),content_type='application/json').status_code,404)
    def test_reason_optional_and_revision_conflict(self):
        b=self.rule_body();b['reason']=''
        self.assertEqual(self.client.post(self.url,b,content_type='application/json').status_code,200)
        self.client.post(self.url,self.rule_body(),content_type='application/json')
        self.assertEqual(self.client.post(self.url,self.rule_body(),content_type='application/json').status_code,409)
    def test_choose_old_new_versions(self):
        self.doc=apply(self.doc,'team','rule',self.rule_body())
        b=self.body([40000,30000,20000,10000]);b.update(scoreMode='recalculate',confirmNoPenalties=True)
        b['ruleId']=self.doc['rules'][0]['id'];p,old=preview(self.doc,b)
        self.assertEqual(old['results'][0]['seats'][0]['points'],600)
        b['ruleId']=self.doc['rules'][1]['id'];p,new=preview(self.doc,b)
        self.assertEqual(new['results'][0]['seats'][0]['points'],450)
        self.assertEqual(new['results'][0]['ruleVersion'],2)
        self.assertEqual(new['results'][0]['correctionRule'],self.doc['rules'][1])
    def test_rule_version_signed_and_frozen(self):
        self.client.post(self.url,self.rule_body(),content_type='application/json');self.e.refresh_from_db()
        b=self.body([40000,30000,20000,10000]);b.update(scoreMode='recalculate',confirmNoPenalties=True,ruleId=self.e.document['rules'][0]['id'])
        r=self.client.post(self.url,dict(action='history-preview',revision=2,**b),content_type='application/json')
        self.assertEqual(r.status_code,200)
        r=self.client.post(self.url,dict(action='history-correct',revision=2,token=r.json()['token'],acknowledgeCarry=True,ruleId=self.e.document['rules'][1]['id']),content_type='application/json')
        self.assertEqual(r.status_code,200);self.e.refresh_from_db()
        self.assertEqual(self.e.document['historyCurrent']['results'][0]['correctionRule']['version'],1)
        old=copy.deepcopy(self.e.document['historyCurrent'])
        b=self.rule_body();b['revision']=3
        self.assertEqual(self.client.post(self.url,b,content_type='application/json').status_code,200)
        self.e.refresh_from_db();self.assertEqual(self.e.document['historyCurrent'],old)
    def test_foreign_rule_rejected(self):
        b=self.body([40000,30000,20000,10000]);b['ruleId']='not-from-this-event'
        self.assertEqual(self.client.post(self.url,dict(action='history-preview',revision=1,**b),content_type='application/json').status_code,400)
