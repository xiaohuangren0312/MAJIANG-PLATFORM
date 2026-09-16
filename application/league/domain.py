"""Event commands. PT are signed integer tenths; no client-computed totals."""
import copy, uuid, datetime, re
from fractions import Fraction

class Invalid(ValueError): pass
def require(ok,message):
    if not ok: raise Invalid(message)
def uid(): return uuid.uuid4().hex
def integer(v,label,low=None,high=None):
    require(type(v) is int,f'{label}必须是整数')
    require((low is None or v>=low) and (high is None or v<=high),f'{label}超出范围')
    return v
def label(v):
    require(isinstance(v,str) and 0<len(v.strip())<=120,'名称必填，最多120字')
    return v.strip()
def find(items,id):
    row=next((x for x in items if x['id']==id),None)
    require(row is not None,'对象不存在或不属于当前赛事')
    return row
def initial():
    return {'season':'','venue':'欢雀楼','teams':[],'players':[],'stages':[], 'matches':[], 'settlements':[], 'rules':[{'id':uid(),'version':1,'name':'M.LEAGUE 默认计分','start':25000,'return':30000,'bonuses':[500,100,-100,-300]}]}
def score(rule,values):
    require(len(values)==4,'必须录入四人成绩')
    for n in values: integer(n,'终局点数',-10000000,10000000)
    require(sum(values)==rule['start']*4,f"当前总分 {sum(values):,}，应为 {rule['start']*4:,}（简写 {rule['start']*4//100:,}），差额 {rule['start']*4-sum(values):+,}；请检查输入或未结供托")
    require(all(n%100==0 for n in values),'终局点数必须为100点的整数倍')
    ordered=sorted(values,reverse=True); result=[]
    for i,n in enumerate(values):
        positions=[k for k,v in enumerate(ordered) if v==n]
        # Split integer tenths exactly; positive remainder follows east-first.
        pool=sum(rule['bonuses'][k] for k in positions)
        bonus,rem=divmod(pool,len(positions))
        tie_index=[j for j,v in enumerate(values) if v==n].index(i)
        base=(n-rule['return'])//100+bonus+(tie_index<rem)
        result.append(dict(score=n,rank=min(positions)+1,tied=len(positions)>1,base=base,penalty=0,points=base,teamPoints=base))
    return result
def eligible_ids(d,kind,stage_id):
    stage=find(d['stages'],stage_id)
    if d['stages'].index(stage)==0:return {x['id'] for x in d['teams' if kind=='team' else 'players']}
    incoming=next((c for c in d['settlements'] if c['target']==stage_id),None)
    require(incoming is not None,'请先结算上一阶段并确认晋级名单')
    return set(incoming['rows'])

def validate_qualification(d,kind,stage_id,seats):
    require(isinstance(seats,list) and len(seats)==4 and all(isinstance(s,dict) for s in seats),'每场必须有四个座次')
    eligible=eligible_ids(d,kind,stage_id);key='teamId' if kind=='team' else 'playerId'
    require(all(s.get(key) in eligible for s in seats),'存在未晋级当前阶段的队伍或选手')

def live_stage(d,id):
    stage=find(d['stages'],id);require(not stage.get('locked'),'阶段已结算锁定');return stage
def validate_lineup(d,kind,seats,complete,historical=False,stage_id=None):
    require(isinstance(seats,list) and len(seats)==4,'每场必须有四个座次')
    player_ids=[];team_ids=[];out=[]
    for seat in seats:
        pid=seat.get('playerId');tid=seat.get('teamId')
        if kind=='team':
            team=find(d['teams'],tid); require(historical or team['active'],'队伍已停用');team_ids.append(tid)
        else: require(not tid,'个人赛不能设置队伍')
        if pid:
            p=find(d['players'],pid);require(historical or p['active'],'选手已停用')
            require(historical or kind!='team' or (p.get('bondStages',{}).get(stage_id) if p.get('bond') else p['teamId'])==tid,'选手不属于所选队伍')
            player_ids.append(pid)
        else: require(not complete,'请补齐四名出战选手')
        out.append(dict(playerId=pid or None,teamId=tid or None,**({'bond':True} if pid and p.get('bond') else {})))
    require(len(set(player_ids))==len(player_ids),'同一选手不能重复出场')
    require(kind!='team' or len(set(team_ids))==4,'团体赛每桌需要四支不同队伍')
    return out
