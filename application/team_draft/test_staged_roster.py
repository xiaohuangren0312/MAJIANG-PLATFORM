import copy
from django.test import TestCase
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from league.domain import Invalid
from . import tests as fixtures
from .services import projection
from .lifecycle import preview

class StagedRosterTests(TestCase):
    call=fixtures.ActivityTests.call
    def setUp(self):
        fixtures.ActivityTests.setUp(self)
        self.original=copy.deepcopy(self.event.document)
        self.original_revision=self.event.revision
        self.call('link',eventId=str(self.event.pk))
        self.call('configure',**self.payload)
        self.call('start')
        for i,u in enumerate(self.users):self.call('nominate',u,playerId='p'+str(i))
        self.call('reveal');self.call('continue');self.call('draw')
    def control(self,action):
        result=preview(self.activity.pk,self.admin,self.activity.revision,action)
        self.call(action,previewToken=result['token'])
    def assign(self):
        self.call('assign-second',lotId=self.activity.document['lot']['id'],teamId='t0',price=7)
    def finish(self):
        self.assign();self.call('next-lot',lotId=self.activity.document['lot']['id']);self.control('finish')
    def test_roster_private_until_finish_import_and_full_rollback(self):
        self.event.refresh_from_db()
        self.assertEqual(self.event.document,self.original)
        self.assertEqual(self.event.revision,self.original_revision)
        self.assertEqual(projection(self.activity,self.admin)['players'][2]['teamId'],'t0')
        self.finish();self.event.refresh_from_db()
        self.assertEqual(self.event.document['players'][4]['teamId'],'t0')
        self.assertEqual(self.event.revision,self.original_revision+1)
        with self.assertRaises(Invalid):self.control('finish')
        allocations=copy.deepcopy(self.activity.document['allocations'])
        self.control('rollback-import');self.event.refresh_from_db()
        self.assertEqual(self.event.document,self.original)
        self.assertEqual(self.activity.document['allocations'],allocations)
        self.assertEqual(self.activity.document['phase'],'review-ready')
        with self.assertRaises(Invalid):self.control('rollback-import')
        self.control('finish');self.event.refresh_from_db()
        self.assertEqual(self.event.document['players'][4]['teamId'],'t0')
    def test_undo_and_stage_rollback_do_not_write_original_event(self):
        self.assign();self.control('undo')
        self.assertIsNone(projection(self.activity,self.admin)['players'][4]['teamId'])
        self.control('rollback')
        self.assertEqual(self.activity.document['phase'],'revealed')
        self.event.refresh_from_db();self.assertEqual(self.event.document,self.original)
        self.assertEqual(self.event.revision,self.original_revision)
    def test_import_blocks_external_event_changes(self):
        self.assign();self.call('next-lot',lotId=self.activity.document['lot']['id'])
        self.event.refresh_from_db();self.event.document['players'][0]['name']='外部改名';self.event.revision+=1;self.event.save()
        with self.assertRaises(Invalid):self.control('finish')
    def test_rollback_blocks_external_changes_permissions_and_stale_token(self):
        self.finish()
        with self.assertRaises(PermissionDenied):preview(self.activity.pk,self.users[0],self.activity.revision,'rollback-import')
        token=preview(self.activity.pk,self.admin,self.activity.revision,'rollback-import')['token']
        self.call('publish',public=True)
        with self.assertRaises(Invalid):self.call('rollback-import',previewToken=token)
        self.event.refresh_from_db();self.event.document['players'][0]['name']='外部改名';self.event.revision+=1;self.event.save()
        with self.assertRaises(Invalid):self.control('rollback-import')
    def test_private_snapshots_not_exposed(self):
        self.call('publish',public=True)
        for user in [self.admin,self.users[0],AnonymousUser()]:
            d=projection(self.activity,user)['draft']
            for key in ['_roster','_baseline','_import']:self.assertNotIn(key,d)
    def test_completed_import_can_edit_descriptions_without_event_write(self):
        self.finish();self.event.refresh_from_db();revision=self.event.revision
        self.call('edit-candidates',candidates=[dict(playerId='p2',startPrice=9,description='更新介绍')])
        self.event.refresh_from_db();self.assertEqual(self.event.revision,revision)
        self.assertEqual(self.activity.status,'complete')
        self.control('rollback-import')


class LegacyConversionTests(TestCase):
    setUp=fixtures.ActivityTests.setUp
    call=fixtures.ActivityTests.call
    assign=StagedRosterTests.assign
    control=StagedRosterTests.control
    def test_migrate_legacy_keeps_choices_and_restores_original_then_imports(self):
        from django.db import transaction
        from .roster import enable_staging
        # Set up a separate legacy activity through the explicit legacy fixture.
        original=copy.deepcopy(self.event.document)
        fixtures.ActivityTests.setup_activity(self)
        self.call('start')
        for i,u in enumerate(self.users):self.call('nominate',u,playerId='p'+str(i))
        self.call('reveal');self.call('continue');self.call('draw');self.assign()
        projected=projection(self.activity,self.admin)['players']
        with transaction.atomic():enable_staging(self.activity,self.admin)
        self.event.refresh_from_db();self.assertEqual(self.event.document,original)
        self.assertEqual(projection(self.activity,self.admin)['players'],projected)
        self.call('next-lot',lotId=self.activity.document['lot']['id']);self.control('finish')
        self.event.refresh_from_db();self.assertEqual(self.event.document['players'][4]['teamId'],'t0')
        self.control('rollback-import');self.event.refresh_from_db();self.assertEqual(self.event.document,original)


class StagedHttpWorkflowTests(TestCase):
    setUp=fixtures.ActivityTests.setUp
    def request(self,action,user=None,**data):
        self.activity.refresh_from_db();self.client.force_login(user or self.admin)
        response=self.client.post(f'/api/draft/{self.activity.pk}/',data={'action':action,'revision':self.activity.revision,**data},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.activity.refresh_from_db()
        return response.json()
    def test_all_stages_import_rollback_and_reimport_via_http(self):
        original=copy.deepcopy(self.event.document)
        self.request('link',eventId=str(self.event.pk));self.request('configure',**self.payload)
        self.request('start')
        for i,u in enumerate(self.users):self.request('nominate',u,playerId='p'+str(i))
        self.request('reveal');self.request('continue');self.request('draw')
        lot=self.activity.document['lot']['id']
        self.request('mark-unsold',lotId=lot);self.request('next-lot',lotId=lot)
        self.assertEqual(self.activity.document['phase'],'third-ready')
        self.request('draw-third');lot=self.activity.document['lot']['id']
        self.request('edit-candidates',candidates=[dict(playerId='p2',startPrice=2,description='测试介绍')])
        self.request('open-bidding',lotId=lot)
        tid=self.activity.document['lot']['turn']
        self.request('bid',self.users[int(tid[1:])],lotId=lot,price=2)
        self.request('admin-third',lotId=lot,teamId='t1',price=1)
        self.request('next-lot',lotId=lot)
        self.event.refresh_from_db();self.assertEqual(self.event.document,original)
        for action in ['finish','rollback-import','finish']:
            preview_result=self.request('preview',operation=action)['preview']
            self.request(action,previewToken=preview_result['token'])
            self.event.refresh_from_db()
            if action=='rollback-import':self.assertEqual(self.event.document,original)
            else:self.assertEqual(self.event.document['players'][4]['teamId'],'t1')
        self.assertEqual(self.activity.document['teams'][1]['balance'],26)
