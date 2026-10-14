import tempfile
from pathlib import Path
from django.test import TestCase,Client,override_settings
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from league.models import Event
from league.domain import initial
from league.permissions import actions_for
from league.roles import VENUE_ADMIN,PLATFORM_SHADOW
from hql.tenancy import _current

@override_settings(DRAFT_ENABLED=False)
class AdminRoleTests(TestCase):
    databases={'default','ylg'}
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=str(settings.ENV_ROOT/'tmp'));self.addCleanup(self.tmp.cleanup)
        self.registry={k:dict(key=k,database=db,name=k,english=k,root=str(Path(self.tmp.name)/k),hosts=[host]) for k,db,host in [('hql','default','testserver'),('ylg','ylg','ylg.test')]}
        override=override_settings(VENUES=self.registry,ALLOWED_HOSTS=['testserver','ylg.test']);override.enable();self.addCleanup(override.disable)
        self.password='Testing-Role123!'
        User=get_user_model()
        self.root=User.objects.create_superuser('platform',password=self.password)
        self.admin=User.objects.create_user('venue',password=self.password)
        self.admin.groups.add(Group.objects.create(name=VENUE_ADMIN))
        self.editor=User.objects.create_user('editor',password=self.password)
        self.coach=User.objects.create_user('coach',password=self.password)
        self.viewer=User.objects.create_user('viewer',password=self.password)
        doc=initial();doc['coachAccounts']={str(self.coach.pk):{'username':'coach','active':True,'teamId':'own'}}
        self.event=Event.objects.create(name='own',kind='team',document=doc);self.event.editors.add(self.editor)
        token=_current.set(self.registry['ylg'])
        try:
            self.other=User.objects.create_user('other-venue',password=self.password)
            self.other.groups.add(Group.objects.create(name=VENUE_ADMIN))
            self.other_event=Event.objects.create(name='other',kind='team',document=initial())
        finally:_current.reset(token)
    def login(self,name,host='testserver',password=None):
        c=Client();r=c.post('/login/?next=/wrong/',{'username':name,'password':password or self.password},HTTP_HOST=host)
        return c,r
    def test_role_landing_pages(self):
        for name,url in [('platform','/manage/'),('venue','/manage/'),('editor','/manage/'),('coach','/coach/lineups/'),('viewer','/')]:
            c,r=self.login(name);self.assertEqual(r.status_code,302);self.assertEqual(r.url,url)
        self.event.editors.add(self.coach)
        self.assertEqual(self.login('coach')[1].url,'/manage/')
    def test_venue_admin_capabilities_and_no_backfill(self):
        c,_=self.login('venue')
        data=c.get('/api/events/').json();self.assertTrue(data['canCreateEvent']);self.assertEqual(data['events'][0]['role'],'venueadmin')
        self.assertEqual(c.get('/api/brand/settings/').status_code,200)
        html=c.get('/manage/').content.decode();self.assertIn('venue-settings-form',html);self.assertNotIn('href="/manage/history-backfill/"',html);self.assertIn('场馆管理员',html)
        self.assertEqual(c.get('/api/history-backfill/events/').status_code,403)
        self.assertEqual(c.post('/api/events/',{'name':'new','kind':'team'},content_type='application/json').status_code,201)
        self.assertIn('grant',actions_for(self.event,self.admin))
        self.event.document['archive']={ 'done':True }
        self.assertIn('archive-reopen',actions_for(self.event,self.admin));self.assertEqual(actions_for(self.event,self.editor),[])
    def test_event_editor_cannot_escalate(self):
        c,_=self.login('editor')
        self.assertEqual(c.get('/api/brand/settings/').status_code,403)
        self.assertEqual(c.post('/api/events/',{'name':'no','kind':'team'},content_type='application/json').status_code,403)
        self.assertEqual(c.post('/api/accounts/',{'username':'bad','role':'admin','eventId':str(self.event.pk),'revision':self.event.revision},content_type='application/json').status_code,403)
        self.assertNotIn('grant',actions_for(self.event,self.editor))
    def test_platform_shared_credentials_and_tenant_isolation(self):
        c,r=self.login('platform','ylg.test');self.assertEqual(r.url,'/manage/')
        self.assertEqual(c.get('/api/events/',HTTP_HOST='ylg.test').json()['events'][0]['id'],str(self.other_event.pk))
        self.assertEqual(c.get('/api/events/'+str(self.event.pk)+'/',HTTP_HOST='ylg.test').status_code,404)
        self.assertEqual(c.get('/api/events/',HTTP_HOST='testserver').status_code,401)
        _,r=self.login('venue','ylg.test');self.assertEqual(r.status_code,200)
        _,r=self.login('other-venue');self.assertEqual(r.status_code,200)
    def test_platform_password_change_invalidates_other_venue_session(self):
        c,_=self.login('platform','ylg.test')
        self.root.set_password('Changed-Password123!');self.root.save(using='default')
        self.assertEqual(c.get('/api/events/',HTTP_HOST='ylg.test').status_code,401)
        self.assertEqual(self.login('platform','ylg.test')[1].status_code,200)
        self.assertEqual(self.login('platform','ylg.test','Changed-Password123!')[1].status_code,302)
    def test_platform_revocation_invalidates_shadow(self):
        c,_=self.login('platform','ylg.test')
        self.root.is_superuser=False;self.root.save(using='default')
        self.assertEqual(c.get('/api/events/',HTTP_HOST='ylg.test').status_code,401)
        self.assertEqual(self.login('platform','ylg.test')[1].status_code,200)
    def test_platform_password_change_from_secondary_venue(self):
        c,_=self.login('platform','ylg.test')
        r=c.post('/account/',{'old_password':self.password,'new_password1':'Updated-Password123!','new_password2':'Updated-Password123!'},HTTP_HOST='ylg.test')
        self.assertEqual(r.status_code,302)
        self.root.refresh_from_db(using='default');self.assertTrue(self.root.check_password('Updated-Password123!'))
        self.assertEqual(c.get('/api/events/',HTTP_HOST='ylg.test').status_code,200)
        self.assertEqual(self.login('platform',password='Updated-Password123!')[1].status_code,302)
    def test_platform_name_collision_does_not_promote_existing_user(self):
        get_user_model().objects.db_manager('ylg').create_user('platform',password=self.password)
        self.assertEqual(self.login('platform','ylg.test')[1].status_code,200)
        self.assertFalse(get_user_model().objects.using('ylg').get(username='platform').is_superuser)
