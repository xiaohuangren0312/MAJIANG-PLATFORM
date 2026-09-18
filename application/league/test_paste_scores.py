from django.test import TestCase
from .tests import fixture
from .domain import Invalid
from .paste_scores import preview,commit,inverse
class PasteTests(TestCase):
 def setup_body(self):
  d=fixture();m=d['matches'][0];names=[next(p['name'] for p in d['players'] if p['id']==s['playerId']) for s in m['seats']]
  return d,dict(id=m['id'],text='\t'.join(names)+'\n400\t300\t200\t100',mode='scores')
 def test_paste_short_scores_and_publish(self):
  d,b=self.setup_body();p=preview(d,'team',b)
  self.assertEqual(p['candidates'][0]['scores'],[40000,30000,20000,10000])
  self.assertEqual(d['matches'][0]['state'],'draft')
  changed=commit(d,'team',b,0);self.assertEqual(changed['matches'][0]['state'],'published')
 def test_invalid_input_and_unknown_names(self):
  d,b=self.setup_body()
  for text in ['甲\t乙\t丙\t丁\n400\t300\t200\t100','bad','a,b,c,d\nNaN,1,2,3']:
   with self.assertRaises(Invalid):preview(d,'team',dict(b,text=text))
 def test_pt_roundtrip_and_tied_first(self):
  rule=dict(start=25000,**{'return':30000},bonuses=[500,100,-100,-300])
  self.assertIn([35000,35000,20000,10000],inverse(rule,[350,350,-200,-500]))
  self.assertEqual(inverse(rule,[600,100,-200,-500]),[[40000,30000,20000,10000]])

 def test_history_inverse_is_read_only_and_rejects_invalid_total(self):
  from django.contrib.auth import get_user_model
  from .models import Event
  user=get_user_model().objects.create_user('inverse-admin',is_superuser=True);self.client.force_login(user)
  d=fixture();d['historySnapshot']={'id':'s1','results':[{'id':'historical','seats':[{'points':p} for p in [600,100,-200,-500]],'penalties':[]}]}
  e=Event.objects.create(name='历史反算测试',kind='team',document=d)
  url=f'/api/history-backfill/events/{e.id}/';body={'action':'history-inverse','revision':1,'id':'historical'}
  r=self.client.post(url,body,content_type='application/json');self.assertEqual(r.status_code,200,r.content)
  self.assertEqual(r.json()['candidates'],[[40000,30000,20000,10000]])
  e.refresh_from_db();self.assertEqual(e.document,d);self.assertEqual(e.revision,1)
  e.document['historySnapshot']['results'][0]['seats'][0]['points']=601;e.save()
  self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,400)
