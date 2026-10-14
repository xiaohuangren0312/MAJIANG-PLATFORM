from unittest.mock import patch
from django.test import TestCase,Client,override_settings
from django.conf import settings
from django.contrib.auth import get_user_model
import re

@override_settings(VENUES={},DRAFT_ENABLED=False)
class LoginFeedbackTests(TestCase):
 def setUp(self):
  get_user_model().objects.create_user('login-check',password='Correct-Password123!')
  self.c=Client(enforce_csrf_checks=True)
 def token(self,response):
  return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',response.content.decode())[1]
 def test_wrong_password_has_normal_feedback(self):
  page=self.c.get('/login/');self.assertIn('no-store',page['Cache-Control'])
  response=self.c.post('/login/',{'username':'login-check','password':'wrong','csrfmiddlewaretoken':self.token(page)})
  self.assertEqual(response.status_code,200);self.assertContains(response,'用户名或密码不正确')
  self.assertContains(response,'value="login-check"');self.assertNotContains(response,'value="wrong"')
 def test_stale_token_recovers_without_authentication(self):
  old=self.c.get('/login/');self.c.cookies[settings.CSRF_COOKIE_NAME]='b'*32
  with patch('league.views.authenticate') as auth:
   response=self.c.post('/login/',{'username':'login-check','password':'Correct-Password123!','csrfmiddlewaretoken':self.token(old)})
   self.assertEqual(response.status_code,403);auth.assert_not_called()
  html=response.content.decode();self.assertIn('登录页面已失效',html);self.assertNotIn('DEBUG',html);self.assertNotIn('Correct-Password123!',html)
  self.assertIn('no-store',response['Cache-Control'])
  response=self.c.post('/login/',{'username':'login-check','password':'Correct-Password123!','csrfmiddlewaretoken':self.token(response)})
  self.assertEqual(response.status_code,302);self.assertEqual(response.url,'/')
 def test_missing_cookie_and_untrusted_origin_remain_rejected(self):
  response=self.c.post('/login/',{'username':'<script>alert(1)</script>','password':'secret'})
  self.assertEqual(response.status_code,403);self.assertNotIn('<script>alert(1)</script>',response.content.decode())
  page=self.c.get('/login/')
  with patch('league.views.authenticate') as auth:
   response=self.c.post('/login/',{'username':'login-check','password':'Correct-Password123!','csrfmiddlewaretoken':self.token(page)},HTTP_ORIGIN='https://untrusted.example')
   self.assertEqual(response.status_code,403);auth.assert_not_called()