def result(d,kind,m,body):
    validate_qualification(d,kind,m['stageId'],m['seats'])
    seats=validate_lineup(d,kind,m['seats'],True,historical=m['state']=='published',stage_id=m['stageId'])
    values=body.get('scores',[])
    if isinstance(values,list) and len(values)==4 and all(type(v) is int for v in values) and sum(values)==m['rule']['start']*4//100:
        values=[v*100 for v in values]
    calculated=score(m['rule'],values)
    for s,c in zip(seats,calculated): s.update(c)
    penalties=body.get('penalties',[]);yakuman=body.get('yakuman',[])
    require(isinstance(penalties,list) and isinstance(yakuman,list),'事件格式不正确')
    require(len(penalties)<=100 and len(yakuman)<=100,'单场每类事件最多100条')
    clean=[]
    for p in penalties:
        require(isinstance(p,dict),'罚分记录格式错误')
        who=next((s for s in seats if s['playerId']==p.get('playerId')),None)
        require(who is not None,'处罚对象必须为本场选手')
        amount=integer(p.get('amount'),'罚分（0.1PT）',1,100000)
        scope=p.get('scope');require(scope in ['personal','team','both'],'处罚范围错误')
        require(kind=='team' or scope=='personal','个人赛仅支持个人罚分')
        reason=optional_note(p.get('explanation'))
        if scope in ['personal','both']: who['penalty']+=amount;who['points']-=amount
        if scope in ['team','both']: who['teamPoints']-=amount
        clean.append(dict(playerId=who['playerId'],amount=amount,scope=scope,explanation=reason))
    achievements=[]
    for y in yakuman:
        require(isinstance(y,dict),'役满记录格式错误')
        require(y.get('method') in ['自摸','荣和'],'和牌方式必须为自摸或荣和')
        require(y.get('playerId') in [s['playerId'] for s in seats],'役满选手不在本场')
        require(isinstance(y.get('types'),list) and 1<=len(y['types'])<=10,'请填写役满役种')
        achievements.append(dict(playerId=y['playerId'],types=[label(n) for n in y['types']],multiplier=integer(y.get('multiplier',1),'役满倍数',1,10),round=label(y.get('round')),method=label(y.get('method'))))
    return dict(seats=seats,penalties=clean,yakuman=achievements)
