import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Event,Audit
from .domain import initial
from .history_correction import preview,commit

class HistoryCorrectionTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user(username='root',is_superuser=True)
        self.child=get_user_model().objects.create_user(username='child')
        self.other=get_user_model().objects.create_user(username='other')
        self.payload={'id':'s-test','name':'历史赛事','type':'team','stages':[{'id':'regular','name':'常规赛'},{'id':'final','name':'决赛'}],'players':[{'id':'p'+str(i),'name':'选手'+str(i),'teamId':'t'+str(i)} for i in range(1,6)],'teams':[{'id':'t'+str(i),'name':'队伍'+str(i)} for i in range(1,6)],'results':[{'id':'r1','stageId':'regular','date':'2026-01-01','number':1,'seats':[{'playerId':'p'+str(i),'teamId':'t'+str(i),'score':None,'rank':None,'base':None,'penalty':None,'points':v,'teamPoints':v} for i,v in enumerate([500,100,-100,-500],1)],'penalties':[],'yakuman':[]}],'schedule':[{'id':'r1','resultId':'r1','players':[]}],'statistics':{},'snapshots':[{'name':'决赛','rows':[{'name':'队伍1','total':999,'carry':250}]}]}
        for stage in ['all','regular','final']:
            self.payload['statistics'][stage]={}
            for metric in ['raw','competitive']:
                self.payload['statistics'][stage][metric]={kind:[dict(id=('p' if kind=='player' else 't')+str(i),name='对象'+str(i),total=v+(250 if stage=='final' else 0),raw=v,carry=250 if stage=='final' else 0,rank=i) for i,v in enumerate([500,100,-100,-500,0],1)] for kind in ['player','team']}
        self.doc=initial();self.doc['historySnapshot']=copy.deepcopy(self.payload)
        self.e=Event.objects.create(name='历史赛事',kind='team',document=self.doc);self.e.editors.add(self.child)
        self.url=f'/api/events/{self.e.id}/';self.client.force_login(self.child)
    def body(self):
        seats=copy.deepcopy(self.payload['results'][0]['seats']);seats[0]['points']=600;seats[0]['teamPoints']=650
        return dict(id='r1',reason='按原始成绩单更正',seats=seats)
    def test_delta_source_and_carry(self):
        p,new=preview(self.doc,self.body());self.assertEqual(self.doc['historySnapshot'],self.payload)
        self.assertEqual(new['statistics']['regular']['raw']['player'][0]['total'],600)
        self.assertEqual(new['statistics']['regular']['raw']['team'][0]['total'],650)
        self.assertEqual(new['statistics']['final'],self.payload['statistics']['final'])
        self.assertEqual(new['snapshots'],self.payload['snapshots'])
        self.assertIn('保留',p['notice'])
    def test_repeated_correction_not_double_applied(self):
        d=commit(self.doc,self.body());b=self.body();b['seats'][0]['points']=700
        d=commit(d,b)
        row=next(x for x in d['historyCurrent']['statistics']['all']['raw']['player'] if x['id']=='p1')
        self.assertEqual(row['total'],700);self.assertEqual(d['historySnapshot'],self.payload)
    def test_attribution_transfers_points_and_schedule(self):
        b=self.body();b['seats'][0].update(playerId='p5',teamId='t5',points=500,teamPoints=500)
        _,new=preview(self.doc,b);rows={x['id']:x for x in new['statistics']['all']['raw']['player']}
        self.assertEqual(rows['p1']['total'],0);self.assertEqual(rows['p5']['total'],500)
        self.assertEqual(new['schedule'][0]['players'][0]['playerId'],'p5')
        self.assertEqual(new['players'],self.payload['players'])
    def test_signed_commit_audit_and_stale(self):
        response=self.client.post(self.url,dict(action='history-preview',revision=1,**self.body()),content_type='application/json');self.assertEqual(response.status_code,200)
        b=dict(action='history-correct',revision=1,token=response.json()['token'],acknowledgeCarry=True,reason='伪造不同原因')
        self.assertEqual(self.client.post(self.url,b,content_type='application/json').status_code,200)
        self.e.refresh_from_db();self.assertEqual(self.e.document['historySnapshot'],self.payload)
        self.assertEqual(Audit.objects.get(event=self.e).reason,'按原始成绩单更正')
        self.assertEqual(self.client.post(self.url,b,content_type='application/json').status_code,409)
    def test_permission_and_wrong_event(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,dict(action='history-preview',revision=1,**self.body()),content_type='application/json').status_code,404)
        self.client.force_login(self.child)
        res=self.client.post(self.url,dict(action='history-preview',revision=1,**self.body()),content_type='application/json').json()
        second=Event.objects.create(name='另一个',kind='team',document=self.doc);second.editors.add(self.child)
        self.assertEqual(self.client.post(f'/api/events/{second.id}/',dict(action='history-correct',revision=1,token=res['token'],acknowledgeCarry=True),content_type='application/json').status_code,400)
    def test_invalid_mapping_blank_and_duplicate(self):
        for field,value in [('playerId','outside'),('playerId','p2'),('teamId','t2'),('points',None),('points',1.5)]:
            b=self.body();b['seats'][0][field]=value
            response=self.client.post(self.url,dict(action='history-preview',revision=1,**b),content_type='application/json')
            self.assertEqual(response.status_code,400,(field,value))
        b=self.body();b['reason']=''
        self.assertEqual(self.client.post(self.url,dict(action='history-preview',revision=1,**b),content_type='application/json').status_code,200)
    def test_commit_requires_acknowledgement(self):
        res=self.client.post(self.url,dict(action='history-preview',revision=1,**self.body()),content_type='application/json').json()
        self.assertEqual(self.client.post(self.url,dict(action='history-correct',revision=1,token=res['token']),content_type='application/json').status_code,400)
    def test_known_identity_cannot_orphan_achievement(self):
        self.doc['historySnapshot']['results'][0]['yakuman']=[{'playerId':'p1'}]
        b=self.body();b['seats'][0]['playerId']='p5'
        from .domain import Invalid
        with self.assertRaises(Invalid):preview(self.doc,b)

    def test_unaffected_statistics_preserved(self):
        _,new=preview(self.doc,self.body())
        for metric in ['raw','competitive']:
            for kind in ['player','team']:
                before={r['id']:r for r in self.payload['statistics']['regular'][metric][kind]}
                after={r['id']:r for r in new['statistics']['regular'][metric][kind]}
                for key in before:
                    if key.endswith('1'):continue
                    self.assertEqual({k:v for k,v in after[key].items() if k!='rank'},{k:v for k,v in before[key].items() if k!='rank'})
