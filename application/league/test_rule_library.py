from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Event,RuleTemplate
from .tests import fixture
class RuleLibraryTests(TestCase):
 def test_reuse_preserves_existing_matches(self):
  admin=get_user_model().objects.create_user('rule-library-admin',is_superuser=True);self.client.force_login(admin)
  body={'name':'联赛方案','start':25000,'return':30000,'bonuses':[400,200,-100,-300]}
  r=self.client.post('/api/rule-templates/',body,content_type='application/json');self.assertEqual(r.status_code,201,r.content);tid=r.json()['id']
  self.assertEqual(self.client.post('/api/rule-templates/',body,content_type='application/json').status_code,400)
  e=Event.objects.create(name='已有赛事',kind='team',document=fixture());original=e.document['matches'][0]['rule']
  response=self.client.post(f'/api/events/{e.id}/',{'action':'rule-select','revision':1,'templateId':tid},content_type='application/json');self.assertEqual(response.status_code,200,response.content)
  e.refresh_from_db();self.assertEqual(e.document['matches'][0]['rule'],original);self.assertEqual(e.document['rules'][-1]['bonuses'],body['bonuses'])
  r=self.client.post('/api/events/',{'name':'新赛事','kind':'personal','ruleTemplateId':tid},content_type='application/json');self.assertEqual(r.status_code,201,r.content)
  new=Event.objects.get(pk=r.json()['id']);self.assertEqual(new.document['rules'][-1]['name'],'联赛方案')
  other=get_user_model().objects.create_user('rule-library-ordinary');self.client.force_login(other)
  self.assertEqual(self.client.get('/api/rule-templates/').status_code,403)
  self.assertEqual(self.client.post(f'/api/events/{e.id}/',{'action':'rule-select','revision':e.revision,'templateId':tid},content_type='application/json').status_code,404)

 def test_builtin_available_without_saved_templates(self):
  from .rule_presets import ML_TEMPLATE_ID, ML_RULE
  admin=get_user_model().objects.create_user('builtin-admin',is_superuser=True)
  self.client.force_login(admin)
  self.assertFalse(RuleTemplate.objects.exists())
  items=self.client.get('/api/rule-templates/').json()['templates']
  self.assertEqual(items[0]['id'],ML_TEMPLATE_ID)
  self.assertEqual(items[0]['rule'],ML_RULE)
  r=self.client.post('/api/events/',{'name':'默认方案赛事','kind':'team','ruleTemplateId':ML_TEMPLATE_ID},content_type='application/json')
  self.assertEqual(r.status_code,201,r.content)
  e=Event.objects.get(pk=r.json()['id'])
  self.assertEqual(len(e.document['rules']),1)
  self.assertEqual(e.document['rules'][0]['bonuses'],ML_RULE['bonuses'])
  e.document=fixture();e.save()
  original=e.document['matches'][0]['rule'].copy()
  r=self.client.post(f'/api/events/{e.id}/',{'action':'rule-select','revision':e.revision,'templateId':ML_TEMPLATE_ID},content_type='application/json')
  self.assertEqual(r.status_code,200,r.content)
  e.refresh_from_db()
  self.assertEqual(e.document['matches'][0]['rule'],original)
  self.assertEqual(e.document['rules'][-1]['bonuses'],ML_RULE['bonuses'])
  self.assertEqual(self.client.post('/api/rule-templates/',ML_RULE,content_type='application/json').status_code,400)
  self.assertFalse(RuleTemplate.objects.exists())
