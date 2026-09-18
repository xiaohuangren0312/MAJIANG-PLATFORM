import copy,json
from pathlib import Path
from django.test import SimpleTestCase,TestCase
from django.contrib.auth import get_user_model
from .history_bonds import register,mark
from .history_correction import preview
from .domain import initial,Invalid
from .models import Event,Audit
from .projection import public_event
from .archive_export import history_csv

def source():return json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
def document():
    d=initial();d['historySnapshot']=source();return d

class HistoryBondTests(SimpleTestCase):
    def test_existing_player_stage_mark_and_score_preservation(self):
        d=document();before=copy.deepcopy(d);p=d['historySnapshot']['players'][0]
        new=register(d,dict(playerId=p['id'],stageId='regular',teamId=p['teamId']))
        self.assertEqual(d,before);self.assertEqual(new['historySnapshot'],before['historySnapshot'])
        for key in ['results','schedule','statistics','snapshots']:self.assertEqual(new['historyCurrent'][key],before['historySnapshot'][key])
        marked=mark(copy.deepcopy(new['historyCurrent']))
        for stage in ['all','regular','semi','final']:
            r=next(r for r in marked['statistics'][stage]['raw']['player'] if r['id']==p['id'])
            self.assertEqual(r['bond'],stage in ['all','regular'])
        self.assertEqual(new['historyCurrent']['players'][0]['bondStages'],{'regular':p['teamId']})
    def test_registration_conflicts_and_isolation(self):
        d=document();p=d['historySnapshot']['players'][0]
        other=next(t['id'] for t in d['historySnapshot']['teams'] if t['id']!=p['teamId'])
        for b in [dict(playerId='foreign',stageId='regular',teamId=p['teamId']),dict(playerId=p['id'],stageId='foreign',teamId=p['teamId']),dict(playerId=p['id'],stageId='regular',teamId=other)]:
            with self.assertRaises(Invalid):register(d,b)
        args=dict(playerId=p['id'],stageId='regular',teamId=p['teamId']);new=register(d,args)
        with self.assertRaises(Invalid):register(new,args)
        self.assertNotIn('bondStages',d['historySnapshot']['players'][0])
    def test_new_bond_not_permanent_roster_and_correction_guard(self):
        d=document();team=d['historySnapshot']['teams'][0]['id']
        new=register(d,dict(name='新增羁绊',stageId='semi',teamId=team));p=new['historyCurrent']['players'][-1]
        self.assertIsNone(p['teamId']);self.assertEqual(p['number'],'50');self.assertEqual(p['bondStages'],{'semi':team})
        match=next(m for m in new['historyCurrent']['results'] if m['stageId']=='semi');seats=copy.deepcopy(match['seats']);i=next(i for i,s in enumerate(seats) if s['teamId']!=team);seats[i]['playerId']=p['id']
        with self.assertRaisesMessage(Invalid,'羁绊代表队伍不匹配'):preview(new,dict(id=match['id'],seats=seats,scoreMode='keep-pt'))
        new2=register(new,dict(playerId=p['id'],stageId='final',teamId=team));self.assertEqual(len(new2['historyCurrent']['players'][-1]['bondStages']),2)
        self.assertEqual(new2['historyCurrent']['results'],d['historySnapshot']['results'])

class HistoryBondApiTests(TestCase):
    def test_scoped_access_audit_projection_and_export(self):
        manager=get_user_model().objects.create_user('bond-manager');other=get_user_model().objects.create_user('bond-other')
        d=document();p=d['historySnapshot']['players'][0];event=Event.objects.create(name='历史羁绊验收',kind='team',document=d);event.editors.add(manager)
        admin=get_user_model().objects.create_user('bond-root',is_superuser=True)
        url=f'/api/history-backfill/events/{event.id}/';body=dict(action='history-bond-register',revision=1,playerId=p['id'],stageId='regular',teamId=p['teamId'])
        self.client.force_login(other);self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,403)
        self.client.force_login(manager);self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,403)
        self.client.force_login(admin);self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,200)
        event.refresh_from_db();self.assertEqual(Audit.objects.get(event=event).action,'history-bond-register')
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,409)
        projected=public_event(event);self.assertTrue(next(r for r in projected['statistics']['regular']['raw']['player'] if r['id']==p['id'])['bond'])
        self.assertIn('羁绊阶段登记',history_csv(event));self.assertEqual(event.document['historySnapshot'],d['historySnapshot'])
