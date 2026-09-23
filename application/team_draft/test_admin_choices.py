from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from . import tests as fixtures
from .services import projection

class AdminChoicesTests(TestCase):
    setUp=fixtures.ActivityTests.setUp
    call=fixtures.ActivityTests.call
    setup_activity=fixtures.ActivityTests.setup_activity
    def test_unpublished_choices_are_only_returned_to_manager(self):
        self.setup_activity();self.call('publish',public=True);self.call('start')
        self.call('nominate',self.users[0],playerId='p0')
        self.assertEqual(projection(self.activity,self.admin)['draft']['adminChoices'],{'t0':'p0'})
        for user in [self.users[0],self.users[1],self.outside,AnonymousUser()]:
            d=projection(self.activity,user)['draft']
            self.assertNotIn('adminChoices',d);self.assertNotIn('nominations',d)
        self.assertEqual(projection(self.activity,self.users[0])['draft']['myPick'],'p0')
        self.assertIsNone(projection(self.activity,self.users[1])['draft']['myPick'])
        self.client.force_login(self.users[1])
        d=self.client.get(f'/api/draft/{self.activity.pk}/?admin=true').json()['draft']
        self.assertNotIn('adminChoices',d)
        self.event.editors.add(self.outside)
        self.assertEqual(projection(self.activity,self.outside)['draft']['adminChoices'],{'t0':'p0'})
        self.event.editors.remove(self.outside)
        self.assertNotIn('adminChoices',projection(self.activity,self.outside)['draft'])
    def test_reveal_does_not_keep_private_field(self):
        self.setup_activity();self.call('start')
        self.call('nominate',self.users[0],playerId='p0');self.call('nominate',self.users[1],playerId='p1');self.call('reveal')
        self.assertNotIn('adminChoices',projection(self.activity,self.admin)['draft'])

    def test_admin_can_fill_and_correct_only_before_reveal(self):
        from league.domain import Invalid
        from django.core.exceptions import PermissionDenied
        from .lifecycle import preview
        self.setup_activity();self.call('start')
        self.call('admin-nominate',teamId='t0',playerId='p0')
        self.call('admin-nominate',teamId='t0',playerId='p1')
        self.assertEqual(projection(self.activity,self.users[0])['draft']['myPick'],'p1')
        with self.assertRaises(PermissionDenied):self.call('admin-nominate',self.users[1],teamId='t0',playerId='p0')
        with self.assertRaises(Invalid):self.call('admin-nominate',teamId='foreign',playerId='p0')
        with self.assertRaises(Invalid):self.call('admin-nominate',teamId='t0',playerId='c0')
        token=preview(self.activity.pk,self.admin,self.activity.revision,'undo')['token']
        self.call('undo',previewToken=token)
        self.assertEqual(self.activity.document['nominations']['t0'],'p0')
        self.call('admin-nominate',teamId='t1',playerId='p0')
        self.call('reveal')
        self.assertEqual(len(self.activity.document['conflicts']),1)
        with self.assertRaises(Invalid):self.call('admin-nominate',teamId='t0',playerId='p1')
