import copy
from django.test import SimpleTestCase, TestCase
from league.domain import initial, Invalid, validate_lineup
from .domain import configuration, first_pick, allocate, exclusion
from . import tests as fixtures
from .services import projection

class CoachCapacityRulesTests(SimpleTestCase):
    def setUp(self):
        self.doc=initial()
        self.doc['teams']=[dict(id=f't{i}',name=f'Team {i}',active=True) for i in range(9)]
        self.doc['players']=[dict(id=f'c{i}',name=f'Coach {i}',teamId=f't{i}',active=True) for i in range(9)]
        self.doc['players'] += [dict(id=f'p{i}',name=f'Player {i}',teamId=None,active=True) for i in range(46)]
        self.payload=dict(teams=[dict(teamId=f't{i}',coachUserId=i+1,coachPlayerId=f'c{i}',coachPlaying=i!=8,capacity=7 if i==8 else 6,coachPrice=0) for i in range(9)],candidates=[dict(playerId=f'p{i}') for i in range(46)])
    def test_default_six_and_s4_total_fifty_five(self):
        del self.payload['teams'][0]['capacity']
        d=configuration(self.doc,'team',self.payload)
        self.assertEqual(d['draft']['teams'][0]['capacity'],6)
        self.assertEqual(sum(t['capacity'] for t in d['draft']['teams']),55)
        self.assertEqual(d['draft']['teams'][-1]['balance'],30)
    def test_full_time_coach_zero_price_and_boolean_validation(self):
        self.payload['teams'][-1]['coachPrice']=1
        with self.assertRaises(Invalid):configuration(self.doc,'team',self.payload)
        self.payload['teams'][-1]['coachPrice']=0
        self.payload['teams'][-1]['coachPlaying']='false'
        with self.assertRaises(Invalid):configuration(self.doc,'team',self.payload)
    def test_six_picks_for_full_time_coach_five_for_ordinary(self):
        d=first_pick(configuration(self.doc,'team',self.payload),'start',{})
        self.assertTrue(d['players'][8]['nonPlayingCoach'])
        self.assertTrue(d['players'][8]['active'])
        for i in range(6):allocate(d,'t8',f'p{i}','first-pick')
        with self.assertRaises(Invalid):allocate(d,'t8','p6','first-pick')
        for i in range(6,11):allocate(d,'t0',f'p{i}','first-pick')
        with self.assertRaises(Invalid):allocate(d,'t0','p11','first-pick')
        self.assertEqual(exclusion(d,d['draft']['teams'][-1],0),'人数已满')
    def test_full_time_coach_not_candidate_or_match_player(self):
        d=first_pick(configuration(self.doc,'team',self.payload),'start',{})
        seats=[dict(teamId=f't{i}',playerId=f'c{i}') for i in [8,0,1,2]]
        with self.assertRaisesMessage(Invalid,'全职教练'):validate_lineup(d,'team',seats,True)
        seats[0]=dict(teamId='t3',playerId='c3')
        self.assertEqual(len(validate_lineup(d,'team',seats,True)),4)
        self.doc['players'][-1]['nonPlayingCoach']=True
        with self.assertRaises(Invalid):configuration(self.doc,'team',self.payload)
    def test_existing_coach_flag_defaults_to_nonplaying(self):
        self.doc['players'][8]['nonPlayingCoach']=True
        del self.payload['teams'][8]['coachPlaying']
        d=configuration(self.doc,'team',self.payload)
        self.assertFalse(d['draft']['teams'][8]['coachPlaying'])

class CoachCapacityServiceTests(TestCase):
    setUp=fixtures.ActivityTests.setUp
    call=fixtures.ActivityTests.call
    setup_activity=fixtures.ActivityTests.setup_activity
    def test_nonplaying_flag_persisted_at_start_and_defaults_exposed(self):
        self.payload['teams'][0].update(coachPlaying=False,coachPrice=0,capacity=7)
        self.setup_activity();self.call('start');self.event.refresh_from_db()
        self.assertTrue(self.event.document['players'][0]['nonPlayingCoach'])
        value=projection(self.activity,self.admin)
        self.assertTrue(value['players'][0]['nonPlayingCoach'])
        self.assertFalse(value['draft']['teams'][0]['coachPlaying'])
    def test_finish_reports_vacancies_without_changing_existing_finish_policy(self):
        from .lifecycle import finish_review
        self.setup_activity();self.call('start')
        self.activity.document.update(phase='review-ready',candidates=[])
        self.activity.save()
        result=finish_review(self.activity)
        self.assertEqual(result['vacancies'],10)
        self.assertIn('仍缺10人',result['message'])
    def test_manager_page_contains_nonplaying_control_and_capacity_summary(self):
        self.client.force_login(self.admin)
        response=self.client.get(f'/draft/{self.activity.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'全职教练</option>')
        self.assertContains(response,'capacity-summary')
