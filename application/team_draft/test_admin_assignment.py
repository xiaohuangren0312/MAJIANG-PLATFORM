from django.test import TestCase
from django.core.exceptions import PermissionDenied
from league.domain import Invalid
from . import tests as fixtures
from .models import DraftAudit
from .lifecycle import preview

class AdminAssignmentTests(TestCase):
    setUp=fixtures.AuctionTests.setUp
    call=fixtures.ActivityTests.call
    setup_activity=fixtures.ActivityTests.setup_activity
    lot_call=fixtures.AuctionTests.lot_call
    def test_assign_preview_and_refund_reassign(self):
        self.lot_call('assign-second',teamId='t0',price=7)
        self.assertEqual(self.activity.document['teams'][0]['balance'],20)
        self.lot_call('assign-second',teamId='t1',price=4)
        self.assertEqual([t['balance'] for t in self.activity.document['teams']],[27,23])
        self.assertEqual(len(self.activity.document['lots']),1)
        self.assertEqual(self.activity.document['allocations'][-1]['teamId'],'t1')
        self.event.refresh_from_db();self.assertEqual(self.event.document['players'][4]['teamId'],'t1')
    def test_bid_in_progress_override_and_undo(self):
        self.lot_call('open-bidding');self.lot_call('bid',self.users[0],price=5)
        self.lot_call('assign-second',teamId='t1',price=0)
        p=preview(self.activity.pk,self.admin,self.activity.revision,'undo')
        self.call('undo',previewToken=p['token'])
        self.assertEqual(self.activity.document['lot']['state'],'bidding')
        self.assertEqual(self.activity.document['lot']['leader'],'t0')
        self.assertEqual([t['balance'] for t in self.activity.document['teams']],[27,27])
    def test_invalid_inputs_permissions_and_stale_lot(self):
        for value in [-1,28,True,1.5]:
            with self.assertRaises(Invalid):self.lot_call('assign-second',teamId='t0',price=value)
        with self.assertRaises(Invalid):self.lot_call('assign-second',teamId='foreign',price=0)
        with self.assertRaises(PermissionDenied):self.lot_call('assign-second',self.users[0],teamId='t0',price=0)
        with self.assertRaises(Invalid):self.call('assign-second',lotId='old',teamId='t0',price=0)
        self.activity.document['teams'][0]['capacity']=2;self.activity.save()
        with self.assertRaises(Invalid):self.lot_call('assign-second',teamId='t0',price=0)
    def test_sold_correction_and_failed_change_keeps_original(self):
        self.lot_call('open-bidding');self.lot_call('bid',self.users[0],price=5);self.lot_call('pass',self.users[1]);self.lot_call('confirm-lot')
        with self.assertRaises(Invalid):self.lot_call('assign-second',teamId='t1',price=100)
        self.activity.refresh_from_db();self.assertEqual(self.activity.document['teams'][0]['balance'],22)
        self.lot_call('assign-second',teamId='t0',price=27)
        self.assertEqual(self.activity.document['teams'][0]['balance'],0)
    def test_unsold_correction_and_next_lot_boundary(self):
        self.lot_call('open-bidding')
        for u in self.users:self.lot_call('pass',u)
        self.lot_call('confirm-lot');self.lot_call('assign-second',teamId='t1',price=0)
        self.assertEqual(self.activity.document['candidates'][2]['state'],'allocated')
        self.lot_call('next-lot')
        with self.assertRaises(Invalid):self.lot_call('assign-second',teamId='t0',price=0)

    def test_admin_unsold_refunds_and_undo(self):
        self.lot_call('assign-second',teamId='t0',price=7)
        self.lot_call('mark-unsold')
        self.assertEqual(self.activity.document['teams'][0]['balance'],27)
        self.assertEqual(self.activity.document['lot']['outcome'],'unsold')
        self.assertEqual(self.activity.document['candidates'][2]['state'],'third-pool')
        self.assertEqual(len(self.activity.document['lots']),1)
        self.event.refresh_from_db();self.assertFalse(self.event.document['players'][4].get('teamId'))
        p=preview(self.activity.pk,self.admin,self.activity.revision,'undo')
        self.call('undo',previewToken=p['token'])
        self.assertEqual(self.activity.document['lot']['outcome'],'assigned')
        self.assertEqual(self.activity.document['teams'][0]['balance'],20)
    def test_admin_unsold_during_bidding_and_permissions(self):
        with self.assertRaises(PermissionDenied):self.lot_call('mark-unsold',self.users[0])
        with self.assertRaises(Invalid):self.call('mark-unsold',lotId='old')
        self.lot_call('open-bidding');self.lot_call('bid',self.users[0],price=5)
        self.lot_call('mark-unsold')
        self.assertEqual(self.activity.document['lot']['state'],'settled')
        self.assertEqual([t['balance'] for t in self.activity.document['teams']],[27,27])
        self.lot_call('next-lot')
        with self.assertRaises(Invalid):self.lot_call('mark-unsold')

    def test_full_teams_automatically_skip_without_coach_response(self):
        self.activity.document['teams'][0]['capacity']=2
        self.activity.save()
        self.lot_call('open-bidding')
        self.assertEqual(self.activity.document['lot']['turn'],'t1')
        with self.assertRaises(Invalid):self.lot_call('bid',self.users[0],price=1)
        self.lot_call('bid',self.users[1],price=1)
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
    def test_all_full_teams_go_straight_to_unsold_confirmation(self):
        for t in self.activity.document['teams']:t['capacity']=2
        self.activity.save()
        self.lot_call('open-bidding')
        self.assertIsNone(self.activity.document['lot']['turn'])
        self.assertEqual(self.activity.document['lot']['state'],'awaiting-confirm')
        self.lot_call('confirm-lot')
        self.assertEqual(self.activity.document['lot']['outcome'],'unsold')

    def test_opening_bid_equals_start_price_in_both_stages(self):
        from .domain import auction
        import copy
        doc=copy.deepcopy(self.event.document)
        doc['draft']=copy.deepcopy(self.activity.document)
        for stage in (2,3):
            d=copy.deepcopy(doc)
            d['draft']['lot'].update(stage=stage,startPrice=2,minimum=2)
            lot_id=d['draft']['lot']['id']
            d=auction(d,'open-bidding',{'lotId':lot_id})
            self.assertEqual(d['draft']['lot']['minimum'],2)
            first=d['draft']['lot']['turn']
            with self.assertRaises(Invalid):auction(d,'bid',{'lotId':lot_id,'price':1},first)
            d=auction(d,'bid',{'lotId':lot_id,'price':2},first)
            self.assertEqual(d['draft']['lot']['price'],2)
            self.assertEqual(d['draft']['lot']['minimum'],3)

    def test_third_admin_direct_assignment_correction_and_undo(self):
        self.lot_call('mark-unsold');self.lot_call('next-lot');self.call('draw-third');self.lot_id=self.activity.document['lot']['id']
        with self.assertRaises(PermissionDenied):self.lot_call('admin-third',self.users[0],teamId='t0',price=2)
        with self.assertRaises(Invalid):self.lot_call('admin-third',teamId='t0',price=28)
        self.lot_call('admin-third',teamId='t0',price=2)
        self.assertEqual(self.activity.document['teams'][0]['balance'],25)
        self.lot_call('admin-third',teamId='t1',price=0)
        self.assertEqual([t['balance'] for t in self.activity.document['teams']],[27,27])
        p=preview(self.activity.pk,self.admin,self.activity.revision,'undo')
        self.call('undo',previewToken=p['token'])
        self.assertEqual(self.activity.document['lot']['assignedTeam'],'t0')
        self.assertEqual(self.activity.document['teams'][0]['balance'],25)
    def test_third_admin_override_bid(self):
        self.lot_call('mark-unsold');self.lot_call('next-lot');self.call('draw-third');self.lot_id=self.activity.document['lot']['id']
        self.lot_call('open-bidding')
        tid=self.activity.document['lot']['turn']
        self.lot_call('bid',self.users[int(tid[1:])],price=3)
        self.lot_call('admin-third',teamId='t0',price=1)
        self.assertEqual(self.activity.document['lot']['assignedPrice'],1)
        self.assertEqual(self.activity.document['lot']['state'],'settled')

    def test_third_full_team_rejected_without_roster_or_budget_change(self):
        import copy
        self.lot_call('mark-unsold');self.lot_call('next-lot');self.call('draw-third')
        self.lot_id=self.activity.document['lot']['id']
        self.activity.document['teams'][0]['capacity']=2;self.activity.save()
        original=copy.deepcopy(self.activity.document)
        self.event.refresh_from_db();roster=copy.deepcopy(self.event.document)
        with self.assertRaisesMessage(Invalid,'队伍人数已满'):
            self.lot_call('admin-third',teamId='t0',price=0)
        self.activity.refresh_from_db();self.event.refresh_from_db()
        self.assertEqual(self.activity.document,original)
        self.assertEqual(self.event.document,roster)
