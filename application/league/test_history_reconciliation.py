import copy,json
from pathlib import Path
from django.test import SimpleTestCase
from .history_reconciliation import reconcile
from .history_review import report

class HistoryReconciliationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data=json.loads((Path(__file__).parents[2]/'design/prototypes/public-v1/site/data.json').read_text())
        cls.sources={p['id']:p for p in data['tournaments']}
    def test_s3_team_and_all_case_aliases(self):
        p=reconcile(self.sources['s3'])
        team=next(x for x in p['statistics']['regular']['competitive']['team'] if x['name']=='El Psy Tomcoco')
        self.assertEqual((team['games'],team['total']),(48,1428))
        self.assertFalse(any(not s.get('teamId') for m in p['results'] for s in m['seats']))
        self.assertEqual(len(p['players']),63)
    def test_s2_every_stage_matches_final_controls(self):
        p=reconcile(self.sources['s2'])
        for stage in ['regular','semi','final']:
            for row in p['statistics'][stage]['competitive']['team']:
                self.assertEqual(row['detailTotal'],row['raw'])
        tom=next(x for x in p['players'] if x['name']=='TOM')
        self.assertEqual(tom['teamId'],'t5')
        self.assertFalse(any(not s.get('teamId') for m in p['results'] for s in m['seats']))
    def test_source_fines_and_carry_not_double_counted(self):
        p=reconcile(self.sources['s3'])
        rows={r['id']:r for r in p['statistics']['regular']['competitive']['team']}
        self.assertEqual([rows[k]['stagePenalty'] for k in ['t3','t4','t10']],[120,200,20])
        self.assertEqual([rows[k]['total'] for k in ['t3','t4','t10']],[5628,2667,-4546])
        for row in p['statistics']['all']['competitive']['team']:
            expected=sum(r['raw'] for stage in ['regular','semi','final'] for r in p['statistics'][stage]['competitive']['team'] if r['id']==row['id'])
            self.assertEqual(row['total'],expected)
    def test_no_source_mutation_or_invented_results(self):
        source=copy.deepcopy(self.sources['s3']);p=reconcile(source)
        self.assertEqual(source,self.sources['s3'])
        self.assertEqual(p['snapshots'],source['snapshots'])
        self.assertEqual(p['dailySummaries'],source['dailySummaries'])
        self.assertEqual(len(p['results']),len(source['results']))
        for old,new in zip(source['results'],p['results']):
            for a,b in zip(old['seats'],new['seats']):
                for key in ['score','points','teamPoints','rank','penalty']:self.assertEqual(a.get(key),b.get(key))
        self.assertEqual(reconcile(p),p)
    def test_user_confirmations_apply_to_all_records(self):
        source=self.sources['s2'];p=reconcile(source)
        self.assertEqual(report(p)['issues'],[])
        self.assertEqual(report(reconcile(self.sources['s3']))['issues'],[])
        names={x['name'] for x in p['players']}
        self.assertTrue({'COCO','神菜菜子','_404','楠哥'}.issubset(names))
        self.assertFalse({'Zing_Coco','菜菜子','404'} & names)
        for old,new in [('Zing_Coco','COCO'),('菜菜子','神菜菜子'),('404','_404')]:
            originals=[x['id'] for x in source['players'] if x['name'] in [old,new]]
            person=next(x for x in p['players'] if x['name']==new)
            expected=sum(s['points'] for m in source['results'] for s in m['seats'] if s.get('playerId') in originals)
            actual=next(x for x in p['statistics']['all']['raw']['player'] if x['id']==person['id'])
            self.assertEqual(actual['total'],expected)
        late=next(m for m in p['results'] if m['id']=='S2-r55')
        self.assertEqual(late['penalties'][0]['amount'],20)
        self.assertIn('迟到',late['penalties'][0]['explanation'])
