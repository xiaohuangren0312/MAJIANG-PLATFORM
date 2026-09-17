from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from league.domain import Invalid
from league.lifecycle import cleanup_preview
from . import tests as fixtures
from .services import projection
from .lifecycle import preview
from .models import DraftAudit

class LifecycleTests(TestCase):
    setUp=fixtures.AuctionTests.setUp
    call=fixtures.ActivityTests.call
    setup_activity=fixtures.ActivityTests.setup_activity
    lot_call=fixtures.AuctionTests.lot_call
    def settle(self):
        self.lot_call('open-bidding')
        self.lot_call('bid',self.users[0],price=5)
        self.lot_call('pass',self.users[1])
        self.lot_call('confirm-lot')
    def control(self,action):
        self.activity.refresh_from_db()
        result=preview(self.activity.pk,self.admin,self.activity.revision,action)
        self.call(action,previewToken=result['token'])
        return result
    def test_finish_without_third_candidates_and_immutable_snapshot(self):
        self.settle();self.lot_call('next-lot')
        result=self.control('finish')
        self.assertEqual(result['unassigned'],[])
        self.assertEqual(self.activity.status,'complete')
        self.event.refresh_from_db();self.assertNotIn('archive',self.event.document)
        with self.assertRaises(Invalid):self.call('draw-third')
        with self.assertRaises(Invalid):self.control('undo')
        original=projection(self.activity,self.admin)['players']
        self.event.document['players'][0]['name']='later rename';self.event.save()
        self.assertEqual(projection(self.activity,self.admin)['players'],original)
        self.call('unlink')
        self.assertIsNone(self.activity.event_id)
        self.assertEqual(projection(self.activity,self.admin)['players'],original)
        self.assertTrue(DraftAudit.objects.filter(activity=self.activity,action='finish').exists())
    def test_finish_rejects_open_lot_and_remaining_capacity(self):
        with self.assertRaises(Invalid):self.control('finish')
        self.lot_call('open-bidding')
        for u in self.users:self.lot_call('pass',u)
        self.lot_call('confirm-lot');self.lot_call('next-lot')
        with self.assertRaises(Invalid):self.control('finish')
    def test_all_full_can_finish_with_explicit_unassigned(self):
        self.lot_call('open-bidding')
        for u in self.users:self.lot_call('pass',u)
        self.lot_call('confirm-lot');self.lot_call('next-lot')
        for row in self.activity.document['teams']:row['capacity']=2
        self.activity.save()
        result=self.control('finish')
        self.assertEqual([p['playerId'] for p in result['unassigned']],['p2'])
        self.event.refresh_from_db();self.assertIsNone(self.event.document['players'][-1]['teamId'])
    def test_undo_restores_roster_budget_and_lot(self):
        self.settle()
        result=self.control('undo')
        self.assertEqual(result['action'],'confirm-lot')
        self.assertEqual(self.activity.document['teams'][0]['balance'],27)
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
        self.event.refresh_from_db();self.assertIsNone(self.event.document['players'][-1]['teamId'])
        with self.assertRaises(Invalid):self.control('undo')
    def test_external_changes_and_stale_preview_prevent_undo(self):
        self.settle()
        data=preview(self.activity.pk,self.admin,self.activity.revision,'undo')
        self.event.refresh_from_db();self.event.revision+=1;self.event.save()
        with self.assertRaises(Invalid):self.call('undo',previewToken=data['token'])
        with self.assertRaises(Invalid):self.control('undo')
    def test_following_operation_prevents_old_undo(self):
        self.settle()
        data=preview(self.activity.pk,self.admin,self.activity.revision,'undo')
        self.lot_call('next-lot')
        with self.assertRaises(Invalid):self.call('undo',previewToken=data['token'])
        self.event.refresh_from_db();self.assertEqual(self.event.document['players'][-1]['teamId'],'t0')
    def test_private_default_public_opt_in_no_accounts_or_nominations(self):
        url='/api/draft/'+str(self.activity.pk)+'/'
        self.assertEqual(self.client.get(url).status_code,401)
        self.call('publish',public=True)
        r=self.client.get(url);self.assertEqual(r.status_code,200)
        row=r.json()['draft']['teams'][0]
        self.assertNotIn('coachUserId',row);self.assertNotIn('coachUsername',row)
        self.assertNotIn('eventSnapshot',r.json()['draft'])
        self.assertEqual(self.client.post(url,dict(action='draw',revision=self.activity.revision),content_type='application/json').status_code,401)
        self.call('publish',public=False)
        self.assertEqual(self.client.get(url).status_code,401)
    def test_event_cleanup_has_actionable_guard(self):
        self.event.document['archive']={'test':True};self.event.save()
        with self.assertRaisesMessage(Invalid,'选人活动'):cleanup_preview(self.event)
    def test_active_unlink_blocked(self):
        with self.assertRaises(Invalid):self.call('unlink')
    def test_anonymous_listing_filters_private(self):
        self.assertEqual(self.client.get('/api/draft/').json()['activities'],[])
        self.call('publish',public=True)
        self.assertEqual(len(self.client.get('/api/draft/').json()['activities']),1)

    def test_full_teams_can_finish_after_opening_third_lot(self):
        self.lot_call('open-bidding')
        for u in self.users:self.lot_call('pass',u)
        self.lot_call('confirm-lot');self.lot_call('next-lot')
        for row in self.activity.document['teams']:row['capacity']=2
        self.activity.save()
        self.call('draw-third');self.lot_id=self.activity.document['lot']['id']
        self.lot_call('open-bidding')
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
        for team in ('t0','t1'):
            with self.assertRaises(Invalid):self.lot_call('assign-third',teamId=team,price=0)
        result=self.control('finish')
        self.assertEqual([p['playerId'] for p in result['unassigned']],['p2'])
        self.assertEqual(self.activity.status,'complete')
        self.assertEqual([t['balance'] for t in self.activity.document['teams']],[27,27])

    def test_old_undo_token_after_setup_unlink_is_controlled_error(self):
        # A second isolated activity exercises a stale browser's signed token.
        from copy import deepcopy
        from league.models import Event
        from .services import create
        doc=deepcopy(self.event.document)
        for player in doc['players']:player['teamId']=None
        self.event=Event.objects.create(name='隔离解除关联测试',kind='team',document=doc,is_test=True)
        self.activity=create(self.admin,'解除关联临时活动')
        self.setup_activity()
        token=preview(self.activity.pk,self.admin,self.activity.revision,'undo')['token']
        self.call('unlink')
        with self.assertRaisesMessage(Invalid,'解除关联'):
            self.call('undo',previewToken=token)

    def test_bad_event_uuid_is_http_400(self):
        self.client.force_login(self.admin)
        response=self.client.post('/api/draft/'+str(self.activity.pk)+'/',dict(action='link',revision=self.activity.revision,eventId='not-a-uuid'),content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_completed_public_projection_omits_full_snapshot_and_accounts(self):
        self.settle();self.control('finish');self.call('publish',public=True)
        self.assertIn('eventSnapshot',self.activity.document)
        result=projection(self.activity,AnonymousUser())
        self.assertNotIn('eventSnapshot',result['draft'])
        self.assertNotIn('eventIdentity',result['draft'])
        self.assertNotIn('nominations',result['draft'])
        for team in result['draft']['teams']:
            self.assertNotIn('coachUserId',team);self.assertNotIn('coachUsername',team)
        self.call('unlink')
        self.assertEqual(projection(self.activity,AnonymousUser())['players'],result['players'])

    def test_undo_reveal_restores_secret_nomination_phase(self):
        from .services import create
        from league.models import Event
        from copy import deepcopy
        doc=deepcopy(self.event.document)
        for player in doc['players']:player['teamId']=None
        self.event=Event.objects.create(name='隔离公布撤销测试',kind='team',document=doc,is_test=True)
        self.activity=create(self.admin,'公布撤销临时活动')
        self.setup_activity();self.call('publish',public=True);self.call('start')
        for i,u in enumerate(self.users):self.call('nominate',u,playerId='p'+str(i))
        self.call('reveal');self.control('undo')
        self.assertEqual(self.activity.document['phase'],'nomination')
        self.assertEqual(self.activity.document['allocations'],[])
        self.event.refresh_from_db()
        self.assertIsNone(next(p for p in self.event.document['players'] if p['id']=='p0')['teamId'])
        public=projection(self.activity,AnonymousUser())['draft']
        self.assertEqual(public['reveals'],[])
        self.assertNotIn('nominations',public);self.assertIsNone(public['myPick'])
        self.assertEqual(projection(self.activity,self.users[0])['draft']['myPick'],'p0')

    def test_external_bond_change_blocks_allocation(self):
        self.lot_call('open-bidding')
        self.lot_call('bid',self.users[0],price=5)
        self.lot_call('pass',self.users[1])
        self.event.refresh_from_db()
        self.event.document['players'][-1]['bond']=True
        self.event.save()
        with self.assertRaises(Invalid):self.lot_call('confirm-lot')
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.document['teams'][0]['balance'],27)

    def test_detached_completed_activity_does_not_block_cleanup_preview(self):
        self.settle();self.lot_call('next-lot');self.control('finish');self.call('unlink')
        self.event.refresh_from_db();self.event.document['archive']={'test':True};self.event.save()
        self.assertEqual(cleanup_preview(self.event)['eventId'],str(self.event.pk))
        self.assertTrue(DraftAudit.objects.filter(activity=self.activity,action='finish').exists())
