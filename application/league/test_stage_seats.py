import copy
from collections import Counter
from django.test import SimpleTestCase
from .domain import Invalid,apply
from .seat_draw import draw

class StageBalanceTests(SimpleTestCase):
    def document(self):
        teams=[{'id':str(i),'playerId':'p'+str(i)} for i in range(8)]
        rows=[]
        for day in range(4):
            for n in range(2):
                rows.append(dict(id=f'{day}-{n}',stageId='s',date=f'2099-01-{day+1:02}',time='19:30',number=n+1,table=str(n+1),state='draft',seats=[dict(teamId=t['id'],playerId=t['playerId']) for t in teams[n*4:n*4+4]],coachLineups={'example':{'playerId':'p1'}},commentators=['示例']))
        return dict(stages=[dict(id='s',locked=False)],matches=rows)
    def test_exact_and_preserve_pairing_and_metadata(self):
        d=self.document();before=copy.deepcopy(d)
        out=apply(d,'team','random-seats',dict(scope='stage',stageId='s'))
        self.assertEqual(d,before)
        for t in map(str,range(8)):
            rows=[m for m in out['matches'] if any(s['teamId']==t for s in m['seats'])]
            self.assertEqual(Counter(m['number'] for m in rows),{1:2,2:2})
            self.assertEqual(Counter(i for m in rows for i,s in enumerate(m['seats']) if s['teamId']==t),{0:1,1:1,2:1,3:1})
        for a,b in zip(d['matches'],out['matches']):
            self.assertEqual(sorted(a['seats'],key=lambda s:s['teamId']),sorted(b['seats'],key=lambda s:s['teamId']))
            self.assertEqual({k:v for k,v in a.items() if k not in ['seats','number','table','seatDraw']},{k:v for k,v in b.items() if k not in ['seats','number','table','seatDraw']})
    def test_published_preserved_and_automatic_draw_disabled(self):
        d=self.document();m=d['matches'][0];m['state']='published'
        for s in m['seats']:s['score']=25000
        before=copy.deepcopy(m);out=apply(d,'team','random-seats',dict(scope='stage',stageId='s'));self.assertEqual(out['matches'][0],before)
        m=out['matches'][1];before=copy.deepcopy(m);draw(out,m,automatic=True);self.assertEqual(m,before)
    def test_explicit_scope_required(self):
        with self.assertRaises(Invalid):apply(self.document(),'team','random-seats',{'id':'0-0'})
    def test_impossible_fixed_counts_fail_without_mutation(self):
        d=self.document()
        for m in d['matches'][:6]:m['state']='published'
        before=copy.deepcopy(d)
        with self.assertRaises(Invalid):apply(d,'team','random-seats',dict(scope='stage',stageId='s'))
        self.assertEqual(d,before)
    def test_incomplete_and_locked_rejected(self):
        d=self.document();d['matches'].pop()
        with self.assertRaises(Invalid):apply(d,'team','random-seats',dict(scope='stage',stageId='s'))
        d=self.document();d['stages'][0]['locked']=True
        with self.assertRaises(Invalid):apply(d,'team','random-seats',dict(scope='stage',stageId='s'))
