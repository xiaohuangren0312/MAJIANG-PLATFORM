from .domain import optional_note
"""Corrections overlay an immutable source; historical carry is never inferred."""
import copy
from .domain import require,label,integer,find,score

def effective(document):
    return document.get('historyCurrent',document['historySnapshot'])

def totals(payload,stage,kind,entity_id):
    key='teamPoints' if kind=='team' else 'points'
    pairs=[(m,s) for m in sorted(payload['results'],key=lambda m:(m.get('date',''),m.get('number',0))) if stage=='all' or m['stageId']==stage for s in m['seats'] if s.get(kind+'Id')==entity_id]
    seats=[s for _,s in pairs];known=[s[key] for s in seats if s.get(key) is not None]
    places=[0.0]*4
    for m,s in pairs:
        rank=s.get('rank')
        if rank is None:continue
        tied=sum(1 for t in m['seats'] if t.get('rank')==rank) if s.get('tied') else 1
        if not 1<=rank<=4 or rank+tied>5:continue
        for i in range(rank-1,rank-1+tied):places[i]+=1/tied
    ranked=sum(places);scores=[s['score'] for s in seats if s.get('score') is not None]
    bases=[s['base'] for s in seats if s.get('base') is not None]
    return dict(contribution=sum(known),games=len(seats),rankedGames=ranked,places=places,avgRank=sum((i+1)*v for i,v in enumerate(places))/ranked if ranked else None,topRate=places[0]/ranked if ranked else None,topTwo=sum(places[:2])/ranked if ranked else None,avoidLast=1-places[3]/ranked if ranked else None,best=max(scores,default=None),avgPoints=sum(scores)/len(scores) if scores else None,history=known,last=known[-1] if known else 0,base=sum(bases) if len(bases)==len(seats) else None)

