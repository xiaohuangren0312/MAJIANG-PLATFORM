import copy,json
from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from .models import Event,Audit
from .domain import initial,apply,score,Invalid
from .projection import public_event,statistics,settlement_preview,settle

def fixture(kind='team'):
    d=initial()
    d=apply(d,kind,'stage',{'name':'常规赛'})
    d=apply(d,kind,'stage',{'name':'决赛'})
    for i in range(4):
        if kind=='team':d=apply(d,kind,'team',{'name':f'队伍{i}'})
        d=apply(d,kind,'player',{'name':f'选手{i}','number':str(i),'teamId':d['teams'][i]['id'] if kind=='team' else None})
    seats=[{'playerId':p['id'],'teamId':p['teamId']} for p in d['players']]
    d=apply(d,kind,'match',dict(stageId=d['stages'][0]['id'],date='2026-09-06',number=1,time='19:30',seats=seats))
    return d
def publish(d,kind='team',penalties=None,yakuman=None):
    id=d['matches'][0]['id']
    d=apply(d,kind,'score',dict(id=id,scores=[41600,30000,20000,8400],penalties=penalties or [],yakuman=yakuman or []))
    return apply(d,kind,'publish',{'id':id})

class ScoringTests(TestCase):
    def test_ml(self):self.assertEqual([r['points'] for r in score(initial()['rules'][0],[41600,30000,20000,8400])],[616,100,-200,-516])
    def test_negative_and_ties(self):
        for values in [[60000,30000,20000,-10000],[25000]*4,[30000,30000,30000,10000],[40000,20000,20000,20000]]:
            rows=score(initial()['rules'][0],values);self.assertEqual(sum(r['base'] for r in rows),0)
    def test_bad_total_and_fraction(self):
        for values in [[25000]*3,[25000,25000,25000,24900],[25000,25000,25000,25000.0]]:
            with self.assertRaises(Invalid):score(initial()['rules'][0],values)
    def test_different_penalty_scopes(self):
        for scope,personal,team in [('personal',416,616),('team',616,416),('both',416,416)]:
            d=fixture();d=publish(d,penalties=[dict(playerId=d['players'][0]['id'],amount=200,scope=scope,explanation='裁定扣分')]);s=d['matches'][0]['seats'][0]
            self.assertEqual((s['points'],s['teamPoints'],s['rank']),(personal,team,1))
    def test_yakuman_no_extra_points(self):
        d=fixture();d=publish(d,yakuman=[dict(playerId=d['players'][0]['id'],types=['国士无双'],round='南二局',method='自摸',multiplier=2)])
        self.assertEqual(d['matches'][0]['seats'][0]['points'],616)
    def test_rule_snapshot(self):
        d=fixture();original=copy.deepcopy(d['matches'][0]['rule']);d=apply(d,'team','rule',{'name':'自定义','start':30000,'return':30000,'bonuses':[300,100,-100,-300]})
        self.assertEqual(d['matches'][0]['rule'],original)
    def test_cross_event_and_duplicate_lineup(self):
        d=fixture();m=d['matches'][0];seats=copy.deepcopy(m['seats']);seats[0]['playerId']='other-event'
        with self.assertRaises(Invalid):apply(d,'team','lineup',dict(id=m['id'],seats=seats))
        seats=copy.deepcopy(m['seats']);seats[1]=seats[0]
        with self.assertRaises(Invalid):apply(d,'team','lineup',dict(id=m['id'],seats=seats))
    def test_personal_has_no_teams(self):
        d=publish(fixture('personal'),'personal');self.assertTrue(all(s['teamId'] is None for s in d['matches'][0]['seats']))
        with self.assertRaises(Invalid):apply(d,'personal','team',{'name':'越界队伍'})
    def test_unpublished_lineup_hidden(self):
        d=fixture();e=Event(name='测试',kind='team',document=d)
        p=public_event(e);self.assertEqual(p['results'],[]);self.assertTrue(all(s['playerId'] is None for s in p['schedule'][0]['players']))
        e.document=apply(d,'team','lineup',dict(id=d['matches'][0]['id'],seats=d['matches'][0]['seats']))
        self.assertTrue(all(s['playerId'] for s in public_event(e)['schedule'][0]['players']))
    def test_published_is_not_directly_mutable(self):
        d=publish(fixture());id=d['matches'][0]['id']
        for action in ['score','publish','lineup','cancel']:
            with self.assertRaises(Invalid):apply(d,'team',action,{'id':id})
    def test_correction_requires_reason(self):
        d=publish(fixture())
        with self.assertRaises(Invalid):apply(d,'team','correct',dict(id=d['matches'][0]['id'],scores=[25000]*4))