def apply(d,kind,action,b):
    require(not d.get('archive'),'赛事已归档，比赛数据不可修改')
    d=copy.deepcopy(d)
    if action=='save-result':
        m=find(d['matches'],b.get('id'))
        if m['state']=='published':return apply(d,kind,'correct',b)
        d=apply(d,kind,'score',b)
        return apply(d,kind,'publish',{'id':m['id']})
    if action in ['team-update','player-update']:
        from .roster import update_roster
        return update_roster(d,kind,action,b)
    elif action=='bond-player':
        require(kind=='team','羁绊选手仅适用于团队赛')
        stage=live_stage(d,b.get('stageId'));team=find(d['teams'],b.get('teamId'))
        require(team['active'] and team['id'] in eligible_ids(d,kind,stage['id']),'队伍未获得本阶段参赛资格')
        if b.get('id'):
            p=find(d['players'],b['id']);require(p.get('bond'),'请选择羁绊选手')
            require(stage['id'] not in p.get('bondStages',{}),'该选手已报名此阶段；不能改写已登记的代表队伍')
        else:
            d=apply(d,kind,'player',dict(name=b.get('name')));p=d['players'][-1];p['bond']=True
        p.setdefault('bondStages',{})[stage['id']]=team['id']
    elif action=='team':
        require(kind=='team','个人赛不设置队伍')
        name=label(b.get('name'));require(not any(x['name']==name for x in d['teams']),'队伍名称重复')
        from .roster import next_color
        d['teams'].append(dict(id=uid(),name=name,color=next_color(d['teams']),active=True))
    elif action=='player':
        tid=b.get('teamId') or None
        if tid: require(kind=='team','个人赛不设置队伍');find(d['teams'],tid)
        from .roster import next_number
        number=label(b.get('number') or next_number(d['players']));require(not any(x['number']==number for x in d['players']),'报名编号重复')
        d['players'].append(dict(id=uid(),name=label(b.get('name')),number=number,teamId=tid,active=True,bio=''))
    elif action=='stage-update':
        stage=live_stage(d,b.get('id'));name=label(b.get('name',stage['name']))
        require(not any(x['id']!=stage['id'] and x['name']==name for x in d['stages']),'阶段名称重复')
        stage.update(name=name,advanceCount=integer(b.get('advanceCount',stage.get('advanceCount',0)),'晋级名次',0,10000))
    elif action=='stage':
        d['stages'].append(dict(id=uid(),name=label(b.get('name')),locked=False))
    elif action=='rule':
        start=integer(b.get('start'),'起始点',100,1000000);ret=integer(b.get('return'),'返点',100,1000000)
        require(start%100==ret%100==0,'点数必须为100的倍数')
        bonuses=b.get('bonuses');require(isinstance(bonuses,list) and len(bonuses)==4,'需要四个最终顺位分')
        for n in bonuses: integer(n,'顺位分（0.1PT）',-100000,100000)
        d['rules'].append(dict(id=uid(),version=len(d['rules'])+1,name=label(b.get('name')),start=start,return_=ret,bonuses=bonuses))
        d['rules'][-1]['return']=d['rules'][-1].pop('return_')
    elif action=='match':
        stage=live_stage(d,b.get('stageId'));day=b.get('date')
        validate_qualification(d,kind,stage['id'],b.get('seats') or [])
        require(len(b.get('seats') or [])==4,'每场必须有四个座次')
        try: datetime.date.fromisoformat(day)
        except (TypeError,ValueError): raise Invalid('比赛日期格式错误')
        time=b.get('time','19:30')
        require(isinstance(time,str) and re.fullmatch(r'\d{2}:\d{2}',time) is not None,'时间格式应为HH:MM')
        try: datetime.time.fromisoformat(time)
        except ValueError: raise Invalid('比赛时间无效')
        number=integer(b.get('number'),'桌号',1,1000)
        require(not any(m['date']==day and m['time']==time and m['number']==number and m['state']!='cancelled' for m in d['matches']),'同一开赛时间桌号重复')
        d['matches'].append(dict(id=uid(),stageId=stage['id'],date=day,time=time,number=number,table=str(number),seats=validate_lineup(d,kind,b.get('seats'),False,stage_id=stage['id']),rule=copy.deepcopy(d['rules'][-1]),state='draft',lineupPublished=False,penalties=[],yakuman=[]))
        if b.get('commentators'):
            from .match_resources import update
            d=update(d,dict(id=d['matches'][-1]['id'],commentators=b['commentators']))
    elif action in ['lineup','score','publish','correct','cancel']:
        m=find(d['matches'],b.get('id'));live_stage(d,m['stageId'])
        if action=='correct':
            require(m['state']=='published','只能更正已发布战果');optional_note(b.get('reason'))
            m.update(result(d,kind,m,b));m['correctionReason']=optional_note(b.get('reason'))
        else:
            require(m['state']=='draft','已发布或取消的记录不可直接修改')
            if action=='lineup':
                seats=validate_lineup(d,kind,b.get('seats'),True,stage_id=m['stageId'])
                validate_qualification(d,kind,m['stageId'],seats)
                require(not m['penalties'] and not m['yakuman'],'请先处理原有罚分和役满事件')
                m.update(seats=seats,lineupPublished=True)
            elif action=='score': m.update(result(d,kind,m,b))
            elif action=='publish':
                require(all('score' in s for s in m['seats']),'请先保存成绩')
                # Revalidate the server-saved result before publication.
                m.update(result(d,kind,m,dict(scores=[s['score'] for s in m['seats']],penalties=m['penalties'],yakuman=m['yakuman'])))
                m.update(state='published',lineupPublished=True)
            else: optional_note(b.get('reason'));m['state']='cancelled'
    else: raise Invalid('不支持的操作')
    return d


def optional_note(value):
    if value is None or (isinstance(value,str) and not value.strip()): return ""
    return label(value)
