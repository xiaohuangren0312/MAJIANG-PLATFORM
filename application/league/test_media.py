import io,tempfile
from pathlib import Path
from PIL import Image
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from .domain import initial,apply
from .models import Event
class MediaTests(TestCase):
 def test_upload_permissions_and_projection(self):
  from .projection import public_event
  user=get_user_model().objects.create_user('media-admin',is_superuser=True)
  d=apply(initial(),'team','team',{'name':'测试队'})
  e=Event.objects.create(name='图片测试',kind='team',document=d)
  image=io.BytesIO();Image.new('RGB',(32,32),'red').save(image,format='PNG')
  with tempfile.TemporaryDirectory(dir='/data/majiang/dev/tmp') as tmp,override_settings(ENV_ROOT=Path(tmp)):
   self.client.force_login(user)
   r=self.client.post(f'/api/events/{e.id}/image/',{'kind':'team','entityId':d['teams'][0]['id'],'revision':1,'image':SimpleUploadedFile('test.png',image.getvalue(),'image/png')})
   self.assertEqual(r.status_code,200,r.content)
   e.refresh_from_db();url=r.json()['imageUrl'];self.assertEqual(public_event(e)['teams'][0]['imageUrl'],url)
   self.assertEqual(self.client.get(url).status_code,200)
   self.client.logout();self.assertEqual(self.client.get(url).status_code,404)
   e.public=True;e.save();self.assertEqual(self.client.get(url).status_code,200)

 def test_resources_preserve_archived_scores_and_validate_urls(self):
  from .match_resources import update,project
  from .domain import Invalid
  d={'matches':[{'id':'m','state':'published','seats':[{'points':500}]}],'archive':{'standings':{'total':500}}}
  new=update(d,{'id':'m','commentators':['解说甲'],'videos':[{'url':'https://example.com/watch'}]})
  self.assertEqual(new['matches'],d['matches']);self.assertEqual(new['archive'],d['archive'])
  with self.assertRaises(Invalid):update(d,{'id':'m','videos':[{'url':'javascript:alert(1)'}]})
  with self.assertRaises(Invalid):update(d,{'id':'other'})
  self.assertEqual(project({'results':[{'id':'m'}]},new)['results'][0]['resources']['commentators'],['解说甲'])
