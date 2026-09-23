from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from league.models import Event,Audit
from league.domain import initial,Invalid
from .models import DraftActivity,DraftAudit
from .services import create,mutate,projection

class ActivityTests(TestCase):
    def setUp(self):
        U=get_user_model();self.admin=U.objects.create_user('draft-root',is_superuser=True)
        self.users=[U.objects.create_user('draft-coach'+str(i)) for i in range(2)]
        self.outside=U.objects.create_user('draft-outside')
        d=initial();d['teams']=[dict(id='t'+str(i),name='队'+str(i),active=True) for i in range(2)]
        d['players']=[dict(id=p,name=p,teamId=None,active=True) for p in ['c0','c1','p0','p1','p2']]
        self.event=Event.objects.create(name='测试赛事',kind='team',document=d,is_test=True)
        self.activity=create(self.admin,'独立活动')
        self.payload=dict(teams=[dict(teamId='t'+str(i),coachUserId=u.pk,coachPlayerId='c'+str(i),coachPrice=3) for i,u in enumerate(self.users)],candidates=[dict(playerId='p'+str(i)) for i in range(3)])
    def call(self,action,user=None,**body):
        self.activity.refresh_from_db();self.activity=mutate(self.activity.pk,user or self.admin,self.activity.revision,action,body);return self.activity
    # Legacy fixtures retain immediate-write semantics for compatibility coverage.
    @override_settings(HQL_DRAFT_STAGED=False)
    def setup_activity(self):
        self.call('link',eventId=str(self.event.pk));self.call('configure',**self.payload)
    def test_activity_created_unlinked(self):
        self.assertIsNone(self.activity.event_id);self.assertEqual(self.activity.document,{})
        with self.assertRaises(Invalid):self.call('configure',**self.payload)
    def test_configuration_is_independent_and_does_not_double_charge(self):
        self.setup_activity();self.call('configure',**self.payload)
        self.event.refresh_from_db()
        self.assertNotIn('draft',self.event.document);self.assertEqual(self.event.revision,1)
        self.assertFalse(Audit.objects.exists());self.assertEqual(self.activity.document['teams'][0]['balance'],27)
    def test_unique_link_and_locked_after_start(self):
        self.setup_activity();other=create(self.admin,'其他活动')
        with self.assertRaises(Invalid):mutate(other.pk,self.admin,1,'link',{'eventId':str(self.event.pk)})
        self.call('start')
        with self.assertRaises(Invalid):self.call('link',eventId=str(self.event.pk))
    def test_relink_clears_configuration_only(self):
        self.setup_activity();other=Event.objects.create(name='另一赛事',kind='team',document=initial())
        self.call('link',eventId=str(other.pk));self.assertEqual(self.activity.document,{})
        self.event.refresh_from_db();self.assertEqual(self.event.revision,1)
    def test_reject_personal_history_started_event(self):
        for kind,d in [('personal',initial()),('team',dict(initial(),historySnapshot={'id':'s2'})),('team',dict(initial(),matches=[{'state':'published'}]))]:
            other=Event.objects.create(name='无效赛事',kind=kind,document=d)
            with self.assertRaises(Invalid):self.call('link',eventId=str(other.pk))
    def test_private_choices_then_atomic_roster(self):
        self.setup_activity();self.call('start');self.call('nominate',self.users[0],playerId='p0')
        out=projection(self.activity,self.users[1]);self.assertNotIn('nominations',out['draft']);self.assertIsNone(out['draft']['myPick'])
        with self.assertRaises(Invalid):self.call('reveal')
        self.call('nominate',self.users[1],playerId='p1');self.call('reveal');self.call('continue')
        self.assertEqual(self.activity.document['phase'],'auction-ready')
        self.event.refresh_from_db();self.assertNotIn('draft',self.event.document)
        self.assertEqual(next(p for p in self.event.document['players'] if p['id']=='p0')['teamId'],'t0')
        self.assertEqual(self.activity.document['teams'][0]['balance'],27)
    def test_roll_tie_and_retry(self):
        self.setup_activity();self.call('start')
        for u in self.users:self.call('nominate',u,playerId='p0')
        self.call('reveal')
        with patch('secrets.randbelow',side_effect=[49,49]):self.call('roll',playerId='p0')
        self.assertEqual(len(self.activity.document['conflicts']),1)
        with patch('secrets.randbelow',side_effect=[90,20]):self.call('roll',playerId='p0')
        self.call('continue');self.assertEqual(self.activity.document['pending'],['t1'])
        self.call('nominate',self.users[1],playerId='p1');self.call('reveal');self.call('continue')
        self.assertEqual(self.activity.document['phase'],'auction-ready')
    def test_permissions_and_stale_revision(self):
        with self.assertRaises(PermissionDenied):create(self.outside,'越权')
        self.setup_activity()
        with self.assertRaises(PermissionDenied):self.call('start',self.users[0])
        with self.assertRaises(Invalid):mutate(self.activity.pk,self.admin,1,'start',{})
        with self.assertRaises(PermissionDenied):projection(self.activity,self.outside)
    def test_invalid_configuration_rolls_back(self):
        self.call('link',eventId=str(self.event.pk));revision=self.activity.revision
        self.payload['teams'][0]['coachPrice']=31
        with self.assertRaises(Invalid):self.call('configure',**self.payload)
        self.activity.refresh_from_db();self.assertEqual(self.activity.revision,revision);self.assertEqual(self.activity.document,{})
    def test_roster_failure_rolls_back_both_records(self):
        self.setup_activity();self.call('start')
        for i,u in enumerate(self.users):self.call('nominate',u,playerId='p'+str(i))
        self.event.refresh_from_db();d=self.event.document;d['players'][3]['teamId']='t0';self.event.document=d;self.event.save()
        old=self.activity.revision
        with self.assertRaises(Invalid):self.call('reveal')
        self.activity.refresh_from_db();self.event.refresh_from_db()
        self.assertEqual(self.activity.revision,old);self.assertEqual(self.activity.document['allocations'],[])
        self.assertIsNone(self.event.document['players'][2]['teamId'])
    def test_api_routes_no_automatic_event(self):
        self.client.force_login(self.admin)
        r=self.client.post('/api/draft/',{'name':'新活动'},content_type='application/json');self.assertEqual(r.status_code,201)
        url='/api/draft/'+r.json()['id']+'/'
        self.assertIsNone(self.client.get(url).json()['eventId'])
        self.assertContains(self.client.get('/draft/'),'先创建活动，再手动关联赛事')
        self.assertContains(self.client.get('/draft/'+r.json()['id']+'/'),'手动选择关联赛事')
        self.client.force_login(self.outside);self.assertEqual(self.client.get(url).status_code,403)