class SettlementTests(TestCase):
    def args(self,d):return dict(source=d['stages'][0]['id'],target=d['stages'][1]['id'],ids=[x['id'] for x in d['teams']],numerator=1,denominator=2)
    def test_preview_no_mutation_and_carry_no_personal_halving(self):
        d=publish(fixture());old=copy.deepcopy(d);p=settlement_preview(d,'team',self.args(d));self.assertEqual(d,old)
        target=p['target'];new=settle(d,p,{})
        self.assertTrue(new['stages'][0]['locked']);self.assertEqual(statistics(new,target,True,'team')[0]['total'],308)
        self.assertEqual(statistics(new,'all',True,'player')[0]['total'],616)
        self.assertEqual(statistics(new,'all',True,'team')[0]['total'],616)
        with self.assertRaises(Invalid):settlement_preview(new,'team',self.args(new))
        with self.assertRaises(Invalid):apply(new,'team','correct',dict(id=new['matches'][0]['id'],reason='修正',scores=[25000]*4))
    def test_draft_prevents_settlement(self):
        d=fixture()
        with self.assertRaises(Invalid):settlement_preview(d,'team',self.args(d))
    def test_override_requires_reason(self):
        d=publish(fixture());p=settlement_preview(d,'team',self.args(d));id=p['rows'][0]['id']
        with self.assertRaises(Invalid):settle(d,p,{id:{'value':300}})
        changed=settle(d,p,{id:{'value':300,'reason':'赛事裁定'}});self.assertEqual(changed['settlements'][0]['rows'][id],300)

class ApiTests(TestCase):
    def setUp(self):
        User=get_user_model();self.owner=User.objects.create_user('owner',password='a-strong-test-password',is_staff=True,is_superuser=True);self.other=User.objects.create_user('other',password='another-test-password')
        self.event=Event.objects.create(name='私有赛事',kind='team',document=fixture());self.event.editors.add(self.owner)
        self.url=f'/api/events/{self.event.id}/'
    def test_anonymous_denied_and_private_hidden(self):
        self.assertEqual(self.client.get(self.url).status_code,401);self.assertEqual(self.client.get('/data.json').json()['tournaments'],[])
    def test_editor_isolation(self):
        self.client.force_login(self.other);self.assertEqual(self.client.get(self.url).status_code,404);self.assertEqual(self.client.get('/api/events/').json()['events'],[])
        self.assertEqual(self.client.post(self.url,json.dumps({'revision':1,'action':'stage','name':'入侵'}),content_type='application/json').status_code,404)
    def test_optimistic_revision_and_audit(self):
        self.client.force_login(self.owner);payload={'revision':1,'action':'stage','name':'新阶段'}
        self.assertEqual(self.client.post(self.url,json.dumps(payload),content_type='application/json').status_code,200)
        self.assertEqual(self.client.post(self.url,json.dumps(payload),content_type='application/json').status_code,409)
        self.assertEqual(Audit.objects.filter(event=self.event).count(),1)
    def test_csrf_required(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(self.url,'{}',content_type='application/json').status_code,403)
    def test_invalid_action_atomic(self):
        self.client.force_login(self.owner);old=copy.deepcopy(self.event.document)
        self.assertEqual(self.client.post(self.url,json.dumps({'revision':1,'action':'player','name':'x','number':'x','teamId':'foreign'}),content_type='application/json').status_code,400)
        self.event.refresh_from_db();self.assertEqual(self.event.document,old);self.assertEqual(self.event.revision,1)
    def test_preview_bound_to_event_revision(self):
        self.event.document=publish(self.event.document);self.event.save();self.client.force_login(self.owner);d=self.event.document
        args=dict(action='settlement-preview',revision=1,source=d['stages'][0]['id'],target=d['stages'][1]['id'],ids=[t['id'] for t in d['teams']])
        r=self.client.post(self.url,json.dumps(args),content_type='application/json');self.assertEqual(r.status_code,200);token=r.json()['token']
        self.event.revision=2;self.event.save()
        r=self.client.post(self.url,json.dumps(dict(action='settlement-commit',revision=2,token=token)),content_type='application/json');self.assertEqual(r.status_code,400)
    def test_full_http_publish_and_reload(self):
        self.client.force_login(self.owner)
        e=self.client.post('/api/events/',json.dumps({'name':'个人赛端到端','kind':'personal'}),content_type='application/json').json()
        url=f"/api/events/{e['id']}/"
        def command(action,**body):
            current=self.client.get(url).json()
            r=self.client.post(url,json.dumps(dict(action=action,revision=current['revision'],**body)),content_type='application/json')
            self.assertEqual(r.status_code,200,r.content)
            return self.client.get(url).json()['document']
        d=command('stage',name='常规赛')
        for i in range(4):d=command('player',name=f'选手{i}',number=str(i))
        d=command('match',stageId=d['stages'][0]['id'],date='2026-09-06',number=1,time='19:30',seats=[dict(playerId=p['id'],teamId=None) for p in d['players']])
        id=d['matches'][0]['id'];command('score',id=id,scores=[41600,30000,20000,8400])
        command('visibility',public=True)
        before=self.client.get('/data.json').json()['tournaments'][0];self.assertEqual(before['results'],[])
        command('publish',id=id)
        # An independent anonymous client must see exactly the committed result.
        payload=Client().get('/data.json').json()['tournaments'][0]
        self.assertEqual(len(payload['results']),1)
        self.assertEqual(payload['statistics']['all']['raw']['player'][0]['total'],616)
        command('correct',id=id,scores=[25000]*4,reason='裁判核对更正')
        payload=Client().get('/data.json').json()['tournaments'][0]
        self.assertEqual(len(payload['results']),1)
        self.assertEqual(sum(r['total'] for r in payload['statistics']['all']['raw']['player']),0)


