import copy
from django.test import SimpleTestCase
from .domain import initial,apply,Invalid

class EventElementsTests(SimpleTestCase):
    def setUp(self):
        d=apply(initial(),'personal','stage',{'name':'常规赛'})
        for name in ['甲','乙','丙','丁']:d=apply(d,'personal','player',{'name':name})
        self.d=apply(d,'personal','match',dict(stageId=d['stages'][0]['id'],date='2026-01-01',number=1,seats=[{'playerId':p['id']} for p in d['players']]))
        self.mid=self.d['matches'][0]['id']
    def test_delete_published_unsettled_result_and_preserve_audit_input(self):
        d=apply(self.d,'personal','save-result',dict(id=self.mid,scores=[40000,30000,20000,10000]));old=copy.deepcopy(d)
        new=apply(d,'personal','match-delete',dict(id=self.mid))
        self.assertFalse(new['matches']);self.assertEqual(d,old)
        d['stages'][0]['locked']=True
        with self.assertRaises(Invalid):apply(d,'personal','match-delete',dict(id=self.mid))
    def test_metadata_preserves_scores_and_inactive_historical_players(self):
        d=apply(self.d,'personal','save-result',dict(id=self.mid,scores=[40000,30000,20000,10000]));d['players'][0]['active']=False
        new=apply(d,'personal','match-update',dict(id=self.mid,date='2026-02-02',time='21:00',number=2))
        self.assertEqual(new['matches'][0]['seats'],d['matches'][0]['seats'])
        self.assertEqual(new['matches'][0]['time'],'21:00')
        for time in ['24:00','x',None]:
            with self.assertRaises(Invalid):apply(d,'personal','match-update',dict(id=self.mid,date='2026-02-02',time=time,number=2))
    def test_used_rule_and_stage_rejected(self):
        d=apply(self.d,'personal','rule',dict(name='新规则',start=25000,return_=30000,**{'return':30000},bonuses=[500,100,-100,-300]))
        with self.assertRaises(Invalid):apply(d,'personal','rule-delete',dict(id=d['rules'][0]['id']))
        self.assertEqual(len(apply(d,'personal','rule-delete',dict(id=d['rules'][-1]['id']))['rules']),1)
        with self.assertRaises(Invalid):apply(d,'personal','stage-delete',dict(id=d['stages'][0]['id']))
