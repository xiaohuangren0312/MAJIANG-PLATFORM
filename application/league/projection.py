from .domain import optional_note
import copy
from fractions import Fraction
from .domain import require,find,integer,label,eligible_ids,uid

def statistics(d,stage='all',competitive=False,kind='player'):
    matches=sorted([m for m in d['matches'] if m['state']=='published' and (stage=='all' or m['stageId']==stage)],key=lambda m:(m['date'],m['time'],m['number']))
    rows=[]
    incoming=next((c for c in d['settlements'] if c['target']==stage),None)
    for e in d['players' if kind=='player' else 'teams']:
        if incoming:
            qualifier=e['id'] if incoming['kind']==kind else (e.get('bondStages',{}).get(stage) if e.get('bond') else e.get('teamId'))
            if qualifier not in incoming['rows']:continue
        pairs=[(m,s) for m in matches for s in m['seats'] if s[kind+'Id']==e['id']]
        seats=[s for _,s in pairs];n=len(seats);places=[0.0]*4
        for m,s in pairs:
            tied=sum(x['score']==s['score'] for x in m['seats'])
            places[s['rank']-1]+=1
        key='teamPoints' if kind=='team' else 'points'
        total=sum(s[key] for s in seats);base=sum(s['base'] for s in seats)
        carry=sum(c['rows'].get(e['id'],0) for c in d['settlements'] if c['target']==stage and c['kind']==kind) if competitive and stage!='all' else 0
        yakuman=sum(1 for m in matches for y in m['yakuman'] if any(s['playerId']==y['playerId'] and s[kind+'Id']==e['id'] for s in m['seats']))
        rows.append(dict(id=e['id'],name=e['name'],bond=e.get('bond',False),base=base,penalty=base-total,carry=carry,raw=total,total=total+carry,games=n,rank=0,places=places,avgRank=sum((i+1)*v for i,v in enumerate(places))/n if n else None,topRate=places[0]/n if n else None,topTwo=sum(places[:2])/n if n else None,avoidLast=1-places[3]/n if n else None,best=max((s['score'] for s in seats),default=None),avgPoints=sum(s['score'] for s in seats)/n if n else None,yakuman=yakuman,last=seats[-1][key] if seats else 0,history=[s[key] for s in seats]))
    rows.sort(key=lambda r:-r['total'])
    for i,r in enumerate(rows):r['rank']=rows[i-1]['rank'] if i and rows[i-1]['total']==r['total'] else i+1
    return rows

def _public_event(event):
    if event.document.get('archive'):return copy.deepcopy(event.document['archive']['publicPayload'])
    if event.document.get('historySnapshot'):
        payload=copy.deepcopy(event.document.get('historyCurrent',event.document['historySnapshot']));payload['name']=event.name
        return rank_metrics(payload)
    d=event.document;results=[];schedule=[]
    for m in sorted(d['matches'],key=lambda m:(m['date'],m['time'],m['number'])):
        published=m['state']=='published'
        schedule.append(dict(id=m['id'],stageId=m['stageId'],date=m['date'],time=m['time'],table=m['table'],number=m['number'],pairingRound=m.get('pairingRound'),lineupPublished=m['lineupPublished'],players=[dict(playerId=s['playerId'] if m['lineupPublished'] or published else None,teamId=s['teamId']) for s in m['seats']],state='completed' if published else 'cancelled' if m['state']=='cancelled' else 'scheduled',resultId=m['id'] if published else None))
        if published:
            results.append(dict(id=m['id'],stageId=m['stageId'],date=m['date'],time=m['time'],pairingRound=m.get('pairingRound'),table=m['table'],number=m['number'],ruleName=m['rule']['name'],ruleVersion=m['rule']['version'],seats=copy.deepcopy(m['seats']),penalties=copy.deepcopy(m['penalties']),yakuman=copy.deepcopy(m['yakuman'])))
    stats={stage:{metric:{kind:statistics(d,stage,metric=='competitive',kind) for kind in ['player','team']} for metric in ['raw','competitive']} for stage in ['all']+[s['id'] for s in d['stages']]}
    return dict(id=str(event.id),name=event.name,type=event.kind,season=d['season'],venue=d['venue'],currentStage=d['stages'][-1]['id'] if d['stages'] else 'all',stages=[dict(id=s['id'],name=s['name'],advanceCount=s.get('advanceCount',0)) for s in d['stages']],teams=[{**{k:t[k] for k in ['id','name','color']},'imageUrl':t.get('imageUrl')} for t in d['teams']],players=[{**{k:p[k] for k in ['id','name','teamId','bio']},'imageUrl':p.get('imageUrl'),'bond':p.get('bond',False),'bondStages':p.get('bondStages',{})} for p in d['players']],results=results,schedule=schedule,statistics=stats,rules={'name':d['rules'][-1]['name']})