class RosterTests(TestCase):
    def test_edit_identity_keeps_ids_and_duplicate_guards(self):
        d=fixture();p=d['players'][0]
        changed=apply(d,'team','player-update',dict(id=p['id'],name='新昵称',number='新编号',reason='更正报名'))
        self.assertEqual(changed['players'][0]['id'],p['id'])
        self.assertEqual(changed['players'][0]['name'],'新昵称')
        with self.assertRaises(Invalid):apply(d,'team','player-update',dict(id=p['id'],number=d['players'][1]['number'],reason='测试'))
    def test_reason_boolean_and_event_scope(self):
        d=fixture();id=d['players'][0]['id']
        for body in [dict(id=id),dict(id=id,reason='测试',active='false'),dict(id='foreign',reason='测试')]:
            with self.assertRaises(Invalid):apply(d,'team','player-update',body)
    def test_pending_transfer_and_disable_rejected(self):
        d=fixture();p=d['players'][0]
        for body in [dict(teamId=d['teams'][1]['id']),dict(active=False)]:
            with self.assertRaises(Invalid):apply(d,'team','player-update',dict(id=p['id'],reason='测试',**body))
        with self.assertRaises(Invalid):apply(d,'team','team-update',dict(id=d['teams'][0]['id'],active=False,reason='测试'))
    def test_transfer_preserves_published_contribution(self):
        d=publish(fixture());p=d['players'][0];old_team=p['teamId'];historical=copy.deepcopy(d['matches'][0])
        d=apply(d,'team','team',dict(name='新队伍'));new_team=d['teams'][-1]['id']
        d=apply(d,'team','player-update',dict(id=p['id'],teamId=new_team,reason='赛间转队'))
        self.assertEqual(d['matches'][0],historical)
        self.assertEqual(d['players'][0]['membershipHistory'][0]['fromTeamId'],old_team)
        rows=statistics(d,'all',False,'team');self.assertEqual(next(r for r in rows if r['id']==old_team)['total'],616)
        self.assertEqual(next(r for r in rows if r['id']==new_team)['total'],0)
        # A later correction recalculates the original team, not today's team.
        d=apply(d,'team','correct',dict(id=historical['id'],scores=[40000,30000,20000,10000],reason='裁判更正'))
        self.assertEqual(d['matches'][0]['seats'][0]['teamId'],old_team)
        self.assertEqual(d['matches'][0]['seats'][0]['points'],600)
    def test_disabled_player_cannot_join_new_game_but_history_can_be_corrected(self):
        d=publish(fixture());p=d['players'][0]
        d=apply(d,'team','player-update',dict(id=p['id'],active=False,reason='暂停参赛'))
        seats=[dict(playerId=s['playerId'],teamId=s['teamId']) for s in d['matches'][0]['seats']]
        with self.assertRaises(Invalid):apply(d,'team','match',dict(stageId=d['stages'][0]['id'],date='2026-09-07',number=1,seats=seats))
        d=apply(d,'team','correct',dict(id=d['matches'][0]['id'],scores=[25000]*4,reason='更正历史'))
        d=apply(d,'team','player-update',dict(id=p['id'],active=True,reason='恢复参赛'))
        d=apply(d,'team','match',dict(stageId=d['stages'][0]['id'],date='2026-09-07',number=1,seats=seats))
        self.assertEqual(len(d['matches']),2)
    def test_team_status_color_and_restore(self):
        d=publish(fixture());id=d['teams'][0]['id']
        with self.assertRaises(Invalid):apply(d,'team','team-update',dict(id=id,color='url(evil)',reason='测试'))
        d=apply(d,'team','team-update',dict(id=id,active=False,color='#334455',reason='队伍停用'))
        self.assertEqual(d['teams'][0]['color'],'#334455')
        d=apply(d,'team','correct',dict(id=d['matches'][0]['id'],scores=[25000]*4,reason='修正已停用队伍旧成绩'))
        d=apply(d,'team','team-update',dict(id=id,active=True,reason='恢复'))
        self.assertTrue(d['teams'][0]['active'])
    def test_personal_cannot_transfer_to_team(self):
        d=publish(fixture('personal'),'personal')
        with self.assertRaises(Invalid):apply(d,'personal','player-update',dict(id=d['players'][0]['id'],teamId='other',reason='测试'))
    def test_membership_reasons_not_public(self):
        d=publish(fixture());d=apply(d,'team','player-update',dict(id=d['players'][0]['id'],teamId=d['teams'][1]['id'],reason='PRIVATE_TRANSFER_REASON'))
        payload=public_event(Event(name='公开赛',kind='team',document=d))
        self.assertNotIn('PRIVATE_TRANSFER_REASON',json.dumps(payload))
    def test_api_edit_audit_and_cross_event_guard(self):
        user=get_user_model().objects.create_user('roster-editor',password='test-password')
        d=publish(fixture());e=Event.objects.create(name='名单赛事',kind='team',document=d);e.editors.add(user)
        other=Event.objects.create(name='另一赛事',kind='team',document=fixture())
        self.client.force_login(user);url=f'/api/events/{e.id}/'
        body=dict(action='player-update',revision=1,id=d['players'][0]['id'],name='修订昵称',reason='报名修订')
        r=self.client.post(url,json.dumps(body),content_type='application/json');self.assertEqual(r.status_code,200)
        e.refresh_from_db();self.assertEqual(e.document['players'][0]['name'],'修订昵称')
        self.assertEqual(Audit.objects.get(event=e).reason,'报名修订')
        body.update(revision=2,teamId=other.document['teams'][0]['id'])
        self.assertEqual(self.client.post(url,json.dumps(body),content_type='application/json').status_code,400)
        e.refresh_from_db();self.assertEqual(e.revision,2)