def preview(document,body):
    require(bool(document.get('historySnapshot')),'此操作仅支持导入历史赛事')
    reason=optional_note(body.get('reason'));old=effective(document);new=copy.deepcopy(old)
    match=find(new['results'],body.get('id'));original=find(old['results'],body.get('id'))
    incoming=body.get('seats');require(isinstance(incoming,list) and len(incoming)==len(match['seats'])==4,'必须保留四个座次')
    mode=body.get('scoreMode','keep-pt');require(mode in ['keep-pt','recalculate'],'点棒处理模式错误')
    player_ids=[];team_ids=[]
    for s,b,previous_seat in zip(match['seats'],incoming,original['seats']):
        require(isinstance(b,dict),'座次格式错误')
        for field,collection in [('playerId','players'),('teamId','teams')]:
            value=b.get(field)
            require(value is None or isinstance(value,str),'归属格式错误')
            if value:find(new[collection],value)
            # Unknown is allowed; mappings are match-specific and do not transfer the roster.
            s[field]=value or None
        if s['playerId']:player_ids.append(s['playerId'])
        if s['teamId']:team_ids.append(s['teamId'])
        for field in ['points','teamPoints']:
            value=b.get(field)
            if value is not None:integer(value,'积分（0.1PT）',-10000000,10000000)
            require(value is not None or s.get(field) is None,'已有积分不能清空；如需归零请填写0')
            s[field]=value
        if s.get('points')!=previous_seat.get('points'):s['penalty']=None
        if 'score' in b:
            value=b['score']
            if value is not None:
                integer(value,'终局点数',-10000000,10000000);require(value%100==0,'点棒必须为100点的整数倍')
            require(value is not None or previous_seat.get('score') is None,'已有点棒不能清空')
            s['score']=value
    require(len(player_ids)==len(set(player_ids)),'同一选手不能重复出场')
    require(len(team_ids)==len(set(team_ids)),'同一队伍不能重复出场')
    rule=find(document['rules'],body.get('ruleId') or document['rules'][-1]['id']);scoring_notice='保留输入的历史PT，不自动重算积分。'
    scores=[s.get('score') for s in match['seats']]
    score_changed=any(s.get('score')!=o.get('score') for s,o in zip(match['seats'],original['seats']))
    complete=all(v is not None for v in scores)
    if score_changed and not complete:
        require(not any(s.get('rank') is not None for s in original['seats']),'本场已有顺位，请补齐四人点棒后更正')
        scoring_notice+=' 点棒尚未补齐，顺位继续保留未知。'
    if (score_changed and complete) or mode=='recalculate':
        require(complete,'重算积分需要四人完整点棒')
        ordered=sorted(scores,reverse=True)
        for seat in match['seats']:
            seat['rank']=ordered.index(seat['score'])+1;seat['tied']=ordered.count(seat['score'])>1
        if mode=='recalculate':
            require(body.get('confirmNoPenalties') is True,'请确认本次按无罚分重算')
            require(not match.get('penalties') and all(s.get('penalty') in [None,0] for s in original['seats']),'原表存在罚分，当前请保留历史PT并单独核对')
            for seat,calculated in zip(match['seats'],score(rule,scores)):seat.update(calculated)
            match['correctionRule']=copy.deepcopy(rule)
            match['ruleName']=rule['name'];match['ruleVersion']=rule['version']
            scoring_notice='按 v'+str(rule['version'])+' '+rule['name']+'（起始点 '+str(rule['start'])+' / 返点 '+str(rule['return'])+'）重算基础积分，本次已明确按无罚分处理。'
        else:
            scoring_notice+=' 顺位按四人点棒自动确定，同点平分顺位统计。'
            if sum(scores)!=rule['start']*4:scoring_notice+=' 四人点棒总和与当前规则不一致，历史PT未改动，请核对当时规则或供托。'
    require(match['seats']!=original['seats'] or match.get('correctionRule')!=original.get('correctionRule'),'没有需要保存的变更')
    # An achievement or explicit penalty belongs to its original player; mapping changes must not orphan it.
    referenced={x.get('playerId') for k in ['penalties','yakuman'] for x in match.get(k,[])}
    require(not (referenced-set(player_ids)-{None}),'本场有该选手的罚分或役满记录，不能直接替换其身份')
    changes=[]
    for stage in ['all',match['stageId']]:
        for kind,collection in [('player','players'),('team','teams')]:
            ids={s.get(kind+'Id') for s in original['seats']+match['seats']}-{None}
            for entity_id in sorted(ids):
                before=totals(old,stage,kind,entity_id);after=totals(new,stage,kind,entity_id)
                if before==after:continue
                delta=after.pop('contribution')-before['contribution']
                for metric in ['raw','competitive']:
                    rows=new.setdefault('statistics',{}).setdefault(stage,{}).setdefault(metric,{}).setdefault(kind,[])
                    row=next((x for x in rows if x['id']==entity_id),None)
                    if row is None:
                        entity=find(new[collection],entity_id)
                        row=dict(id=entity_id,name=entity['name'],total=0,raw=0,carry=0,yakuman=None,rank=0);rows.append(row)
                    previous=row.get('total',0);row['total']=previous+delta;row['raw']=row.get('raw',0)+delta
                    row.update(after);row['penalty']=None # Historical PT adjustments are not invented penalty events.
                    changes.append(dict(stage=stage,metric=metric,kind=kind,id=entity_id,name=row['name'],before=previous,after=row['total'],delta=delta,beforeAvgRank=before['avgRank'],afterAvgRank=after['avgRank'],beforeBest=before['best'],afterBest=after['best']))
                for metric in ['raw','competitive']:
                    rows=new.setdefault('statistics',{}).setdefault(stage,{}).setdefault(metric,{}).setdefault(kind,[])
                    rows.sort(key=lambda x:-x['total'])
                    for i,row in enumerate(rows):row['rank']=rows[i-1]['rank'] if i and rows[i-1]['total']==row['total'] else i+1
    for scheduled in new.get('schedule',[]):
        if scheduled.get('resultId')==match['id'] or scheduled.get('id')==match['id']:
            scheduled['players']=[dict(playerId=s.get('playerId'),teamId=s.get('teamId')) for s in match['seats']]
    message='历史更正已计入个人榜、队伍榜的逐场累计；原表积分快照、比赛日原表合计及后续阶段带入分保留不变。'
    new['correctionNotice']=message
    return dict(id=match['id'],reason=reason,seats=copy.deepcopy(match['seats']),before=copy.deepcopy(original['seats']),changes=changes,notice=message,scoringNotice=scoring_notice,rule=copy.deepcopy(rule)),new

def commit(document,body):
    p,current=preview(document,body);d=copy.deepcopy(document)
    d['historyCurrent']=current
    d.setdefault('historyCorrections',[]).append(dict(id=p['id'],reason=p['reason'],changes=p['changes'],rule=p['rule'] if body.get('scoreMode')=='recalculate' else None))
    return d
