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

 def test_team_crop_original_reuse_validation_and_privacy(self):
  import json
  user=get_user_model().objects.create_user('crop-admin',is_superuser=True)
  outsider=get_user_model().objects.create_user('crop-viewer')
  d=apply(initial(),'team','team',{'name':'裁剪队伍'})
  e=Event.objects.create(name='裁剪测试',kind='team',document=d,public=True)
  tid=d['teams'][0]['id'];buf=io.BytesIO()
  im=Image.new('RGBA',(120,80),(255,0,0,255));im.putpixel((60,40),(0,0,0,0));im.save(buf,format='PNG')
  with tempfile.TemporaryDirectory(dir='/data/majiang/dev/tmp') as tmp,override_settings(ENV_ROOT=Path(tmp)):
   self.client.force_login(user)
   def post(crop,**extra):
    e.refresh_from_db()
    return self.client.post(f'/api/events/{e.id}/image/',{'kind':'team','entityId':tid,'revision':e.revision,'crop':json.dumps(crop),**extra})
   crop={'x':20,'y':0,'size':80,'shape':'circle'}
   r=post(crop,image=SimpleUploadedFile('a.png',buf.getvalue(),'image/png'));self.assertEqual(r.status_code,200,r.content)
   e.refresh_from_db();row=e.document['teams'][0];original=row['imageSourceUrl'];first=row['imageUrl']
   folder=Path(tmp)/'uploads'/'roster'/str(e.id)
   with Image.open(folder/first.rsplit('/',1)[-1]) as out:
    self.assertEqual(out.size,(512,512));self.assertEqual(out.getpixel((0,0))[3],0)
   with Image.open(folder/original.rsplit('/',1)[-1]) as source:self.assertEqual(source.size,(120,80))
   self.assertEqual(self.client.get(original).status_code,200)
   self.client.logout();self.assertEqual(self.client.get(first).status_code,200);self.assertEqual(self.client.get(original).status_code,404)
   self.client.force_login(outsider);self.assertEqual(self.client.get(original).status_code,403)
   self.assertEqual(post(crop,reuseSource='1').status_code,403)
   self.client.force_login(user)
   r=post({**crop,'shape':'square'},reuseSource='1');self.assertEqual(r.status_code,200,r.content)
   e.refresh_from_db();self.assertEqual(e.document['teams'][0]['imageSourceUrl'],original)
   with Image.open(folder/r.json()['imageUrl'].rsplit('/',1)[-1]) as out:self.assertEqual(out.getpixel((0,0))[3],255)
   r=post({'x':-20,'y':-40,'size':160,'shape':'square'},reuseSource='1');self.assertEqual(r.status_code,200,r.content)
   with Image.open(folder/r.json()['imageUrl'].rsplit('/',1)[-1]) as out:
    self.assertEqual(out.getpixel((0,0))[3],0);self.assertGreater(out.getpixel((200,200))[3],0)
   e.refresh_from_db()
   before=e.document.copy();count=len(list(folder.iterdir()))
   for bad in [{**crop,'size':321},{**crop,'x':-81},{**crop,'size':float('nan')},{**crop,'shape':'bad'}]:
    self.assertEqual(post(bad,reuseSource='1').status_code,400)
   self.assertEqual(len(list(folder.iterdir())),count)
   e.refresh_from_db();self.assertEqual(e.document,before)
   r=self.client.post(f'/api/events/{e.id}/image/',{'kind':'team','entityId':tid,'revision':0,'reuseSource':'1','crop':json.dumps(crop)})
   self.assertEqual(r.status_code,400)
