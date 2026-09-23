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
