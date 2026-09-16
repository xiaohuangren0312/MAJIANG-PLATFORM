import json
from pathlib import Path
from django.test import SimpleTestCase
from .domain import initial,score
from .history_correction import totals
from .history_review import report

class S1ArchiveTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.t=json.loads((Path(__file__).parents[2]/'design/history-analysis/S1-public.json').read_text())
    def test_complete_records_and_missing_semifinal_detail(self):
        t=self.t
        self.assertEqual((len(t['teams']),len(t['players']),len(t['results']),len(t['schedule'])),(8,49,92,98))
        self.assertEqual([sum(m['stageId']==st for m in t['results']) for st in ['regular','semi','final']],[72,12,8])
        missing=[m for m in t['schedule'] if not m['resultId']]
        self.assertEqual(len(missing),6)
        self.assertTrue(all(m['stageId']=='semi' and m['state']=='completed' and all(s['playerId'] is None for s in m['players']) for m in missing))
        for m in t['results']:
            expected=score(initial()['rules'][0],[s['score'] for s in m['seats']])
            self.assertEqual(len({s['teamId'] for s in m['seats']}),4)
            for s,e in zip(m['seats'],expected):self.assertEqual((s['base'],s['rank']),(e['base'],e['rank']))
        self.assertEqual(report(t)['issues'],[])
    def test_final_control_and_stage_carry(self):
        t=self.t
        rows=t['statistics']['final']['competitive']['team']
        self.assertEqual([(r['name'],r['total'],r['carry']) for r in rows],[('宝宝巴士',1104,1693),('高祖游龙',1089,1486),('二元精品店',770,-274),('都到锅里来',142,200)])
        for r in rows:self.assertEqual(r['raw'],totals(t,'final','team',r['id'])['contribution'])
        for r in t['statistics']['semi']['competitive']['team']:
            self.assertEqual(r['raw'],sum(e['points'] for d in t['dailySummaries'] for e in d['entries'] if e['teamId']==r['id']))
        for r in t['statistics']['all']['competitive']['team']:
            self.assertEqual(r['total'],sum(x['raw'] for st in ['regular','semi','final'] for x in t['statistics'][st]['competitive']['team'] if x['id']==r['id']))
    def test_deduction_and_confirmed_alias_merged(self):
        p=next(p for p in self.t['players'] if p['name']=='小茵')
        r=next(r for r in self.t['statistics']['regular']['raw']['player'] if r['id']==p['id'])
        self.assertEqual((r['total'],r['penalty']),(-1737,200))
        crane=next(p for p in self.t['players'] if p['name']=='鹤')
        self.assertNotIn('鹤轩逸',{p['name'] for p in self.t['players']})
        aliases=[s for m in self.t['results'] for s in m['seats'] if s.get('sourceName')=='鹤轩逸']
        self.assertEqual(len(aliases),2)
        self.assertTrue(all(s['playerId']==crane['id'] for s in aliases))
        self.assertEqual(sum(len(m['penalties']) for m in self.t['results']),1)
