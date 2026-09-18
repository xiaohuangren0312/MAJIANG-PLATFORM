import copy
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from .domain import initial, apply, Invalid
from .roster_delete import delete_roster
from .models import Event, Audit

class DeleteRosterTests(SimpleTestCase):
    def setUp(self):
        self.d=apply(initial(),'team','team',{'name':'甲队'})
        self.t=self.d['teams'][0]['id']
        self.d=apply(self.d,'team','player',{'name':'甲','teamId':self.t})
        self.p=self.d['players'][0]['id']
    def test_unused_delete_is_copy_and_team_requires_empty_roster(self):
        original=copy.deepcopy(self.d)
        with self.assertRaisesMessage(Invalid,'选手归属'):delete_roster(self.d,'team',self.t)
        d=apply(self.d,'team','player-delete',{'id':self.p})
        self.assertEqual(self.d,original)
        self.assertFalse(d['players'])
        self.assertFalse(apply(d,'team','team-delete',{'id':self.t})['teams'])
    def test_all_match_states_and_settlement_coach_block(self):
        for state in ['draft','published','cancelled']:
            d=copy.deepcopy(self.d);d['matches']=[{'state':state,'seats':[{'playerId':self.p,'teamId':self.t}]}]
            with self.assertRaisesMessage(Invalid,'赛程与战果'):delete_roster(d,'player',self.p)
        d=copy.deepcopy(self.d);d['settlements']=[{'rows':{self.p:123}}]
        with self.assertRaisesMessage(Invalid,'阶段结算'):delete_roster(d,'player',self.p)
        d=copy.deepcopy(self.d);d['teams'][0]['coach']={'playerId':self.p}
        with self.assertRaisesMessage(Invalid,'教练'):delete_roster(d,'player',self.p)
    def test_foreign_id_archive_and_type_rejected(self):
        for kind,id in [('team',self.p),('player','foreign'),('other',self.p)]:
            with self.assertRaises(Invalid):delete_roster(self.d,kind,id)
        with self.assertRaises(Invalid):delete_roster(dict(self.d,archive={'locked':True}),'player',self.p)
    def test_history_supplement_deleted_source_preserved_and_refs_protected(self):
        source={'teams':[],'players':[{'id':'old','name':'原名单'}]}
        d={'historySnapshot':source,'historyCurrent':copy.deepcopy(source)}
        d['historyCurrent']['players'].append({'id':'new','name':'补录'})
        result=delete_roster(d,'player','new')
        self.assertEqual(result['historySnapshot'],source)
        self.assertEqual(len(d['historyCurrent']['players']),2)
        self.assertEqual(len(result['historyCurrent']['players']),1)
        removed=delete_roster(d,'player','old')
        self.assertEqual(removed['historySnapshot'],source)
        self.assertNotIn('old',[x['id'] for x in removed['historyCurrent']['players']])
        d['historyCurrent']['results']=[{'seats':[{'playerId':'new'}]}]
        with self.assertRaisesMessage(Invalid,'历史战果'):delete_roster(d,'player','new')

class DeleteRosterApiTests(TestCase):
    def test_permissions_revision_audit_and_archive(self):
        user=get_user_model().objects.create_user('delete-editor')
        other=get_user_model().objects.create_user('delete-other')
        d=apply(initial(),'personal','player',{'name':'误录'})
        e=Event.objects.create(name='删除验收',kind='personal',document=d);e.editors.add(user)
        url=f'/api/events/{e.id}/';body={'action':'player-delete','revision':1,'id':d['players'][0]['id']}
        self.client.force_login(other)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,404)
        self.client.force_login(user)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,200)
        e.refresh_from_db();self.assertFalse(e.document['players']);self.assertEqual(e.revision,2)
        self.assertEqual(Audit.objects.filter(event=e,action='player-delete').count(),1)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,409)
        e.document['archive']={'locked':True};e.save();body['revision']=2
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,403)