class MultipleEventTests(TestCase):
    def event_data(self,d):
        pid=d['players'][0]['id']
        penalties=[dict(playerId=pid,amount=200,scope='both',explanation='第一项裁定'),dict(playerId=pid,amount=50,scope='personal',explanation='第二项裁定'),dict(playerId=pid,amount=30,scope='team',explanation='队伍处罚')]
        yakuman=[dict(playerId=pid,types=['大三元','字一色'],round='东四局一本场',method='自摸',multiplier=2),dict(playerId=pid,types=['四暗刻'],round='南二局',method='荣和',multiplier=1)]
        return penalties,yakuman
    def test_multiple_events_publish_and_correct_without_loss(self):
        d=fixture();penalties,yakuman=self.event_data(d);d=publish(d,penalties=penalties,yakuman=yakuman)
        m=d['matches'][0];self.assertEqual((m['seats'][0]['points'],m['seats'][0]['teamPoints']),(366,386))
        self.assertEqual(len(m['penalties']),3);self.assertEqual(len(m['yakuman']),2)
        d=apply(d,'team','correct',dict(id=m['id'],scores=[41600,30000,20000,8400],penalties=penalties,yakuman=yakuman,reason='核对全部记录'))
        self.assertEqual(d['matches'][0]['penalties'],penalties);self.assertEqual(d['matches'][0]['yakuman'],yakuman)
        p=public_event(Event(name='复合事件测试',kind='team',document=d))
        self.assertEqual(len(p['results'][0]['penalties']),3);self.assertEqual(len(p['results'][0]['yakuman']),2)
        self.assertEqual(p['statistics']['all']['raw']['player'][0]['yakuman'],2)
    def test_remove_one_event_preserves_remaining_and_recalculates(self):
        d=fixture();penalties,yakuman=self.event_data(d);d=publish(d,penalties=penalties,yakuman=yakuman)
        d=apply(d,'team','correct',dict(id=d['matches'][0]['id'],scores=[41600,30000,20000,8400],penalties=penalties[1:],yakuman=yakuman[1:],reason='撤销第一条记录'))
        m=d['matches'][0];self.assertEqual((m['seats'][0]['points'],m['seats'][0]['teamPoints']),(566,586));self.assertEqual(m['penalties'],penalties[1:]);self.assertEqual(m['yakuman'],yakuman[1:])
    def test_invalid_event_shapes_rejected(self):
        d=fixture();id=d['matches'][0]['id'];penalties,yakuman=self.event_data(d)
        for body in [dict(penalties=[None]),dict(yakuman=[None]),dict(penalties=penalties*34),dict(yakuman=[{**yakuman[0],'method':'未知'}]),dict(penalties=[{**penalties[0],'amount':0}])]:
            with self.assertRaises(Invalid):apply(d,'team','score',dict(id=id,scores=[25000]*4,**body))


class ThreeRoleTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.root=User.objects.create_superuser('roles-root',password='RoleTest-Root-12345')
        self.child=User.objects.create_user('roles-child',password='RoleTest-Child-12345')
        self.plain=User.objects.create_user('roles-plain',password='RoleTest-Plain-12345')
        self.e=Event.objects.create(name='授权赛事',kind='team',document=fixture());self.e.editors.add(self.child)
        self.other=Event.objects.create(name='独立赛事',kind='team',document=fixture())
        self.url=f'/api/events/{self.e.pk}/'
    def post(self,user,action,**body):
        self.client.force_login(user);self.e.refresh_from_db()
        return self.client.post(self.url,json.dumps(dict(action=action,revision=self.e.revision,**body)),content_type='application/json')
    def test_child_has_full_event_business_permissions(self):
        self.client.force_login(self.child);data=self.client.get(self.url).json()
        self.assertEqual(data['role'],'admin')
        for action in ['score','publish','correct','rule','settlement-commit','player-update']:self.assertIn(action,data['actions'])
        self.assertNotIn('grant',data['actions'])
        self.assertEqual(self.post(self.child,'stage',name='新增阶段').status_code,200)
        self.assertEqual(self.client.get(f'/api/events/{self.other.pk}/').status_code,404)
    def test_child_cannot_grant_or_create_accounts(self):
        self.assertEqual(self.post(self.child,'grant',username=self.plain.username,role='admin',reason='越权').status_code,403)
        self.assertEqual(self.client.post('/api/accounts/',json.dumps(dict(username='intruder',password='Strong-password-000')),content_type='application/json').status_code,403)
        self.assertEqual(self.client.post('/api/events/',json.dumps(dict(name='越权创建',kind='team')),content_type='application/json').status_code,403)
    def test_ordinary_account_no_management(self):
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.assertEqual(self.client.get('/api/events/').json()['events'],[])
        self.assertRedirects(self.client.get('/manage/'),'/',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/data.json').status_code,200)
    def test_root_grant_and_revoke_last_child(self):
        self.assertEqual(self.post(self.root,'grant',username=self.plain.username,role='admin',reason='任命').status_code,200)
        self.client.force_login(self.plain);self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.post(self.root,'grant',username=self.plain.username,role='revoke',reason='撤回').status_code,200)
        self.assertEqual(self.post(self.root,'grant',username=self.child.username,role='revoke',reason='全部撤回').status_code,200)
        self.client.force_login(self.child);self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.force_login(self.root);self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(Audit.objects.filter(event=self.e,action='grant').count(),3)
    def test_removed_roles_rejected_and_staff_not_total_admin(self):
        self.assertEqual(self.post(self.root,'grant',username=self.plain.username,role='recorder',reason='测试').status_code,400)
        self.child.is_staff=True;self.child.save();self.client.force_login(self.child)
        self.assertEqual(self.client.post('/api/events/',json.dumps(dict(name='测试',kind='team')),content_type='application/json').status_code,403)
    def test_root_creates_unprivileged_account(self):
        self.client.force_login(self.root)
        response=self.client.post('/api/accounts/',json.dumps(dict(username='new-ordinary',password='Temp-Account-7zB9-2026',is_superuser=True)),content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        u=get_user_model().objects.get(username='new-ordinary');self.assertFalse(u.is_staff);self.assertFalse(u.is_superuser)
        self.assertFalse(Event.objects.filter(editors=u).exists())


class AccountTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('account-test',password='Old-Password-7k2M-2026')
    def payload(self,**kwargs):
        return dict(old_password='Old-Password-7k2M-2026',new_password1='New-Password-8j3P-2026',new_password2='New-Password-8j3P-2026',**kwargs)
    def test_password_change_keeps_current_session_revokes_other(self):
        other=Client();self.client.force_login(self.user);other.force_login(self.user)
        r=self.client.post('/account/',self.payload());self.assertEqual(r.status_code,302)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('New-Password-8j3P-2026'))
        self.assertEqual(self.client.get('/account/').status_code,200)
        self.assertEqual(other.get('/account/').status_code,302)
        self.assertFalse(self.user.is_staff);self.assertFalse(self.user.is_superuser)
    def test_invalid_password_does_not_change_account(self):
        self.client.force_login(self.user)
        for changes in [{'old_password':'wrong'},{'new_password2':'mismatch'},{'new_password1':'short','new_password2':'short'}]:
            data=self.payload();data.update(changes);r=self.client.post('/account/',data)
            self.assertEqual(r.status_code,200);self.assertTrue(r.context['password_form'].errors)
            self.assertNotIn('value="'+data['new_password1']+'"',r.content.decode())
            self.user.refresh_from_db();self.assertTrue(self.user.check_password('Old-Password-7k2M-2026'))
    def test_normal_account_entry_and_csrf(self):
        self.assertEqual(self.client.get('/account/').status_code,302)
        self.client.force_login(self.user);r=self.client.get('/account/')
        self.assertContains(r,'普通账号');self.assertNotContains(r,'进入管理端')
        self.assertEqual(r['Cache-Control'],'no-store')
        secured=Client(enforce_csrf_checks=True);secured.force_login(self.user)
        self.assertEqual(secured.post('/account/',self.payload()).status_code,403)
    def test_account_lists_only_authorized_events(self):
        e=Event.objects.create(name='可管理赛事',kind='team',document=fixture());e.editors.add(self.user)
        Event.objects.create(name='不得泄露赛事',kind='team',document=fixture())
        self.client.force_login(self.user);r=self.client.get('/account/')
        self.assertContains(r,'子赛事管理员');self.assertContains(r,'可管理赛事');self.assertNotContains(r,'不得泄露赛事')
    def test_public_page_login_entry(self):
        self.assertContains(self.client.get('/'),'登录')
        self.client.force_login(self.user);self.assertContains(self.client.get('/'),'我的账号')


class DefaultPasswordTests(TestCase):
    def test_new_ordinary_account_default_without_changing_root(self):
        root=get_user_model().objects.create_superuser('default-test-root',password='root-test-secret-2026')
        self.client.force_login(root)
        r=self.client.post('/api/accounts/',json.dumps({'username':'default-password-test'}),content_type='application/json')
        self.assertEqual(r.status_code,201,r.content)
        u=get_user_model().objects.get(username='default-password-test')
        self.assertTrue(u.check_password('1234@qwer'));self.assertFalse(u.is_superuser);self.assertFalse(u.is_staff)
        root.refresh_from_db();self.assertTrue(root.check_password('root-test-secret-2026'))
    def test_custom_initial_password_still_validated(self):
        root=get_user_model().objects.create_superuser('custom-test-root',password='root-test-secret-2026')
        self.client.force_login(root)
        r=self.client.post('/api/accounts/',json.dumps({'username':'weak-test','password':'bad'}),content_type='application/json')
        self.assertEqual(r.status_code,400)
