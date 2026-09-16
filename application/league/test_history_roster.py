import copy,json
from pathlib import Path
from django.test import SimpleTestCase
from .history_roster import update
from .domain import Invalid

class HistoryRosterTests(SimpleTestCase):
    def setUp(self):
        self.payload=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
        self.document={'historySnapshot':self.payload}
    def test_identity_preserves_source_scores_and_memberships(self):
        old=copy.deepcopy(self.document);p=self.payload['players'][0]
        result=update(self.document,dict(kind='player',id=p['id'],name='改名选手',number='101'))
        self.assertEqual(self.document,old);self.assertEqual(result['historySnapshot'],self.payload)
        current=result['historyCurrent'];self.assertEqual(current['results'],self.payload['results']);self.assertEqual(current['schedule'],self.payload['schedule']);self.assertEqual(current['snapshots'],self.payload['snapshots'])
        self.assertEqual(current['players'][0]['teamId'],p['teamId']);self.assertEqual(current['players'][0]['number'],'101')
        for metrics in current['statistics'].values():
            for kinds in metrics.values():
                self.assertEqual(next(r for r in kinds['player'] if r['id']==p['id'])['name'],'改名选手')
    def test_duplicate_and_foreign_identity_rejected(self):
        p=self.payload['players'][0]
        for body in [dict(kind='player',id=p['id'],name=self.payload['players'][1]['name']),dict(kind='team',id=p['id'],name='错类型'),dict(kind='player',id='foreign',name='跨赛事')]:
            with self.assertRaises(Invalid):update(self.document,body)
        d=update(self.document,dict(kind='player',id=p['id'],name=p['name'],number='101'))
        other=self.payload['players'][1]
        with self.assertRaises(Invalid):update(d,dict(kind='player',id=other['id'],name=other['name'],number='101'))
        with self.assertRaises(Invalid):update(d,dict(kind='player',id=p['id'],name=p['name'],number=''))
    def test_team_label_preserves_totals_and_prior_overlay(self):
        d=copy.deepcopy(self.document);d['historyCurrent']=copy.deepcopy(self.payload);d['historyCurrent']['players'][0]['imageUrl']='/image.png'
        t=self.payload['teams'][0];new=update(d,dict(kind='team',id=t['id'],name='队伍新名'))['historyCurrent']
        self.assertEqual(new['players'][0]['imageUrl'],'/image.png')
        self.assertEqual(new['results'],self.payload['results'])
        for stage,metrics in new['statistics'].items():
            for metric,kinds in metrics.items():
                for row in kinds['team']:
                    original=next(r for r in self.payload['statistics'][stage][metric]['team'] if r['id']==row['id'])
                    self.assertEqual({k:v for k,v in row.items() if k!='name'},{k:v for k,v in original.items() if k!='name'})

from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Event, Audit
from .domain import initial

class HistoryRosterApiTests(TestCase):
    def test_authorization_revision_and_audit(self):
        manager=get_user_model().objects.create_user('roster-manager')
        stranger=get_user_model().objects.create_user('roster-other')
        payload=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
        d=initial();d['historySnapshot']=payload
        event=Event.objects.create(name='历史测试',kind='team',document=d);event.editors.add(manager)
        url=f'/api/events/{event.id}/';player=payload['players'][0]
        body=dict(action='history-roster',revision=1,kind='player',id=player['id'],name='名单测试',number='9')
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,404)
        self.client.force_login(manager)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,200)
        event.refresh_from_db();self.assertEqual(event.revision,2)
        self.assertEqual(event.document['historySnapshot'],payload)
        self.assertEqual(Audit.objects.filter(event=event,action='history-roster').count(),1)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,409)
        self.assertEqual(Audit.objects.filter(event=event).count(),1)
