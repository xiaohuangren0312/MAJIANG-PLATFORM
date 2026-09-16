"""Two-row spreadsheet paste with exact no-penalty PT inversion."""
import copy,itertools,csv,io
from decimal import Decimal,InvalidOperation
from .domain import require,find,score,apply,Invalid

def inverse(rule,points):
    found=[]
    for groups in itertools.product(range(4),repeat=4):
        levels=sorted(set(groups))
        if levels!=list(range(len(levels))):continue
        values=[0]*4;position=0
        for group in levels:
            members=[i for i in range(4) if groups[i]==group]
            pool=sum(rule['bonuses'][position:position+len(members)]);bonus,rem=divmod(pool,len(members))
            for j,i in enumerate(members):values[i]=rule['return']+(points[i]-bonus-(j<rem))*100
            position+=len(members)
        try:result=score(rule,values)
        except Invalid:continue
        if [s['points'] for s in result]==points and values not in found:found.append(values)
    return found

def preview(d,kind,b):
    m=find(d['matches'],b.get('id'));raw=b.get('text')
    require(isinstance(raw,str) and len(raw)<=10000,'请粘贴两行四列数据')
    lines=raw.strip().splitlines();require(len(lines)==2,'需要两行：第一行四位选手姓名，第二行四个数值')
    rows=list(csv.reader(lines,delimiter='\t' if '\t' in raw else ','))
    require(all(len(row)==4 for row in rows),'每行必须四列，请直接从Excel复制')
    players=[]
    for name in rows[0]:
        matches=[p for p in d['players'] if p['name']==name.strip()]
        require(len(matches)==1,f'选手“{name.strip()}”不存在或重名，请先核对名单')
        players.append(matches[0])
    require(len({p['id'] for p in players})==4,'四列不能出现重复选手')
    if kind=='team':
        ordered=[]
        for seat in m['seats']:
            candidates=[i for i,p in enumerate(players) if (p.get('bondStages',{}).get(m['stageId']) if p.get('bond') else p['teamId'])==seat['teamId']]
            if m['state']=='published':candidates=[i for i,p in enumerate(players) if p['id']==seat['playerId']]
            require(len(candidates)==1,'粘贴名单与赛程队伍不对应，每队应有一名选手');ordered.append(candidates[0])
    else:
        ordered=[]
        for seat in m['seats']:
            require(seat['playerId'] in [p['id'] for p in players],'粘贴名单与本场参赛名单不一致')
            ordered.append(next(i for i,p in enumerate(players) if p['id']==seat['playerId']))
    try:numbers=[Decimal(rows[1][i].strip().replace('−','-')) for i in ordered]
    except InvalidOperation:raise Invalid('第二行必须为有效数字')
    require(all(n.is_finite() and abs(n)<=10000000 for n in numbers),'数值必须有限')
    mode=b.get('mode','scores');require(mode in ['scores','pt'],'请选择点棒或PT模式')
    if mode=='pt':
        require(not m.get('penalties'),'本场已有罚分，不能按无罚分PT反算')
        require(all(n*10==(n*10).to_integral_value() for n in numbers),'PT最多一位小数')
        candidates=inverse(dict(start=25000,**{'return':30000},bonuses=[500,100,-100,-300]),[int(n*10) for n in numbers])
        require(m['rule']['start']==25000 and m['rule']['return']==30000 and m['rule']['bonuses']==[500,100,-100,-300],'PT反算仅适用ML规则，请改用点棒录入')
    else:
        require(all(n==n.to_integral_value() for n in numbers),'点棒必须为整数')
        values=[int(n) for n in numbers]
        if sum(values)==m['rule']['start']*4//100:values=[v*100 for v in values]
        score(m['rule'],values);candidates=[values]
    require(candidates,'无法按无罚分ML规则还原这四个PT，请检查数值')
    seats=[dict(teamId=m['seats'][i]['teamId'],playerId=players[index]['id']) for i,index in enumerate(ordered)]
    prepared=apply(d,kind,'lineup',dict(id=m['id'],seats=seats)) if m['state']=='draft' and seats!=[{k:s[k] for k in ['teamId','playerId']} for s in m['seats']] else d
    output=[]
    for values in candidates:
        changed=apply(prepared,kind,'save-result',dict(id=m['id'],scores=values,penalties=m.get('penalties',[]),yakuman=m.get('yakuman',[])))
        result=find(changed['matches'],m['id'])
        output.append(dict(scores=values,seats=result['seats']))
    return dict(names=[players[i]['name'] for i in ordered],candidates=output,seats=seats)

def commit(d,kind,b,index):
    p=preview(d,kind,b);require(type(index) is int and 0<=index<len(p['candidates']),'请选择一个预览结果')
    m=find(d['matches'],b['id'])
    if m['state']=='draft' and p['seats']!=[{k:s[k] for k in ['teamId','playerId']} for s in m['seats']]:d=apply(d,kind,'lineup',dict(id=m['id'],seats=p['seats']))
    return apply(d,kind,'save-result',dict(id=m['id'],scores=p['candidates'][index]['scores'],penalties=m.get('penalties',[]),yakuman=m.get('yakuman',[])))
