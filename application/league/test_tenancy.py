import copy,tempfile
from pathlib import Path
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from hql.tenancy import _current,database
from hql import tenant_transaction as transaction
from league.models import Event
from league.domain import initial
class VenueTests(TestCase):
 databases={'default','ylg'}
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=str(settings.ENV_ROOT/'tmp'));self.addCleanup(self.tmp.cleanup)
  self.registry={k:dict(key=k,database=db,name=name,english=k,root=str(Path(self.tmp.name)/k),hosts=[host]) for k,db,name,host in [('hql','default','欢雀楼','testserver'),('ylg','ylg','一乐馆','ylg.test')]}
  self.override=override_settings(VENUES=self.registry,ALLOWED_HOSTS=['testserver','ylg.test','unknown.test']);self.override.enable();self.addCleanup(self.override.disable)
  for k in self.registry:
   token=_current.set(self.registry[k])
   try:
    get_user_model().objects.create_superuser('hql-test-root' if k=='hql' else 'admin',password='Test-Only-Pass123!')
    e=Event.objects.create(name=k,kind='team',public=True,document=initial())
    setattr(self,k,e)
   finally:_current.reset(token)
 def test_feed_brand_and_default(self):
  for host,k in [('testserver','hql'),('ylg.test','ylg'),('testserver','hql')]:
   r=Client().get('/data.json',HTTP_HOST=host);self.assertEqual(r.status_code,200)
   self.assertEqual([x['id'] for x in r.json()['tournaments']],[str(getattr(self,k).pk)])
   self.assertEqual(r.json()['defaultEventId'],str(getattr(self,k).pk))
   html=Client().get('/login/',HTTP_HOST=host).content.decode();self.assertIn(self.registry[k]['name'],html)
  self.assertEqual(Client().get('/data.json',HTTP_HOST='unknown.test').status_code,400)
 def test_login_cross_venue_and_csrf(self):
  c=Client(enforce_csrf_checks=True);r=c.get('/login/',HTTP_HOST='ylg.test');cookie=settings.CSRF_COOKIE_NAME+'_ylg';self.assertIn(cookie,c.cookies)
  r=c.post('/login/',{'username':'admin','password':'Test-Only-Pass123!','csrfmiddlewaretoken':c.cookies[cookie].value},HTTP_HOST='ylg.test');self.assertEqual(r.status_code,302)
  self.assertIn(settings.SESSION_COOKIE_NAME+'_ylg',c.cookies)
  self.assertEqual(c.get('/api/events/',HTTP_HOST='ylg.test').status_code,200)
  self.assertEqual(c.get('/api/events/'+str(self.hql.pk)+'/',HTTP_HOST='ylg.test').status_code,404)
  self.assertNotEqual(c.get('/api/events/',HTTP_HOST='testserver').status_code,200)
  self.assertEqual(database(),'default')
  response=c.post('/api/events/',{'name':'isolated-create','kind':'team'},content_type='application/json',HTTP_HOST='ylg.test',HTTP_X_CSRFTOKEN=c.cookies[cookie].value)
  self.assertEqual(response.status_code,201)
  self.assertFalse(Event.objects.using('default').filter(name='isolated-create').exists())
  self.assertTrue(Event.objects.using('ylg').filter(name='isolated-create').exists())
 def test_atomic_rollback_on_selected_database(self):
  token=_current.set(self.registry['ylg'])
  try:
   with self.assertRaises(ValueError):
    with transaction.atomic():
     Event.objects.create(name='rollback',kind='team',document=initial());raise ValueError()
   self.assertFalse(Event.objects.filter(name='rollback').exists())
  finally:_current.reset(token)
 def test_newest_created_not_name(self):
  e=Event.objects.create(name='S1 newest',kind='team',public=True,document=initial())
  self.assertEqual(Client().get('/data.json').json()['defaultEventId'],str(e.pk))
  e.public=False;e.save()
  self.assertEqual(Client().get('/data.json').json()['defaultEventId'],str(self.hql.pk))
 def test_storage_isolation(self):
  for k in self.registry:
   folder=Path(self.registry[k]['root'])/'uploads/brand';folder.mkdir(parents=True);(folder/'logo.png').write_bytes(k.encode())
  for host,k in [('testserver','hql'),('ylg.test','ylg')]:
   response=Client().get('/brand/logo',HTTP_HOST=host)
   self.assertEqual(b''.join(response.streaming_content),k.encode())

 def test_archived_not_default(self):
  from league.projection import public_event
  snapshot=public_event(self.hql)
  self.hql.document['archive']={'publicPayload':snapshot};self.hql.save()
  self.assertIsNone(Client().get('/data.json').json()['defaultEventId'])
 def test_thread_context_isolation(self):
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier
  barrier=Barrier(2)
  def work(k):
   token=_current.set(self.registry[k])
   try:
    barrier.wait();return database()
   finally:_current.reset(token)
  with ThreadPoolExecutor(2) as pool:
   self.assertEqual(list(pool.map(work,['hql','ylg'])),['default','ylg'])
  self.assertEqual(database(),'default')

 def test_brand_settings_permissions_revision_and_isolation(self):
  c=Client();c.post('/login/',{'username':'admin','password':'Test-Only-Pass123!'},HTTP_HOST='ylg.test')
  before=c.get('/api/brand/settings/',HTTP_HOST='ylg.test').json()
  payload={'name':'二重楼','english':'','tagline':'新的宣传语','revision':before['revision']}
  r=c.post('/api/brand/settings/',payload,content_type='application/json',HTTP_HOST='ylg.test');self.assertEqual(r.status_code,200)
  html=c.get('/login/',HTTP_HOST='ylg.test').content.decode();self.assertIn('二重楼',html)
  self.assertIn('欢雀楼',c.get('/login/',HTTP_HOST='testserver').content.decode())
  self.assertNotEqual(c.post('/api/brand/settings/',payload,content_type='application/json',HTTP_HOST='ylg.test').status_code,200)
  self.assertNotEqual(Client().post('/api/brand/settings/',payload,content_type='application/json',HTTP_HOST='ylg.test').status_code,200)
  token=_current.set(self.registry['ylg'])
  try:
   editor=get_user_model().objects.create_user('editor',password='Test-Only-Pass123!');Event.objects.get(pk=self.ylg.pk).editors.add(editor)
  finally:_current.reset(token)
  ordinary=Client();ordinary.post('/login/',{'username':'editor','password':'Test-Only-Pass123!'},HTTP_HOST='ylg.test')
  self.assertEqual(ordinary.get('/api/brand/settings/',HTTP_HOST='ylg.test').status_code,403)
  import json
  audit=json.loads((Path(self.registry['ylg']['root'])/'uploads/brand/settings.json').read_text())
  self.assertEqual(audit['history'][0]['actor'],'admin')
  self.assertEqual(Event.objects.using('ylg').get(pk=self.ylg.pk).name,'ylg')
