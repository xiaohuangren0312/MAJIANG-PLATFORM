"""One-half-game high-high pairing; integer-tenth ranking and signed previews."""
import copy,datetime,re,secrets
from .domain import require,integer,label,eligible_ids,live_stage,apply,uid
from .projection import statistics

def number_key(value):
    raw=str(value).strip()
    return (tuple((0,int(x)) if x.isdigit() else (1,x.casefold()) for x in re.split(r'(\d+)',raw) if x),raw.casefold(),raw)

def context(d,kind,b):
    require(kind=='personal','高高碰自动排程仅支持个人赛')
    require(not d.get('historySnapshot'),'历史导入赛事不生成新赛程')
    require(not d.get('archive'),'赛事已归档')
    stage=live_stage(d,b.get('stageId'));eligible=eligible_ids(d,kind,stage['id'])
    players=[p for p in d['players'] if p['active'] and not p.get('nonPlayingCoach') and p['id'] in eligible]
    require(len(players)>=4 and len(players)%4==0,'参赛人数必须至少4人且为4的倍数，请先处理名单；不会自动补人或轮空')
    require(not any(m['state']=='draft' and m['stageId']==stage['id'] for m in d['matches']),'本阶段还有未发布或未取消的对局，请先完成上一轮所有桌')
    day=b.get('date');time=b.get('time')
    try:
        datetime.date.fromisoformat(day)
        require(isinstance(time,str) and re.fullmatch(r'\d{2}:\d{2}',time) is not None,'时间格式应为HH:MM')
        datetime.time.fromisoformat(time)
    except (ValueError,TypeError):require(False,'请填写有效比赛日期和时间')
    start=integer(b.get('startTable',1),'起始桌号',1,1000)
    require(start+len(players)//4-1<=1000,'生成桌号超出范围')
    published=[m for m in d['matches'] if m['state']=='published']
    require(not published or (day,time)>max((m['date'],m['time']) for m in published),'下一轮开赛时间必须晚于已有已发布对局')
    rows={r['id']:r for r in statistics(d,stage['id'],True,'player')}
    counts={rows[p['id']]['games'] for p in players}
    require(len(counts)==1,'本阶段参赛选手已赛场次不一致，请先补齐对局或核对参赛名单')
    first=not published
    players.sort(key=lambda p:((0 if first else -rows[p['id']]['total']),number_key(p['number']),p['id']))
    ranking=[dict(id=p['id'],name=p['name'],number=p['number'],points=rows[p['id']]['total'],games=rows[p['id']]['games'],order=i+1) for i,p in enumerate(players)]
    commentators=b.get('commentators',[]);require(isinstance(commentators,list) and len(commentators)<=10,'最多10位解说员')
    commentators=[label(x) for x in commentators]
    return dict(commentators=commentators,stageId=stage['id'],stageName=stage['name'],date=day,time=time,startTable=start,round=next(iter(counts))+1,method='number' if first else 'high-high',ranking=ranking,rule=copy.deepcopy(d['rules'][-1]))

def preview(d,kind,b):
    p=context(d,kind,b);tables=[]
    for i in range(0,len(p['ranking']),4):
        seats=[r['id'] for r in p['ranking'][i:i+4]];secrets.SystemRandom().shuffle(seats)
        tables.append(dict(number=p['startTable']+i//4,players=seats))
    p['tables']=tables
    return p

def commit(d,kind,p,tables=None,reason=''):
    fresh=context(d,kind,p)
    require(all(fresh[k]==p[k] for k in fresh),'排程依据已变化，请重新预览')
    selected=copy.deepcopy(p['tables'] if tables is None else tables)
    require(isinstance(selected,list) and len(selected)==len(p['tables']),'桌数与预览不一致')
    seen=[]
    for suggested,row in zip(p['tables'],selected):
        require(isinstance(row,dict) and type(row.get('number')) is int and row['number']==suggested['number'],'桌号与预览不一致')
        seats=row.get('players');require(isinstance(seats,list) and len(seats)==4 and all(isinstance(x,str) for x in seats),'每桌必须为四名选手')
        seen.extend(seats)
    require(len(seen)==len(set(seen)) and set(seen)=={r['id'] for r in p['ranking']},'每名参赛选手必须且只能出现一次，不可增删或替换参赛名单')
    changed=selected!=p['tables']
    reason=str(reason or "").strip()[:120]
    result=copy.deepcopy(d);round_id=uid();match_ids=[]
    for row in selected:
        result=apply(result,kind,'match',dict(stageId=p['stageId'],date=p['date'],time=p['time'],number=row['number'],commentators=p.get('commentators',[]),seats=[dict(playerId=x,teamId=None) for x in row['players']]))
        m=result['matches'][-1];m.update(lineupPublished=True,pairingRoundId=round_id,pairingRound=p['round'])
        match_ids.append(m['id'])
    result.setdefault('pairingRounds',[]).append(dict(id=round_id,stageId=p['stageId'],round=p['round'],basis=copy.deepcopy(p),tables=selected,manualAdjustment=changed,reason=reason if changed else '',matchIds=match_ids))
    return result
