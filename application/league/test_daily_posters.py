import copy
from unittest.mock import patch
from django.test import TestCase
from .test_coach_lineups import CoachLineupTests

class DailyPosterTests(TestCase):
    setUp=CoachLineupTests.setUp
    def url(self): return f'/api/posters/{self.e.pk}/daily/?date=2030-01-02'
    def payload(self):
        return dict(name='赛事',stages=[dict(id='stage',name='常规赛')],teams=[dict(id='a',name='甲'),dict(id='b',name='乙')],players=[dict(id='p',name='选手')],results=[dict(id=str(i),stageId='stage',date=day,time='19:30',table='A',seats=[dict(playerId='p',teamId='a',rank=1,points=points,teamPoints=points),dict(playerId='q',teamId='b',rank=2,points=-points,teamPoints=-points)]) for i,(day,points) in enumerate([('2030-01-01',-20),('2030-01-02',40),('2030-01-03',100)])],statistics={'stage':{'competitive':{'team':[dict(id='a',name='甲',carry=10,raw=120,total=130),dict(id='b',name='乙',carry=0,raw=-120,total=-120)]}}})
    def test_permissions_and_invalid_date(self):
        self.assertEqual(self.client.get(self.url()).status_code,401)
        self.client.force_login(self.coach)
        self.assertEqual(self.client.get(self.url()).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url().split('?')[0]+'?date=oops').status_code,400)
    def test_day_bounds_carry_and_rank_changes(self):
        self.client.force_login(self.admin)
        with patch('league.projection.public_event',return_value=self.payload()):
            response=self.client.get(self.url())
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        data=response.json();self.assertEqual(len(data['matches']),1)
        a=data['stages'][0]['rows'][0]
        self.assertEqual((a['before'],a['delta'],a['total'],a['beforeRank'],a['rank']),(-10,40,30,2,1))
        self.e.refresh_from_db();self.assertEqual(self.e.revision,1)
    def test_incomplete_history_is_not_invented(self):
        self.client.force_login(self.admin);p=self.payload();p['statistics']['stage']['competitive']['team'][0]['raw']=999
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        self.assertEqual(data['stages'][0]['rows'],[])
        self.assertTrue(data['stages'][0]['notice'])
    def test_no_published_results(self):
        self.client.force_login(self.admin)
        data=self.client.get(self.url()).json()
        self.assertEqual(data['matches'],[])
        self.assertEqual(data['stages'],[])

    def test_winds_are_not_finishing_places(self):
        self.client.force_login(self.admin);p=self.payload()
        p['results'][1]['seats']=[dict(playerId='p',teamId='a',wind=w,rank=rank,points=0,teamPoints=0) for w,rank in [('北',1),('南',4),('东',3),('西',2)]]
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        seats=data['matches'][0]['seats']
        self.assertEqual([s['wind'] for s in seats],['东','南','西','北'])
        self.assertEqual([s['rank'] for s in seats],[3,4,2,1])

    def test_export_preserves_score_and_team_art(self):
        self.client.force_login(self.admin);p=self.payload()
        p['teams'][0].update(imageUrl='/media/roster/team.png',color='#123456')
        p['results'][1]['seats'][0].update(wind='东',score=45200)
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        seat=data['matches'][0]['seats'][0]
        self.assertEqual(seat['score'],45200)
        self.assertEqual(seat['points'],40)
        self.assertEqual(seat['teamImageUrl'],'/media/roster/team.png')
        self.assertEqual(seat['teamColor'],'#123456')
        row=data['stages'][0]['rows'][0]
        self.assertEqual(row['imageUrl'],'/media/roster/team.png')
        self.assertEqual(row['color'],'#123456')

    def test_daily_assets_are_served_and_included(self):
        self.client.force_login(self.admin)
        page=self.client.get('/manage/posters/?type=daily')
        for name in ['daily-poster-renderer.js','daily-posters.js']:
            self.assertContains(page,'/assets/'+name)
            response=self.client.get('/assets/'+name)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response['Content-Type'],'text/javascript')
            list(response.streaming_content)

    def test_advancement_count_comes_from_published_stage(self):
        self.client.force_login(self.admin)
        p=self.payload();p['stages'][0]['advanceCount']=6
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        self.assertEqual(data['stages'][0]['advanceCount'],6)
        p['stages'][0].pop('advanceCount')
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        self.assertEqual(data['stages'][0]['advanceCount'],0)

    def test_team_half_games_are_date_and_stage_scoped(self):
        self.client.force_login(self.admin);p=self.payload()
        def scheduled(mid,teams,state='scheduled',stage='stage',result=None):
            return dict(id=mid,resultId=result,stageId=stage,state=state,players=[dict(teamId=t,playerId=None) for t in teams])
        p['schedule']=[scheduled('schedule-0',['a','b'],'completed',result='0'),
                       scheduled('1',['a','b'],'completed'),scheduled('2',['a','b'],'completed'),
                       scheduled('future-a',['a','a']),scheduled('future-b',['b']),scheduled('future-b2',['b']),
                       scheduled('cancelled',['a','b'],'cancelled'),scheduled('other',['a','b'],stage='next')]
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        rows={r['id']:r for r in data['stages'][0]['rows']}
        self.assertEqual((rows['a']['playedGames'],rows['a']['stageGames']),(2,4))
        self.assertEqual((rows['b']['playedGames'],rows['b']['stageGames']),(2,5))
        self.assertEqual(rows['a']['total'],30)

    def test_missing_schedule_does_not_invent_stage_total(self):
        self.client.force_login(self.admin)
        with patch('league.projection.public_event',return_value=self.payload()):
            data=self.client.get(self.url()).json()
        self.assertEqual(data['stages'][0]['rows'][0]['playedGames'],2)
        self.assertIsNone(data['stages'][0]['rows'][0]['stageGames'])

    def test_daily_report_preserves_per_match_commentators(self):
        self.client.force_login(self.admin);p=self.payload()
        p['results'][1]['resources']={'commentators':['解说甲','解说乙']}
        with patch('league.projection.public_event',return_value=p):
            data=self.client.get(self.url()).json()
        self.assertEqual(data['matches'][0]['commentators'],['解说甲','解说乙'])
