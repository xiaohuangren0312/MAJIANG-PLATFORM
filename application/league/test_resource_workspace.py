import copy
from django.test import TestCase
from .test_coach_lineups import CoachLineupTests
from .models import Audit

class ResourceWorkspaceTests(TestCase):
    setUp=CoachLineupTests.setUp
    def save(self, **values):
        return self.client.post(f'/api/events/{self.e.pk}/', {'action':'match-resources','revision':self.e.revision,**values}, content_type='application/json')
    def test_per_game_resources_survive_commentator_edit_and_project_to_poster(self):
        self.client.force_login(self.admin)
        first,second=self.e.document['matches'][:2]
        links={'videos':[{'title':'录像','url':'https://example.com/video'}],'records':[{'title':'牌谱','url':'https://example.com/record'}]}
        response=self.save(id=first['id'],commentators=['甲','乙'],**links)
        self.assertEqual(response.status_code,200,response.content)
        self.e.refresh_from_db()
        before=copy.deepcopy(self.e.document)
        response=self.save(id=first['id'],commentators=['丙'],**links)
        self.assertEqual(response.status_code,200,response.content)
        self.e.refresh_from_db()
        self.assertEqual(self.e.document['matches'],before['matches'])
        self.assertNotIn(second['id'],self.e.document['matchResources'])
        for key,value in links.items():self.assertEqual(self.e.document['matchResources'][first['id']][key],value)
        rows=self.client.get(f'/api/posters/{self.e.pk}/').json()['matches']
        self.assertEqual(next(x for x in rows if x['id']==first['id'])['commentators'],['丙'])
        self.assertEqual(Audit.objects.filter(event=self.e,action='match-resources').count(),2)
    def test_stale_revision_foreign_match_invalid_link_do_not_write(self):
        self.client.force_login(self.admin)
        first=self.e.document['matches'][0]
        before=copy.deepcopy(self.e.document)
        for values,code in [({'id':first['id'],'revision':0},409),({'id':'not-in-event'},400),({'id':first['id'],'videos':[{'url':'javascript:alert(1)'}]},400)]:
            response=self.save(**values);self.assertEqual(response.status_code,code,response.content)
        self.e.refresh_from_db();self.assertEqual(self.e.document,before)
        self.assertFalse(Audit.objects.filter(event=self.e,action='match-resources').exists())
    def test_coach_and_viewer_cannot_save_resources(self):
        first=self.e.document['matches'][0]
        for user in (self.coach,self.viewer):
            self.client.force_login(user)
            self.assertIn(self.save(id=first['id'],commentators=['甲']).status_code,(403,404))
    def test_workspace_assets_and_template_are_served(self):
        self.client.force_login(self.admin)
        response=self.client.get('/manage/')
        self.assertContains(response,'/assets/manager-resources.js')
        self.assertContains(response,'/assets/manager-resources.css')
        for name in ['manager-resources.js','manager-resources.css']:
            response=self.client.get('/assets/'+name)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response['Cache-Control'],'no-cache')
