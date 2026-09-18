import io,tempfile,copy
from pathlib import Path
from PIL import Image
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Event,Audit
from .domain import initial
from .projection import public_event

class EventBrandTests(TestCase):
 def setUp(self):
  tmp=self.enterContext(tempfile.TemporaryDirectory(dir='/data/majiang/dev/tmp'))
  self.enterContext(override_settings(ENV_ROOT=Path(tmp)))
  User=get_user_model();self.root=User.objects.create_user('logo-root',is_superuser=True);self.editor=User.objects.create_user('logo-editor');self.viewer=User.objects.create_user('logo-viewer')
  self.e=Event.objects.create(name='赛事甲',kind='team',document=initial(),public=True);self.e.editors.add(self.editor)
  self.other=Event.objects.create(name='赛事乙',kind='team',document=initial())
  self.url=f'/api/events/{self.e.pk}/logo/';self.image=f'/brand/events/{self.e.pk}/logo'
 def file(self):
  buf=io.BytesIO();Image.new('RGB',(900,450),'red').save(buf,format='PNG');return SimpleUploadedFile('logo.png',buf.getvalue(),'image/png')
 def test_permissions_isolation_and_private_read(self):
  self.client.force_login(self.editor)
  self.assertEqual(self.client.post('/api/brand/logo/',{'image':self.file()}).status_code,403)
  self.assertEqual(self.client.post(f'/api/events/{self.other.pk}/logo/',{'revision':1,'image':self.file()}).status_code,404)
  self.assertEqual(self.client.get(f'/brand/events/{self.other.pk}/logo').status_code,404)
  self.client.force_login(self.viewer);self.assertEqual(self.client.post(self.url,{'revision':1,'image':self.file()}).status_code,404)
  self.client.logout();self.assertEqual(self.client.post(self.url,{'revision':1,'image':self.file()}).status_code,401)
 def test_upload_reset_fallback_audit_and_projection(self):
  self.assertEqual(self.client.get(self.image)['Content-Type'],'image/svg+xml')
  before=copy.deepcopy(self.e.document);self.client.force_login(self.editor)
  response=self.client.post(self.url,{'revision':1,'image':self.file()});self.assertEqual(response.status_code,200,response.content)
  self.e.refresh_from_db();name=self.e.document['eventLogo'];self.assertEqual(self.e.revision,2)
  from django.conf import settings
  with Image.open(settings.ENV_ROOT/'uploads/events'/str(self.e.pk)/name) as im:self.assertEqual(im.size,(512,256))
  self.assertEqual({k:v for k,v in self.e.document.items() if k!='eventLogo'},before)
  self.assertEqual(public_event(self.e)['logoUrl'],self.image)
  self.assertEqual(self.client.get(self.image)['Content-Type'],'image/png')
  self.assertEqual(self.client.post(self.url,{'revision':1,'remove':'1'}).status_code,409)
  self.assertEqual(self.client.post(self.url,{'revision':2,'remove':'1'}).status_code,200)
  self.assertEqual(self.client.get(self.image)['Content-Type'],'image/svg+xml')
  self.assertEqual(Audit.objects.filter(event=self.e,action='event-logo').count(),2)
  self.client.force_login(self.root);self.client.post('/api/brand/logo/',{'image':self.file()})
  self.assertEqual(self.client.get(self.image)['Content-Type'],'image/png')
  self.other.refresh_from_db();self.assertNotIn('eventLogo',self.other.document)
 def test_invalid_image_and_archive_access(self):
  self.client.force_login(self.editor)
  self.assertEqual(self.client.post(self.url,{'revision':1,'image':SimpleUploadedFile('bad.png',b'bad')}).status_code,400)
  self.e.document['archive']={'locked':True};self.e.save()
  self.assertEqual(self.client.post(self.url,{'revision':1,'image':self.file()}).status_code,403)
  self.client.force_login(self.root)
  self.assertEqual(self.client.post(self.url,{'revision':1,'image':self.file()}).status_code,200)
