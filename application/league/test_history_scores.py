import copy
from django.test import TestCase
from . import test_history_correction as fixtures
from .history_correction import preview,commit
from .domain import Invalid

class HistoryScoreTests(TestCase):
    setUp=fixtures.HistoryCorrectionTests.setUp
    def body(self,values):
        seats=copy.deepcopy(self.payload['results'][0]['seats'])
        for s,v in zip(seats,values):s['score']=v
        return dict(id='r1',reason='补录原始点棒',scoreMode='keep-pt',seats=seats)
    def test_partial(self):
        p,n=preview(self.doc,self.body([40000,None,None,None]))
        self.assertEqual(n['results'][0]['seats'][0]['score'],40000)
        self.assertTrue(all(s['rank'] is None for s in n['results'][0]['seats']))
        self.assertEqual(self.doc['historySnapshot'],self.payload)
        self.assertTrue(any(c['afterBest']==40000 for c in p['changes']))
    def test_ties_keep_pt(self):
        _,n=preview(self.doc,self.body([30000,30000,25000,15000]))
        self.assertEqual([s['rank'] for s in n['results'][0]['seats']],[1,1,3,4])
        self.assertEqual([s['points'] for s in n['results'][0]['seats']],[500,100,-100,-500])
        row=next(r for r in n['statistics']['all']['raw']['player'] if r['id']=='p1')
        self.assertEqual(row['avgRank'],1.5)
    def test_recalculate(self):
        b=self.body([40000,30000,20000,10000]);b.update(scoreMode='recalculate',confirmNoPenalties=True)
        p,n=preview(self.doc,b)
        self.assertEqual([s['points'] for s in n['results'][0]['seats']],[600,100,-200,-500])
        self.assertEqual(n['snapshots'],self.payload['snapshots'])
        self.assertEqual(n['statistics']['final'],self.payload['statistics']['final'])
    def test_invalid_recalculation(self):
        for values,ack in [([40000,30000,20000,10000],False),([40000,None,20000,10000],True),([40000,30000,20000,0],True)]:
            b=self.body(values);b.update(scoreMode='recalculate',confirmNoPenalties=ack)
            with self.assertRaises(Invalid):preview(self.doc,b)
    def test_penalties_and_point_validation(self):
        for value in [12345,1.5,True]:
            with self.assertRaises(Invalid):preview(self.doc,self.body([value,None,None,None]))
        self.doc['historySnapshot']['results'][0]['seats'][0]['penalty']=10
        b=self.body([40000,30000,20000,10000]);b.update(scoreMode='recalculate',confirmNoPenalties=True)
        with self.assertRaises(Invalid):preview(self.doc,b)
    def test_signed_mode_zero(self):
        b=self.body([50000,30000,20000,0]);b.update(scoreMode='recalculate',confirmNoPenalties=True)
        res=self.client.post(self.url,dict(action='history-preview',revision=1,**b),content_type='application/json')
        self.assertEqual(res.status_code,200)
        res=self.client.post(self.url,dict(action='history-correct',revision=1,token=res.json()['token'],acknowledgeCarry=True),content_type='application/json')
        self.assertEqual(res.status_code,200);self.e.refresh_from_db()
        s=self.e.document['historyCurrent']['results'][0]['seats'][3]
        self.assertEqual((s['score'],s['rank'],s['points']),(0,4,-600))
    def test_cannot_clear(self):
        d=commit(self.doc,self.body([40000,None,None,None]))
        with self.assertRaises(Invalid):preview(d,self.body([None,None,None,None]))
