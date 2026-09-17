import copy
from django.test import SimpleTestCase
from .history_schedule import normalize

class HistoricalTableTests(SimpleTestCase):
    def fixture(self):
        rows=[]
        for i,teams in enumerate([['a','b','c','d'],['e','f','g','h'],['a','b','c','d'],['e','f','g','h']],1):
            rows.append(dict(id=str(i),resultId=str(i),number=i,date='2026-01-01',stageId='regular',table=str(i),time='19:30' if i%2 else '21:00',players=[{'teamId':t} for t in teams]))
        return dict(id='s2',schedule=rows,results=[dict(id=str(i),points=99,table=str(i),time='unknown') for i in range(1,5)])
    def test_repeated_opponents_share_table_and_play_different_rounds(self):
        p=self.fixture();normalize(p)
        self.assertEqual([(m['table'],m['time']) for m in p['schedule']],[('A','19:30'),('B','19:30'),('A','21:00'),('B','21:00')])
        self.assertEqual([(m['table'],m['time']) for m in p['results']],[(m['table'],m['time']) for m in p['schedule']])
        self.assertTrue(all(m['points']==99 for m in p['results']))
        again=copy.deepcopy(p);normalize(again);self.assertEqual(again,p)
    def test_new_events_keep_arbitrary_physical_tables(self):
        p=self.fixture();p['id']='new-event';old=copy.deepcopy(p);normalize(p);self.assertEqual(old,p)
    def test_incomplete_day_does_not_invent_dates_or_round_times(self):
        p=self.fixture();p['schedule']=p['schedule'][:1];before=copy.deepcopy(p['schedule'][0]);normalize(p)
        self.assertEqual(p['schedule'][0]['date'],before['date']);self.assertEqual(p['schedule'][0]['time'],before['time'])
