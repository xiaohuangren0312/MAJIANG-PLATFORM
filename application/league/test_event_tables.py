import copy
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from .domain import initial, apply, Invalid
from .event_tables import catalog, display
from .models import Event, Audit
from .projection import public_event

class TableDomainTests(SimpleTestCase):
    def setUp(self):
        d=apply(initial(),'personal','stage',{'name':'常规赛'})
        for name in ['甲','乙','丙','丁']:d=apply(d,'personal','player',{'name':name})
        self.d=apply(d,'personal','match',dict(stageId=d['stages'][0]['id'],date='2030-01-01',number=1,seats=[{'playerId':p['id']} for p in d['players']]))
        self.rows=[dict(number=1,name='黑八',active=True),dict(number=2,name='蓝八',active=True),dict(number=9,name='九号',active=True)]
    def configured(self):return apply(self.d,'personal','tables-update',{'tables':self.rows})
    def test_rename_preserves_references_and_has_no_suffix(self):
        old=copy.deepcopy(self.d);d=self.configured()
        self.assertEqual(d['matches'],old['matches']);self.assertEqual(self.d,old)
        self.assertEqual(display(d,1),'黑八');self.assertEqual(display(d,2),'蓝八')
    def test_names_and_numbers_validated(self):
        for rows in [[],[dict(number=1,name='')],[dict(number=1,name='a'),dict(number=2,name='A')],[dict(number=True,name='a')],[dict(number=1,name='a',active=False)], [dict(number=2,name='a')]]:
            with self.assertRaises(Invalid):apply(self.d,'personal','tables-update',{'tables':rows})
    def test_stage_defaults_do_not_rewrite_matches(self):
        d=self.configured();old=copy.deepcopy(d['matches']);sid=d['stages'][0]['id']
        d=apply(d,'personal','stage-update',dict(id=sid,tableNumbers=[2,9]))
        self.assertEqual(d['matches'],old);self.assertEqual(d['stages'][0]['tableNumbers'],[2,9])
        for values in [[],[1,1],[3],[True]]:
            with self.assertRaises(Invalid):apply(d,'personal','stage-update',dict(id=sid,tableNumbers=values))
        with self.assertRaises(Invalid):apply(d,'personal','tables-update',dict(tables=[self.rows[0],dict(self.rows[1],active=False),self.rows[2]]))
    def test_inactive_table_cannot_receive_new_match(self):
        d=self.configured();d['tables'][1]['active']=False
        with self.assertRaises(Invalid):apply(d,'personal','match',dict(stageId=d['stages'][0]['id'],date='2030-01-02',number=2,seats=[{'playerId':p['id']} for p in d['players']]))
    def test_noncontiguous_pairing_uses_stage_tables(self):
        from .pairing import preview,commit
        d=self.configured();d['matches']=[];d['stages'][0]['tableNumbers']=[9]
        p=preview(d,'personal',dict(stageId=d['stages'][0]['id'],date='2030-01-02',time='19:30'))
        self.assertEqual(p['tables'][0]['number'],9)
        result=commit(d,'personal',p);self.assertEqual(result['matches'][0]['number'],9)
    def test_unset_stage_is_not_all_tables(self):
        from .event_tables import stage_tables
        d=self.configured();stage=d['stages'][0]
        self.assertEqual(stage_tables(d,stage),[])
        self.assertEqual(len(d['matches']),1)
        with self.assertRaisesMessage(Invalid,'请先设置本阶段使用桌次'):
            apply(d,'personal','match',dict(stageId=stage['id'],date='2030-01-02',number=1,seats=[{'playerId':p['id']} for p in d['players']]))
        d=apply(d,'personal','stage-update',dict(id=stage['id'],tableNumbers=[1]))
        self.assertEqual(len(apply(d,'personal','match',dict(stageId=stage['id'],date='2030-01-02',number=1,seats=[{'playerId':p['id']} for p in d['players']]))['matches']),2)
    def test_archive_cannot_change(self):
        d=self.configured();d['archive']={'publicPayload':{}}
        with self.assertRaises(Invalid):apply(d,'personal','tables-update',dict(tables=self.rows))

class TableAPITests(TestCase):
    def setUp(self):
        U=get_user_model();self.manager=U.objects.create_user('tables-manager');self.other=U.objects.create_user('tables-viewer')
        d=apply(initial(),'team','stage',{'name':'常规赛'})
        self.event=Event.objects.create(name='Table event',kind='team',document=d,public=True);self.event.editors.add(self.manager)
        self.url='/api/events/'+str(self.event.pk)+'/'
    def test_management_asset_available(self):
        self.assertEqual(self.client.get('/assets/event-tables.js').status_code,200)
    def test_permission_revision_audit_and_public_projection(self):
        payload=dict(action='tables-update',revision=self.event.revision,tables=[dict(number=1,name='黑八',active=True),dict(number=2,name='蓝八',active=True)])
        self.client.force_login(self.other)
        self.assertIn(self.client.post(self.url,payload,content_type='application/json').status_code,[403,404])
        self.client.force_login(self.manager)
        response=self.client.post(self.url,payload,content_type='application/json');self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.client.post(self.url,payload,content_type='application/json').status_code,409)
        self.event.refresh_from_db();self.assertEqual(public_event(self.event)['tables'][0]['name'],'黑八')
        audit=Audit.objects.get(event=self.event);self.assertEqual(audit.actor,self.manager);self.assertEqual(audit.action,'tables-update')
        other=Event.objects.create(name='Other',kind='team',document=initial())
        self.assertEqual(self.client.post('/api/events/'+str(other.pk)+'/',dict(payload,revision=other.revision),content_type='application/json').status_code,404)
