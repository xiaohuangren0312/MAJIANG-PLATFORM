"""Real PostgreSQL connections exercise locking and all-or-nothing roster writes.

Run with a dedicated TEST database; these tests never use the development data.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection, connections, close_old_connections
from django.test import TransactionTestCase

from league.domain import Invalid
from league.models import Event, Audit
from . import tests as fixtures
from .models import DraftActivity, DraftAudit
from .services import mutate


@skipUnless(connection.vendor == 'postgresql', 'Requires real PostgreSQL row locks')
class DraftConcurrencyTests(TransactionTestCase):
    call = fixtures.ActivityTests.call
    setup_activity = fixtures.ActivityTests.setup_activity
    lot_call = fixtures.AuctionTests.lot_call

    def setUp(self):
        fixtures.AuctionTests.setUp(self)
        self.lot_call('open-bidding')

    def stored(self):
        self.activity.refresh_from_db()
        self.event.refresh_from_db()
        return deepcopy((self.activity.revision, self.activity.status,
                         self.activity.document, self.event.revision,
                         self.event.document, DraftAudit.objects.count(),
                         Audit.objects.count()))

    def race(self, actions):
        """Each request has its own DB connection and the same captured revision."""
        revision = self.activity.revision
        activity_id = self.activity.pk
        barrier = Barrier(len(actions))

        def request(item):
            action, user, body = item
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    result = mutate(activity_id, user, revision, action, body)
                    return ('ok', result.revision)
                except Invalid as exc:
                    return ('stale', str(exc))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(actions)) as executor:
            results = list(executor.map(request, actions))
        self.assertEqual([r[0] for r in results].count('ok'), 1, results)
        self.assertEqual([r[0] for r in results].count('stale'), 1, results)
        self.assertIn('活动已更新', next(r[1] for r in results if r[0] == 'stale'))
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.revision, revision + 1)
        return results

    def test_two_terminals_bid_same_revision_once(self):
        before = DraftAudit.objects.count()
        body = dict(lotId=self.lot_id, price=4)
        self.race([('bid', self.users[0], body)] * 2)
        self.assertEqual(self.activity.document['lot']['leader'], 't0')
        self.assertEqual(DraftAudit.objects.count(), before + 1)
        self.assertEqual(self.activity.document['teams'][0]['balance'], 27)

    def test_two_terminals_pass_same_revision_once(self):
        before = DraftAudit.objects.count()
        body = dict(lotId=self.lot_id)
        self.race([('pass', self.users[0], body)] * 2)
        self.assertEqual(self.activity.document['lot']['passed'], ['t0'])
        self.assertEqual(DraftAudit.objects.count(), before + 1)

    def test_bid_and_pass_race_accepts_exactly_one(self):
        self.race([('bid', self.users[0], dict(lotId=self.lot_id, price=4)),
                   ('pass', self.users[0], dict(lotId=self.lot_id))])
        lot = self.activity.document['lot']
        self.assertNotEqual(lot.get('leader') == 't0', 't0' in lot['passed'])

    def awaiting_confirmation(self):
        self.lot_call('bid', self.users[0], price=4)
        self.lot_call('pass', self.users[1])

    def test_two_admin_confirmations_deduct_and_allocate_once(self):
        self.awaiting_confirmation()
        before_draft = DraftAudit.objects.count()
        before_event = Audit.objects.count()
        self.event.refresh_from_db()
        event_revision = self.event.revision
        body = dict(lotId=self.lot_id)
        self.race([('confirm-lot', self.admin, body)] * 2)
        self.event.refresh_from_db()
        self.assertEqual(self.activity.document['teams'][0]['balance'], 23)
        self.assertEqual(sum(a['playerId'] == 'p2' for a in self.activity.document['allocations']), 1)
        self.assertEqual(next(p for p in self.event.document['players'] if p['id'] == 'p2')['teamId'], 't0')
        self.assertEqual(self.event.revision, event_revision + 1)
        self.assertEqual(DraftAudit.objects.count(), before_draft + 1)
        self.assertEqual(Audit.objects.count(), before_event + 1)

    def test_event_audit_failure_rolls_back_event_and_draft(self):
        self.awaiting_confirmation()
        before = self.stored()
        with patch('team_draft.services.Audit.objects.create', side_effect=RuntimeError('injected event audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected event audit'):
                self.lot_call('confirm-lot')
        self.assertEqual(self.stored(), before)

    def test_final_draft_audit_failure_rolls_back_all_prior_writes(self):
        self.awaiting_confirmation()
        before = self.stored()
        with patch('team_draft.services.DraftAudit.objects.create', side_effect=RuntimeError('injected draft audit failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected draft audit'):
                self.lot_call('confirm-lot')
        self.assertEqual(self.stored(), before)

    def test_cross_role_actions_leave_all_records_unchanged(self):
        before = self.stored()
        for user in (self.admin, self.outside, self.users[1]):
            with self.assertRaises(Invalid):
                self.lot_call('bid', user, price=4)
            self.assertEqual(self.stored(), before)
        self.awaiting_confirmation()
        before = self.stored()
        for user in (self.outside, *self.users):
            with self.assertRaises(PermissionDenied):
                self.lot_call('confirm-lot', user)
            self.assertEqual(self.stored(), before)

    def test_external_roster_conflict_preserves_budget_and_audits(self):
        self.awaiting_confirmation()
        self.event.refresh_from_db()
        next(p for p in self.event.document['players'] if p['id'] == 'p2')['teamId'] = 't1'
        self.event.revision += 1
        self.event.save(update_fields=['document', 'revision'])
        before = self.stored()
        with self.assertRaises(Invalid):
            self.lot_call('confirm-lot')
        self.assertEqual(self.stored(), before)


@skipUnless(connection.vendor == 'postgresql', 'Requires real PostgreSQL row locks')
class StagedImportConcurrencyTests(TransactionTestCase):
    call=fixtures.ActivityTests.call
    race=DraftConcurrencyTests.race
    def setUp(self):
        fixtures.ActivityTests.setUp(self)
        self.original=deepcopy(self.event.document)
        self.call('link',eventId=str(self.event.pk));self.call('configure',**self.payload);self.call('start')
        for i,u in enumerate(self.users):self.call('nominate',u,playerId='p'+str(i))
        self.call('reveal');self.call('continue');self.call('draw')
        lot=self.activity.document['lot']['id']
        self.call('assign-second',lotId=lot,teamId='t0',price=3);self.call('next-lot',lotId=lot)
    def test_duplicate_import_and_rollback_only_write_once(self):
        from .lifecycle import preview
        for action in ['finish','rollback-import']:
            self.activity.refresh_from_db();self.event.refresh_from_db();revision=self.event.revision
            token=preview(self.activity.pk,self.admin,self.activity.revision,action)['token']
            results=self.race([(action,self.admin,{'previewToken':token})]*2)
            self.assertEqual(sorted(r[0] for r in results),['ok','stale'])
            self.event.refresh_from_db();self.assertEqual(self.event.revision,revision+1)
        self.assertEqual(self.event.document,self.original)
