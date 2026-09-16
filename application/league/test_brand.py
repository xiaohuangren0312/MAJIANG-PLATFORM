import tempfile,io
from pathlib import Path
from PIL import Image
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
class BrandTests(TestCase):
 def test_placeholder_permissions_and_upload(self):
  with tempfile.TemporaryDirectory(dir='/data/majiang/dev/tmp') as tmp,override_settings(ENV_ROOT=Path(tmp)):
   self.assertEqual(self.client.get('/brand/logo')['Content-Type'],'image/svg+xml')
   u=get_user_model().objects.create_user('brand-user');self.client.force_login(u)
   self.assertEqual(self.client.post('/api/brand/logo/').status_code,403)
   u.is_superuser=True;u.save();buf=io.BytesIO();Image.new('RGB',(10,10)).save(buf,format='PNG')
   r=self.client.post('/api/brand/logo/',{'image':SimpleUploadedFile('a.png',buf.getvalue(),'image/png')});self.assertEqual(r.status_code,200,r.content)
   self.assertEqual(self.client.get('/brand/logo')['Content-Type'],'image/png')
   self.assertTrue((Path(tmp)/'uploads/brand/logo.png').exists())
