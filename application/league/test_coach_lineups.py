import copy, datetime
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Event,Audit
from .domain import initial,apply
from .projection import public_event
from .coach_lineups import CST

class CoachLineupTests(TestCase):
    def setUp(self):
        U=get_user_model();self.coach=U.objects.create_user('coach');self.other=U.objects.create_user('other');self.admin=U.objects.create_user('admin');self.viewer=U.objects.create_user('viewer')
        d=apply(initial(),'team','stage',{'name':'常规赛'})
        for i in range(4):
            d=apply(d,'team','team',{'name':f'队伍{i}'})
            d=apply(d,'team','player',{'name':f'选手{i}','teamId':d['teams'][-1]['id']})
        self.tid=d['teams'][0]['id'];self.pid=d['players'][0]['id'];self.other_tid=d['teams'][1]['id'];self.other_pid=d['players'][1]['id']
        for time in ['19:30','21:00']:
            d=apply(d,'team','match',dict(date='2030-01-02',time=time,number=1,stageId=d['stages'][0]['id'],seats=[{'teamId':t['id']} for t in d['teams']]))
        d['coachAccounts']={str(self.coach.pk):{'active':True,'teamId':self.tid},str(self.other.pk):{'active':True,'teamId':self.other_tid}}
        self.e=Event.objects.create(name='赛事',kind='team',public=True,document=d);self.e.editors.add(self.admin)
        self.mid=d['matches'][0]['id'];self.mid2=d['matches'][1]['id']
        self.now=datetime.datetime(2030,1,2,16,0,tzinfo=CST)
        self.clock=patch('django.utils.timezone.now',return_value=self.now);self.clock.start();self.addCleanup(self.clock.stop)
    def post(self,user=None,rows=None,revision=None):
        self.client.force_login(user or self.coach);self.e.refresh_from_db()
        return self.client.post(f'/api/coach/lineups/{self.e.pk}/',{'revision':revision if revision is not None else self.e.revision,'rows':rows or [{'matchId':self.mid,'teamId':self.tid,'playerId':self.pid}]},content_type='application/json')
    def test_private_until_boundary_and_other_coach_cannot_see(self):
        self.assertEqual(self.post().status_code,200)
        self.e.refresh_from_db();public=public_event(self.e)['schedule'][0]
        self.assertIsNone(public['players'][0]['playerId'])
        self.client.force_login(self.other);response=self.client.get(f'/api/coach/lineups/{self.e.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertNotIn(self.pid,response.content.decode())
        with patch('django.utils.timezone.now',return_value=self.now.replace(hour=17,minute=30)):
            row=public_event(self.e)['schedule'][0]
            self.assertEqual(row['players'][0]['playerId'],self.pid)
            self.assertTrue(row['players'][0]['lineupPublished']);self.assertFalse(row['lineupPublished'])
            self.assertIsNone(row['players'][1]['playerId'])
        self.assertEqual(Audit.objects.filter(action='coach-lineup').count(),1)
    def test_permissions_and_revision(self):
        self.assertEqual(self.post(self.viewer).status_code,403)
        self.assertEqual(self.post(self.other).status_code,403)
        self.assertEqual(self.post(revision=99).status_code,409)
        self.assertEqual(self.post().status_code,200)
        self.e.refresh_from_db();self.e.document['coachAccounts'][str(self.coach.pk)]['active']=False;self.e.save()
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.post(self.admin).status_code,200)
        self.e.refresh_from_db();self.e.document['archiveRevision']={'test':True};self.e.save()
        self.assertEqual(self.post(self.admin).status_code,400)
    def test_custom_withdraw_and_published_edit(self):
        row={'matchId':self.mid,'teamId':self.tid,'playerId':self.pid,'mode':'custom','publishAt':'2030-01-02T18:00'}
        self.assertEqual(self.post(rows=[row]).status_code,200)
        self.assertEqual(self.post(rows=[dict(row,withdraw=True)]).status_code,200)
        self.e.refresh_from_db();self.assertIsNone(self.e.document['matches'][0]['seats'][0]['playerId'])
        self.assertEqual(self.post().status_code,200)
        with patch('django.utils.timezone.now',return_value=self.now.replace(hour=18)):
            self.assertEqual(self.post(rows=[dict(row,withdraw=True)]).status_code,400)
            self.assertEqual(self.post(rows=[dict(row,publishAt='2030-01-02T19:00')]).status_code,200)
            self.e.refresh_from_db();self.assertEqual(public_event(self.e)['schedule'][0]['players'][0]['playerId'],self.pid)
        with patch('django.utils.timezone.now',return_value=self.now.replace(hour=19,minute=30)):
            self.assertEqual(self.post().status_code,400)
    def test_bond_qualification_and_invalid_batch_rolls_back(self):
        row={'matchId':self.mid,'teamId':self.tid,'playerId':self.other_pid}
        self.assertEqual(self.post(rows=[row]).status_code,400)
        self.e.refresh_from_db();d=apply(self.e.document,'team','bond-player',dict(name='羁绊',teamId=self.tid,stageId=self.e.document['stages'][0]['id']));self.e.document=d;self.e.save()
        row['playerId']=d['players'][-1]['id']
        self.assertEqual(self.post(rows=[row,dict(row,matchId='missing')]).status_code,400)
        self.e.refresh_from_db();self.assertIsNone(self.e.document['matches'][0]['seats'][0]['playerId'])
        self.assertEqual(self.post(rows=[row]).status_code,200)
        self.e.refresh_from_db();self.assertTrue(self.e.document['matches'][0]['seats'][0]['bond'])
        self.e.document['stages'][0]['locked']=True;self.e.save()
        self.assertEqual(self.post(rows=[row]).status_code,400)
    def test_first_start_default_reschedule_and_bad_time(self):
        row={'matchId':self.mid2,'teamId':self.tid,'playerId':self.pid}
        self.assertEqual(self.post(rows=[row]).json()['rows'][1]['publishAt'],'2030-01-02T17:30:00+08:00')
        self.e.refresh_from_db();self.e.document=apply(self.e.document,'team','match-update',dict(id=self.mid,date='2030-01-02',time='18:00',number=1));self.e.save()
        self.assertEqual(public_event(self.e)['schedule'][1]['players'][0]['playerId'],self.pid)
        self.assertEqual(self.post(rows=[dict(row,mode='custom',publishAt='2030-01-02T22:00')]).status_code,400)
    def test_account_team_binding_and_cross_event_rejected(self):
        self.client.force_login(self.admin)
        url=f'/api/events/{self.e.pk}/'
        b={'action':'coach-manage','revision':1,'userId':str(self.coach.pk),'teamId':self.other_tid}
        self.assertEqual(self.client.post(url,b,content_type='application/json').status_code,200)
        self.assertEqual(self.post().status_code,403)
        self.client.force_login(self.admin);b.update(revision=2,teamId='foreign-team')
        self.assertEqual(self.client.post(url,b,content_type='application/json').status_code,400)
    def test_results_lock_and_existing_other_team_is_preserved(self):
        self.assertEqual(self.post(self.other,rows=[{'matchId':self.mid,'teamId':self.other_tid,'playerId':self.other_pid}]).status_code,200)
        self.assertEqual(self.post().status_code,200)
        self.e.refresh_from_db();self.assertEqual(self.e.document['matches'][0]['seats'][1]['playerId'],self.other_pid)
        self.e.document['matches'][0]['seats'][1]['score']=30000;self.e.save()
        self.assertEqual(self.post().status_code,400)

    def test_simultaneous_tables_anonymous_and_cancelled(self):
        self.assertEqual(self.client.get(f'/api/coach/lineups/{self.e.pk}/').status_code,401)
        self.assertEqual(self.post().status_code,200)
        self.e.refresh_from_db();d=self.e.document
        d=apply(d,'team','match',dict(date='2030-01-02',time='19:30',number=2,stageId=d['stages'][0]['id'],seats=[{'teamId':t['id']} for t in d['teams']]))
        self.e.document=d;self.e.save()
        self.assertEqual(self.post(rows=[{'matchId':d['matches'][-1]['id'],'teamId':self.tid,'playerId':self.pid}]).status_code,400)
        self.e.refresh_from_db();self.e.document['matches'][0]['state']='cancelled';self.e.save()
        self.assertEqual(self.post().status_code,400)
