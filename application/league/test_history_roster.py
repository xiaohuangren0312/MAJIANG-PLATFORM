import copy,json
from pathlib import Path
from django.test import SimpleTestCase
from .history_roster import update, add_player
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
    def test_export_includes_current_number_and_source_coach(self):
        import csv,io
        from .archive_export import history_csv
        p=self.payload['players'][0]
        d=update(self.document,dict(kind='player',id=p['id'],name='更名导出',number='101'))
        event=Event(name='导出验收',kind='team',document=d)
        rows=list(csv.reader(io.StringIO(history_csv(event))))
        self.assertIn(['选手ID','姓名','当前队伍','报名编号'],rows)
        self.assertEqual(next(r for r in rows if r and r[0]==p['id'])[3],'101')
        team=next(t for t in self.payload['teams'] if t.get('coach',{}).get('playing') is False)
        self.assertIn([team['id'],team['name'],'麻神','全职教练'],rows)

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


    def test_add_endpoint_records_audit_and_rejects_duplicate(self):
        admin=get_user_model().objects.create_user('history-add-admin',is_superuser=True)
        payload=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
        d=initial();d['historySnapshot']=payload
        event=Event.objects.create(name='历史补录测试',kind='team',document=d)
        self.client.force_login(admin);url=f'/api/events/{event.id}/'
        body=dict(action='history-player-add',revision=1,name='新增选手')
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,200)
        event.refresh_from_db();self.assertEqual(len(event.document['historyCurrent']['players']),50)
        self.assertEqual(event.document['historySnapshot'],payload)
        self.assertEqual(Audit.objects.get(event=event).action,'history-player-add')
        body['revision']=2
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,400)
        event.refresh_from_db();self.assertEqual(event.revision,2)


class HistoryPlayerAddTests(SimpleTestCase):
    def setUp(self):
        self.source=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
        self.d={'historySnapshot':self.source}
    def test_number_and_scores_preserved(self):
        original=copy.deepcopy(self.d)
        d=add_player(self.d,dict(name='补录甲',teamId=self.source['teams'][0]['id']))
        p=d['historyCurrent']['players'][-1];self.assertEqual(p['number'],'50')
        self.assertEqual(self.d,original);self.assertEqual(d['historySnapshot'],self.source)
        for key in ['statistics','results','schedule','snapshots']:self.assertEqual(d['historyCurrent'][key],self.source[key])
        d=update(d,dict(kind='player',id=p['id'],name='补录甲',number='900'))
        d=add_player(d,dict(name='补录乙'));self.assertEqual(d['historyCurrent']['players'][-1]['number'],'901')
        self.assertIsNone(d['historyCurrent']['players'][-1]['teamId'])
    def test_invalid_identity_and_team_rejected(self):
        for body in [dict(name=self.source['players'][0]['name'].upper()),dict(name=''),dict(name='新增',teamId='foreign')]:
            with self.assertRaises(Invalid):add_player(self.d,body)
        with self.assertRaises(Invalid):add_player(dict(self.d,archive={'locked':True}),dict(name='新增'))
    def test_correction_can_link_new_player_without_reassigning_team(self):
        from .history_correction import preview
        doc=initial();doc['historySnapshot']=copy.deepcopy(self.source)
        match=doc['historySnapshot']['results'][0];match['seats'][0]['playerId']=None
        d=add_player(doc,dict(name='漏录选手',teamId=match['seats'][0]['teamId']))
        pid=d['historyCurrent']['players'][-1]['id'];seats=copy.deepcopy(match['seats']);seats[0]['playerId']=pid
        result,new=preview(d,dict(id=match['id'],seats=seats,scoreMode='keep-pt'))
        self.assertEqual(new['results'][0]['seats'][0]['teamId'],match['seats'][0]['teamId'])
        row=next(r for r in new['statistics']['all']['raw']['player'] if r['id']==pid)
        self.assertEqual(row['total'],seats[0]['points']);self.assertEqual(row['games'],1)