def settlement_preview(d,kind,b):
    require(not d.get('archive'),'赛事已归档')
    source=find(d['stages'],b.get('source'))
    if b.get('targetName'):
        require(d['stages'][-1]['id']==source['id'],'已有后续阶段，请先处理该阶段')
        name=label(b['targetName']);require(not any(x['name']==name for x in d['stages']),'阶段名称重复')
        target=dict(id=uid(),name=name,locked=False,advanceCount=integer(b.get('nextAdvanceCount',0),'下一阶段晋级名次',0,10000))
        virtual=copy.deepcopy(d);virtual['stages'].append(target)
        args=dict(b,target=target['id']);args.pop('targetName')
        p=settlement_preview(virtual,kind,args);p['createdStage']=target
        return p
    target=find(d['stages'],b.get('target'))
    require(d['stages'].index(target)==d['stages'].index(source)+1,'请选择紧邻的下一阶段')
    require(not source['locked'] and not target['locked'],'阶段已锁定')
    require(not any(m['state']=='draft' for m in d['matches'] if m['stageId']==source['id']),'源阶段还有未发布或未取消的对局')
    require(any(m['state']=='published' for m in d['matches'] if m['stageId']==source['id']),'源阶段没有已发布战果')
    require(not any(m['state']=='published' for m in d['matches'] if m['stageId']==target['id']),'目标阶段已产生战果')
    require(not any(c['target']==target['id'] for c in d['settlements']),'目标阶段已有带入记录')
    numerator=integer(b.get('numerator',1),'比例分子',0,1000);denominator=integer(b.get('denominator',2),'比例分母',1,1000)
    entity_kind='team' if kind=='team' else 'player'
    eligible=eligible_ids(d,kind,source['id'])
    candidates=[r for r in statistics(d,source['id'],True,entity_kind) if r['id'] in eligible]
    count=source.get('advanceCount',0)
    ids=[r['id'] for r in candidates if r['rank']<=count and r['games']>0] if count else b.get('ids');require(isinstance(ids,list) and len(ids)>0 and len(ids)==len(set(ids)),'请选择不重复的晋级对象')
    require(len(ids)>=4,'下一阶段至少需要四个晋级对象')
    key='teamId' if kind=='team' else 'playerId'
    require(all(s.get(key) in ids for m in d['matches'] if m['stageId']==target['id'] and m['state']!='cancelled' for s in m['seats']),'目标阶段已有未晋级对象的赛程，请先取消')
    rows=[]
    for id in ids:
        r=find(candidates,id);require(r['games']>0,'不能结转无成绩对象')
        value=Fraction(r['total']*numerator,denominator)
        mode=b.get('roundingMode','ceil');require(mode in ['ceil','nearest','floor'],'取整方式错误')
        rounded= -(-value.numerator//value.denominator) if mode=='ceil' else value.numerator//value.denominator if mode=='floor' else (1 if value>=0 else -1)*((abs(value.numerator)*2+value.denominator)//(2*value.denominator))
        rows.append(dict(id=id,name=r['name'],source=r['total'],exact=str(value),suggested=rounded))
    return dict(source=source['id'],target=target['id'],kind=entity_kind,numerator=numerator,denominator=denominator,roundingMode=mode,rounding={'ceil':'向上取整到0.1PT（负数趋向正无穷）','nearest':'四舍五入到0.1PT，中点远离零','floor':'向下取整到0.1PT'}[mode],rows=rows)

def settle(d,preview,overrides):
    require(not d.get('archive'),'赛事已归档')
    d=copy.deepcopy(d); rows={};reasons={}
    if preview.get('createdStage'):d['stages'].append(copy.deepcopy(preview['createdStage']))
    require(isinstance(overrides,dict),'覆盖值格式错误')
    require(set(overrides)<=set(r['id'] for r in preview['rows']),'覆盖对象不属于预览')
    for r in preview['rows']:
        if r['id'] in overrides:
            o=overrides[r['id']];rows[r['id']]=integer(o.get('value'),'带入积分',-10000000,10000000);reasons[r['id']]=optional_note(o.get('reason'))
        else: rows[r['id']]=r['suggested']
    d['settlements'].append(dict(source=preview['source'],target=preview['target'],kind=preview['kind'],rows=rows,reasons=reasons,preview=preview))
    find(d['stages'],preview['source'])['locked']=True
    return d


def rank_metrics(payload):
    """Recompute only rank metrics; preserve historical PT and source snapshots."""
    from .history_correction import totals
    payload=copy.deepcopy(payload)
    from .history_bonds import mark
    payload=mark(payload)
    for collection in ['results','schedule']:
        for m in payload.get(collection,[]):
            if payload.get('id') in ['s2','s3'] and m.get('stageId') in ['semi','final']:
                m['time']='19:30' if m.get('number',1)%2 else '21:00'
    for stage,metrics in payload.get('statistics',{}).items():
        cache={}
        for kinds in metrics.values():
            for kind,rows in kinds.items():
                for row in rows:
                    key=(kind,row['id'])
                    if key not in cache:cache[key]=totals(payload,stage,kind,row['id'])
                    t=cache[key]
                    for field in ['places','rankedGames','avgRank','topRate','topTwo','avoidLast']:row[field]=t[field]
    return payload


def public_event(event):
    from .match_resources import project
    return project(_public_event(event),event.document)