class AuctionTests(TestCase):
    call=ActivityTests.call
    setup_activity=ActivityTests.setup_activity
    def setUp(self):
        ActivityTests.setUp(self)
        self.setup_activity();self.call('start')
        for i,u in enumerate(self.users):self.call('nominate',u,playerId='p'+str(i))
        self.call('reveal');self.call('continue');self.call('draw')
        self.lot_id=self.activity.document['lot']['id']
    def lot_call(self,action,user=None,**body):return self.call(action,user,lotId=self.lot_id,**body)
    def test_turns_confirmation_and_single_deduction(self):
        self.lot_call('open-bidding')
        with self.assertRaises(Invalid):self.lot_call('bid',self.users[1],price=2)
        self.lot_call('bid',self.users[0],price=3)
        self.assertEqual(self.activity.document['lot']['turn'],'t1')
        with self.assertRaises(Invalid):self.lot_call('confirm-lot')
        self.lot_call('bid',self.users[1],price=4)
        self.lot_call('pass',self.users[0])
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
        self.assertEqual(self.activity.document['teams'][1]['balance'],27)
        self.lot_call('confirm-lot')
        self.event.refresh_from_db()
        self.assertEqual(self.activity.document['teams'][1]['balance'],23)
        self.assertEqual(next(p for p in self.event.document['players'] if p['id']=='p2')['teamId'],'t1')
        with self.assertRaises(Invalid):self.lot_call('confirm-lot')
        self.lot_call('next-lot');self.assertEqual(self.activity.document['phase'],'review-ready')
    def test_all_pass_enters_third_pool(self):
        self.lot_call('open-bidding')
        for u in self.users:self.lot_call('pass',u)
        self.lot_call('confirm-lot')
        self.assertEqual(self.activity.document['candidates'][2]['state'],'third-pool')
        self.assertEqual([t['balance'] for t in self.activity.document['teams']],[27,27])
        self.event.refresh_from_db();self.assertIsNone(self.event.document['players'][4]['teamId'])
    def test_pass_cannot_return_and_zero_bid_is_valid(self):
        self.lot_call('open-bidding');self.lot_call('pass',self.users[0])
        with self.assertRaises(Invalid):self.lot_call('bid',self.users[0],price=20)
        self.lot_call('bid',self.users[1],price=0)
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
        self.lot_call('confirm-lot');self.assertEqual(self.activity.document['allocations'][-1]['price'],0)
    def test_budget_minimum_stale_and_permissions(self):
        self.lot_call('open-bidding')
        for value in [-1,28,1.5,True]:
            with self.assertRaises(Invalid):self.lot_call('bid',self.users[0],price=value)
        with self.assertRaises(Invalid):self.call('bid',self.users[0],lotId='old',price=1)
        with self.assertRaises(Invalid):self.lot_call('bid',self.admin,price=1)
        self.lot_call('bid',self.users[0],price=1)
        with self.assertRaises(Invalid):self.lot_call('bid',self.users[1],price=1)
        with self.assertRaises(PermissionDenied):self.lot_call('confirm-lot',self.users[1])
    def test_ineligible_team_skipped_with_reason(self):
        self.activity.document['teams'][0]['capacity']=2;self.activity.save()
        self.lot_call('open-bidding')
        self.assertEqual(self.activity.document['lot']['turn'],'t1')
        self.assertEqual(self.activity.document['lot']['excluded']['t0'],'人数已满')
    def test_roster_change_blocks_confirmation_without_charging(self):
        self.lot_call('open-bidding');self.lot_call('bid',self.users[0],price=4);self.lot_call('pass',self.users[1])
        self.event.refresh_from_db();self.event.document['players'][4]['teamId']='t1';self.event.save()
        with self.assertRaises(Invalid):self.lot_call('confirm-lot')
        self.activity.refresh_from_db();self.assertEqual(self.activity.document['teams'][0]['balance'],27)
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
    def test_http_coach_response_and_hidden_user_ids(self):
        self.lot_call('open-bidding');self.client.force_login(self.users[0])
        url='/api/draft/'+str(self.activity.pk)+'/'
        response=self.client.post(url,{'action':'bid','revision':self.activity.revision,'lotId':self.lot_id,'price':2},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertNotIn('coachUserId',response.json()['draft']['teams'][0])
        self.assertEqual(response.json()['draft']['lot']['leader'],'t0')

    def test_finished_first_pick_with_no_remaining_pool(self):
        from .domain import first_pick
        self.event.refresh_from_db()
        doc=dict(self.event.document)
        draft=dict(self.activity.document)
        draft.update(phase='revealed',conflicts=[],candidates=[c for c in draft['candidates'] if c['state']=='allocated'])
        doc['draft']=draft
        self.assertEqual(first_pick(doc,'continue',{})['draft']['phase'],'review-ready')


class ThirdRoundTests(TestCase):
    call=ActivityTests.call
    setup_activity=ActivityTests.setup_activity
    lot_call=AuctionTests.lot_call
    def setUp(self):
        AuctionTests.setUp(self)
        self.lot_call('open-bidding')
        for u in self.users:self.lot_call('pass',u)
        self.lot_call('confirm-lot');self.lot_call('next-lot')
        self.call('draw-third');self.lot_id=self.activity.document['lot']['id']
        self.lot_call('open-bidding')
    def pass_all(self):
        while self.activity.document['lot']['state']=='bidding':
            tid=self.activity.document['lot']['turn'];self.lot_call('pass',self.users[int(tid[-1])])
    def test_second_round_pass_resets_and_bid_price_locked(self):
        lot=self.activity.document['lot'];self.assertEqual(lot['passed'],[])
        bidder=self.users[int(lot['turn'][-1])]
        self.lot_call('bid',bidder,price=5)
        self.pass_all()
        with self.assertRaises(Invalid):self.lot_call('assign-third',teamId='t0',price=0)
        with self.assertRaises(Invalid):self.lot_call('confirm-lot')
        self.lot_call('assign-third',teamId='t0',price=5)
        self.assertEqual(self.activity.document['teams'][0]['balance'],22)
        self.assertEqual(self.activity.document['lots'][-1]['assignedTeam'],'t0')
        self.event.refresh_from_db();self.assertEqual(self.event.document['players'][4]['teamId'],'t0')
    def test_all_pass_free_assignment_and_completion_boundary(self):
        self.pass_all();self.lot_call('assign-third',teamId='t1',price=0)
        self.assertEqual(self.activity.document['teams'][1]['balance'],27)
        self.assertEqual(self.activity.document['allocations'][-1]['method'],'third-round')
        with self.assertRaises(Invalid):self.lot_call('assign-third',teamId='t1',price=0)
        self.lot_call('next-lot');self.assertEqual(self.activity.document['phase'],'review-ready')
    def test_no_early_assignment_or_coach_assignment(self):
        with self.assertRaises(Invalid):self.lot_call('assign-third',teamId='t0',price=0)
        self.pass_all()
        with self.assertRaises(PermissionDenied):self.lot_call('assign-third',self.users[0],teamId='t0',price=0)
    def test_invalid_team_price_and_capacity_leave_both_unchanged(self):
        self.pass_all()
        for team,price in [('foreign',0),('t0',-1),('t0',28),('t0',False),('t0',1.5)]:
            with self.assertRaises(Invalid):self.lot_call('assign-third',teamId=team,price=price)
        self.activity.document['teams'][0]['capacity']=2;self.activity.save()
        with self.assertRaises(Invalid):self.lot_call('assign-third',teamId='t0',price=0)
        self.event.refresh_from_db();self.activity.refresh_from_db()
        self.assertIsNone(self.event.document['players'][4]['teamId'])
        self.assertEqual(self.activity.document['teams'][0]['balance'],27)
    def test_api_admin_assigns_custom_price_after_all_pass(self):
        self.pass_all();self.client.force_login(self.admin)
        r=self.client.post('/api/draft/'+str(self.activity.pk)+'/',dict(action='assign-third',revision=self.activity.revision,lotId=self.lot_id,teamId='t1',price=2),content_type='application/json')
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(r.json()['draft']['teams'][1]['balance'],25)
