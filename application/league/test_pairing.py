import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from .domain import initial,apply,Invalid
from .pairing import preview,commit
from .models import Event,Audit

class PairingTests(TestCase):
    def setUp(self):
        self.d=apply(initial(),'personal','stage',{'name':'常规赛'})
        for n in [10,2,1,8,7,6,5,3]:
            self.d=apply(self.d,'personal','player',dict(name='选手'+str(n),number=str(n)))
        self.b=dict(stageId=self.d['stages'][0]['id'],date='2026-09-13',time='19:30',startTable=1)
    def publish(self,d):
        for m in list(d['matches']):
            if m['state']=='draft':
                d=apply(d,'personal','score',dict(id=m['id'],scores=[40000,30000,20000,10000],penalties=[],yakuman=[]))
                d=apply(d,'personal','publish',dict(id=m['id']))
        return d
    def test_initial_natural_order_and_exact_preview(self):
        p=preview(self.d,'personal',self.b)
        self.assertEqual([r['number'] for r in p['ranking']],['1','2','3','5','6','7','8','10'])
        d=commit(self.d,'personal',p)
        self.assertEqual(len(d['matches']),2)
        self.assertEqual([s['playerId'] for s in d['matches'][0]['seats']],p['tables'][0]['players'])
        self.assertTrue(all(m['lineupPublished'] and m['state']=='draft' for m in d['matches']))
        self.assertEqual(self.d['matches'],[])
    def test_next_round_points_and_table_reuse(self):
        d=self.publish(commit(self.d,'personal',preview(self.d,'personal',self.b)))
        p=preview(d,'personal',dict(self.b,time='21:00'))
        self.assertEqual(p['method'],'high-high');self.assertEqual(p['round'],2)
        self.assertEqual([r['points'] for r in p['ranking']],[600,600,100,100,-200,-200,-500,-500])
        for i in range(0,8,2):self.assertLess(int(p['ranking'][i]['number']),int(p['ranking'][i+1]['number']))
        after=commit(d,'personal',p)
        self.assertEqual([m['number'] for m in after['matches']],[1,2,1,2])
        self.assertEqual(after['pairingRounds'][0],d['pairingRounds'][0])
    def test_manual_adjustment_needs_no_reason_but_roster_validated(self):
        p=preview(self.d,'personal',self.b);tables=copy.deepcopy(p['tables'])
        tables[0]['players'][0],tables[1]['players'][0]=tables[1]['players'][0],tables[0]['players'][0]
        d=commit(self.d,'personal',p,tables)
        self.assertTrue(d['pairingRounds'][0]['manualAdjustment'])
        self.assertEqual(d['pairingRounds'][0]['reason'],'')
        tables[0]['players'][0]=tables[0]['players'][1]
        with self.assertRaises(Invalid):commit(self.d,'personal',p,tables)
    def test_incomplete_round_blocked(self):
        d=commit(self.d,'personal',preview(self.d,'personal',self.b))
        with self.assertRaises(Invalid):preview(d,'personal',dict(self.b,time='21:00'))
        d['matches'][1]['state']='cancelled';d=self.publish(d)
        with self.assertRaises(Invalid):preview(d,'personal',dict(self.b,time='21:00'))
    def test_invalid_conditions(self):
        for kind in ['team']:
            with self.assertRaises(Invalid):preview(self.d,kind,self.b)
        for changes in [dict(time='7:30'),dict(time='25:00'),dict(date='invalid'),dict(startTable=1000)]:
            with self.assertRaises(Invalid):preview(self.d,'personal',dict(self.b,**changes))
        d=copy.deepcopy(self.d);d['players'].pop()
        with self.assertRaises(Invalid):preview(d,'personal',self.b)
        d=copy.deepcopy(self.d);d['stages'][0]['locked']=True
        with self.assertRaises(Invalid):preview(d,'personal',self.b)
    def test_api_preview_atomic_commit_stale_and_permissions(self):
        U=get_user_model();admin=U.objects.create_user('pairing-root',is_superuser=True);other=U.objects.create_user('pairing-other')
        e=Event.objects.create(name='个人赛',kind='personal',document=self.d)
        url='/api/events/'+str(e.id)+'/'
        self.client.force_login(admin)
        def post(action,**kw):return self.client.post(url,dict(action=action,revision=e.revision,**kw),content_type='application/json')
        r=post('pairing-preview',**self.b);self.assertEqual(r.status_code,200,r.content)
        e.refresh_from_db();self.assertEqual(e.document,self.d);self.assertEqual(Audit.objects.count(),0)
        token=r.json()['token'];r=post('pairing-commit',token=token)
        self.assertEqual(r.status_code,200,r.content);e.refresh_from_db()
        self.assertEqual(len(e.document['matches']),2);self.assertEqual(Audit.objects.count(),1)
        self.assertEqual(post('pairing-commit',token=token).status_code,400)
        self.client.force_login(other);self.assertEqual(post('pairing-preview',**self.b).status_code,404)

    def test_tied_first_counts_as_first_and_shares_bonus(self):
        from .domain import score
        from .projection import statistics,rank_metrics
        from .history_correction import totals
        seats=score(self.d['rules'][-1],[35000,35000,20000,10000])
        self.assertEqual([s['rank'] for s in seats],[1,1,3,4])
        self.assertEqual([s['points'] for s in seats],[350,350,-200,-500])
        for i,s in enumerate(seats):s['playerId']=str(i)
        payload={'results':[{'date':'2026-09-13','number':1,'stageId':'regular','seats':seats}]}
        t=totals(payload,'all','player','0')
        self.assertEqual(t['places'],[1,0,0,0]);self.assertEqual(t['avgRank'],1)
        self.assertEqual(t['topRate'],1)
        payload['statistics']={'all':{'raw':{'player':[{'id':'0','total':350}]}}}
        self.assertEqual(rank_metrics(payload)['statistics']['all']['raw']['player'][0]['total'],350)

    def test_auto_numbers_colors_and_short_scores(self):
        d=initial()
        for i in range(10):d=apply(d,'team','team',{'name':str(i)})
        self.assertEqual(len({t['color'] for t in d['teams']}),10)
        for i in range(4):d=apply(d,'team','player',dict(name=str(i),teamId=d['teams'][i]['id']))
        self.assertEqual([p['number'] for p in d['players']],['1','2','3','4'])
        with self.assertRaises(Invalid):apply(d,'team','team-update',dict(id=d['teams'][0]['id'],color=d['teams'][1]['color']))
        with self.assertRaises(Invalid):apply(d,'team','player-update',dict(id=d['players'][0]['id'],number='2'))
        d=commit(self.d,'personal',preview(self.d,'personal',self.b));mid=d['matches'][0]['id']
        d=apply(d,'personal','score',dict(id=mid,scores=[350,350,200,100]))
        self.assertEqual([s['score'] for s in d['matches'][0]['seats']],[35000,35000,20000,10000])
        with self.assertRaisesRegex(Invalid,'当前总分'):apply(d,'personal','score',dict(id=mid,scores=[35000]*4))

    def test_create_next_stage_only_on_settlement_and_auto_qualify(self):
        from .projection import settlement_preview,settle
        d=self.publish(commit(self.d,'personal',preview(self.d,'personal',self.b)))
        d=apply(d,'personal','stage-update',dict(id=d['stages'][0]['id'],name='预选',advanceCount=4))
        p=settlement_preview(d,'personal',dict(source=d['stages'][0]['id'],targetName='决赛'))
        self.assertEqual(len(d['stages']),1);self.assertEqual(len(p['rows']),4)
        self.assertEqual(p['createdStage']['name'],'决赛');self.assertEqual(p['roundingMode'],'ceil')
        changed=settle(d,p,{})
        self.assertEqual(len(changed['stages']),2);self.assertTrue(changed['stages'][0]['locked'])
        self.assertEqual(changed['stages'][1]['id'],p['target'])
        with self.assertRaises(Invalid):settlement_preview(d,'personal',dict(source=d['stages'][0]['id'],targetName='预选'))
