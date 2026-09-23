from django.test import TestCase
from django.core.exceptions import PermissionDenied
from league.domain import Invalid
from . import tests as fixtures
from .lifecycle import preview

class LiveControlsTests(TestCase):
    setUp=fixtures.AuctionTests.setUp
    call=fixtures.ActivityTests.call
    setup_activity=fixtures.ActivityTests.setup_activity
    lot_call=fixtures.AuctionTests.lot_call
    def edit(self,price=9):
        self.call('edit-candidates',candidates=[dict(playerId='p2',startPrice=price,description='最新介绍')])
    def rollback(self):
        p=preview(self.activity.pk,self.admin,self.activity.revision,'rollback')
        self.call('rollback',previewToken=p['token'])
    def test_edit_preview_and_bid_preserves_current_price(self):
        self.edit();self.assertEqual(self.activity.document['lot']['startPrice'],9)
        self.lot_call('open-bidding');self.lot_call('bid',self.users[0],price=9)
        self.edit(12)
        self.assertEqual(self.activity.document['lot']['price'],9)
        self.assertEqual(self.activity.document['lot']['startPrice'],9)
        self.assertEqual(self.activity.document['candidates'][2]['startPrice'],12)
    def test_rollback_refund_continuous_and_metadata(self):
        self.lot_call('assign-second',teamId='t0',price=7);self.edit()
        self.rollback()
        self.assertEqual(self.activity.document['phase'],'revealed')
        self.assertEqual(self.activity.document['teams'][0]['balance'],27)
        self.event.refresh_from_db();self.assertFalse(self.event.document['players'][4].get('teamId'))
        self.assertEqual(self.activity.document['candidates'][2]['description'],'最新介绍')
        self.rollback();self.assertEqual(self.activity.status,'setup')
        self.assertEqual(self.activity.document['candidates'][2]['startPrice'],9)
        self.call('start');self.rollback();self.assertEqual(self.activity.status,'setup')
    def test_permissions_stale_preview_and_external_change(self):
        with self.assertRaises(PermissionDenied):self.call('edit-candidates',self.users[0],candidates=[])
        with self.assertRaises(PermissionDenied):preview(self.activity.pk,self.users[0],self.activity.revision,'rollback')
        p=preview(self.activity.pk,self.admin,self.activity.revision,'rollback')
        self.edit()
        with self.assertRaises(Invalid):self.call('rollback',previewToken=p['token'])
        self.event.refresh_from_db();self.event.revision+=1;self.event.save()
        with self.assertRaises(Invalid):preview(self.activity.pk,self.admin,self.activity.revision,'rollback')
    def test_invalid_edit_atomic(self):
        for value in [-1,True,1.5]:
            with self.assertRaises(Invalid):self.edit(value)
        with self.assertRaises(Invalid):self.call('edit-candidates',candidates=[dict(playerId='foreign',startPrice=0)])
