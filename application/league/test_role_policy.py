import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from .domain import initial,apply
from .models import Event,Audit
from .lifecycle import archive_event
from .projection import public_event
from team_draft.models import DraftActivity
from team_draft.services import own_team

class RolePolicyTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.root=User.objects.create_user('policy-root',is_superuser=True)
        self.manager=User.objects.create_user('policy-manager')
        self.viewer=User.objects.create_user('policy-viewer')
        self.e=Event.objects.create(name='权限测试',kind='personal',document=initial())
        self.e.editors.add(self.manager)
        self.foreign=Event.objects.create(name='他人赛事',kind='team',document=initial())
    def post(self,user,action,**kw):
        self.client.force_login(user);self.e.refresh_from_db()
        return self.client.post(f'/api/events/{self.e.pk}/',dict(action=action,revision=self.e.revision,**kw),content_type='application/json')
    def create(self,user,**kw):
        self.client.force_login(user);self.e.refresh_from_db()
        return self.client.post('/api/accounts/',dict(username='coach-new',eventId=str(self.e.pk),revision=self.e.revision,role='coach',**kw),content_type='application/json')
    def test_editor_can_only_create_scoped_coach_and_viewer_has_no_write(self):
        self.assertEqual(self.create(self.manager).status_code,201)
        coach=get_user_model().objects.get(username='coach-new')
        self.assertFalse(coach.is_superuser or coach.is_staff)
        self.assertFalse(self.e.editors.filter(pk=coach.pk).exists())
        self.client.force_login(coach)
        self.assertContains(self.client.get('/account/'),'选人大会')
        self.assertRedirects(self.client.get('/manage/'),'/',fetch_redirect_response=False)
        self.assertEqual(self.post(coach,'player',name='越权').status_code,404)
        self.assertEqual(self.post(self.viewer,'player',name='越权').status_code,404)
        self.client.force_login(self.manager)
        for role in ['admin','viewer']:
            res=self.client.post('/api/accounts/',{'username':'forbidden','role':role,'eventId':str(self.e.pk),'revision':2},content_type='application/json')
            self.assertEqual(res.status_code,403)
        res=self.client.post('/api/accounts/',{'username':'foreign','role':'coach','eventId':str(self.foreign.pk),'revision':1},content_type='application/json')
        self.assertEqual(res.status_code,404)
    def test_root_creates_event_manager_and_coach_suspend_is_scoped(self):
        self.client.force_login(self.root)
        response=self.client.post('/api/accounts/',{'username':'new-manager','role':'admin','eventId':str(self.e.pk),'revision':1},content_type='application/json')
        self.assertEqual(response.status_code,201)
        self.assertTrue(self.e.editors.filter(username='new-manager').exists())
        self.assertEqual(self.create(self.manager).status_code,201)
        coach=get_user_model().objects.get(username='coach-new')
        activity=DraftActivity.objects.create(name='选人',event=self.e,creator=self.root,document={'teams':[{'teamId':'t','coachUserId':coach.pk}]})
        self.assertEqual(own_team(activity,coach),'t')
        self.assertEqual(self.post(self.manager,'coach-manage',userId=str(coach.pk),active=False).status_code,200)
        activity.refresh_from_db();self.assertIsNone(own_team(activity,coach))
        self.assertEqual(self.post(self.manager,'coach-manage',userId=str(self.viewer.pk),active=False).status_code,400)
    def test_archive_revision_is_root_only_and_refreshes_public_and_export(self):
        d=apply(initial(),'personal','stage',{'name':'决赛'})
        for name in ['甲','乙','丙','丁']:d=apply(d,'personal','player',{'name':name})
        d=apply(d,'personal','match',dict(stageId=d['stages'][0]['id'],date='2026-01-01',number=1,seats=[{'playerId':p['id']} for p in d['players']]))
        mid=d['matches'][0]['id'];d=apply(d,'personal','save-result',dict(id=mid,scores=[40000,30000,20000,10000]))
        self.e.document=d;self.e.document=archive_event(self.e,'',self.root.username);self.e.save()
        original=copy.deepcopy(public_event(self.e))
        self.assertEqual(self.post(self.manager,'archive-reopen').status_code,403)
        self.assertEqual(self.create(self.manager).status_code,403)
        self.assertEqual(self.post(self.root,'archive-reopen').status_code,200)
        self.assertEqual(self.post(self.manager,'player',name='归档越权').status_code,403)
        self.assertEqual(self.post(self.root,'correct',id=mid,scores=[10000,20000,30000,40000]).status_code,200)
        self.e.refresh_from_db();self.assertEqual(public_event(self.e),original)
        preview=self.post(self.root,'archive-preview');self.assertEqual(preview.status_code,200)
        self.assertEqual(self.post(self.root,'archive-commit',token=preview.json()['token']).status_code,200)
        self.e.refresh_from_db();self.assertNotIn('archiveRevision',self.e.document)
        self.assertNotEqual(public_event(self.e)['results'],original['results'])
        self.assertEqual(self.e.document['archive']['standings']['rows'][0]['name'],'丁')
        self.assertIn('丁',self.e.document['archive']['csvExport'])

    def test_revoked_manager_cannot_manage_standalone_activity(self):
        from team_draft.services import manager as manages
        activity=DraftActivity.objects.create(name='未关联选人',creator=self.manager)
        self.assertTrue(manages(activity,self.manager))
        self.e.editors.remove(self.manager)
        self.assertFalse(manages(activity,self.manager))
        self.assertTrue(manages(activity,self.root))
