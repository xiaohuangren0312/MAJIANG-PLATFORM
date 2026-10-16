from django.test import TestCase
from django.contrib.auth import get_user_model
from league.models import Event,Audit
from league.domain import initial

class WorkspaceImprovementsTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('review-admin',password='test-pass')
        self.viewer=get_user_model().objects.create_user('review-viewer')
        self.event=Event.objects.create(name='review',kind='team',document=initial(),revision=2)
        Audit.objects.create(event=self.event,actor=self.admin,revision=2,action='match-resources',before={'document':{'matches':[]}},after={'document':{'matches':[{'id':'one'}]}})
    def test_conflict_preserves_data_and_returns_metadata(self):
        self.client.force_login(self.admin)
        response=self.client.post('/api/events/'+str(self.event.pk)+'/',{'action':'visibility','revision':1,'public':True},content_type='application/json')
        self.assertEqual(response.status_code,409)
        data=response.json()['conflict'];self.assertEqual(data['actor'],'review-admin');self.assertTrue(data['at']);self.assertIn('对局 / 名单 / 比分 / 解说资料',data['fields'])
        self.event.refresh_from_db();self.assertEqual(self.event.revision,2);self.assertFalse(self.event.public)
    def test_other_user_cannot_read_conflict_actor(self):
        self.client.force_login(self.viewer)
        response=self.client.post('/api/events/'+str(self.event.pk)+'/',{'action':'visibility','revision':1,'public':True},content_type='application/json')
        self.assertEqual(response.status_code,404)
    def test_operations_is_root_only_and_read_only(self):
        self.client.force_login(self.viewer);self.assertEqual(self.client.get('/api/operations/status/').status_code,403)
        self.client.force_login(self.admin);r=self.client.get('/api/operations/status/');self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['roles']),5)
        self.assertEqual(self.client.post('/api/operations/status/').status_code,403)
