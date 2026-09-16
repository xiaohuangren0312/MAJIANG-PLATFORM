import copy,json
from pathlib import Path
from django.test import SimpleTestCase,TestCase
from django.contrib.auth import get_user_model
from .history_stages import update
from .domain import Invalid,initial
from .models import Event,Audit
from .projection import public_event

def source():return json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())

class HistoryStageTests(SimpleTestCase):
    def test_preserves_original_scores_and_prior_changes(self):
        payload=source();d={'historySnapshot':payload,'historyCurrent':copy.deepcopy(payload)}
        d['historyCurrent']['players'][0]['imageUrl']='/existing.png';before=copy.deepcopy(d)
        result=update(d,dict(id='semi',name='四强预选',advanceCount=4))
        self.assertEqual(d,before);self.assertEqual(result['historySnapshot'],payload)
        current=result['historyCurrent'];self.assertEqual(current['players'],before['historyCurrent']['players'])
        for key in ['results','schedule','statistics','snapshots','dailySummaries']:self.assertEqual(current[key],payload[key])
        self.assertEqual(current['stages'][1]['name'],'四强预选')
        self.assertEqual(len(current['stages']),3)
    def test_validation(self):
        d={'historySnapshot':source()}
        for b in [dict(id='foreign',name='新阶段'),dict(id='regular',name='决赛'),dict(id='regular',name=''),dict(id='regular',name='新名',advanceCount=-1),dict(id='regular',name='新名',advanceCount=True),dict(id='regular',name='新名',advanceCount=1.5)]:
            with self.assertRaises(Invalid):update(d,b)
        self.assertEqual(update(d,dict(id='regular',name='常规赛',advanceCount=0))['historyCurrent']['stages'][0]['advanceCount'],0)

class HistoryStageApiTests(TestCase):
    def test_permission_revision_audit_and_projection(self):
        user=get_user_model().objects.create_user('stage-manager');other=get_user_model().objects.create_user('stage-other')
        d=initial();d['historySnapshot']=source();event=Event.objects.create(name='历史阶段测试',kind='team',document=d);event.editors.add(user)
        url=f'/api/events/{event.id}/';body=dict(action='history-stage-update',revision=1,id='regular',name='预选赛',advanceCount=5)
        self.client.force_login(other);self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,404)
        self.client.force_login(user);self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,200)
        event.refresh_from_db();p=public_event(event)
        self.assertEqual((p['stages'][0]['name'],p['stages'][0]['advanceCount']),('预选赛',5))
        self.assertEqual(p['results'],d['historySnapshot']['results']);self.assertEqual(event.document['historySnapshot'],d['historySnapshot'])
        self.assertEqual(Audit.objects.get(event=event).action,'history-stage-update')
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,409)
