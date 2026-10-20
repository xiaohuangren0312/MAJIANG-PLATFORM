"""Stage-wide seat/table balancing; never accepts an approximate plan."""
import copy, math, random, time
from collections import Counter, defaultdict
from django.utils import timezone
from .domain import require, live_stage
from .seat_draw import available


def _solve(groups, fixed, teams, labels, target, seed):
    rng = random.Random(seed)
    base = {(t, l): fixed[t, l] for t in teams for l in labels}
    require(all(v <= target for v in base.values()), '已固定场次超过均衡目标，无法完全均分')
    if all(len(items)==2 for items,_ in groups) and len(groups)<=28:
        # Exact meet-in-the-middle for daily two-table assignments.
        keys=list(base);vectors=[]
        for items,allowed in groups:
            options=[]
            for order in [(0,1),(1,0)]:
                c=Counter((t,allowed[order[i]]) for i,members in enumerate(items) for t in members)
                options.append(tuple(c[k] for k in keys))
            vectors.append(options)
        target_vector=tuple(target-base[k] for k in keys)
        def enumerate_half(part):
            states=[(tuple(0 for _ in keys),())]
            for options in part:
                states=[(tuple(a+b for a,b in zip(v,option)),bits+(choice,)) for v,bits in states for choice,option in enumerate(options)]
            return states
        middle=len(vectors)//2
        left=dict(enumerate_half(vectors[:middle]))
        for vector,bits in enumerate_half(vectors[middle:]):
            need=tuple(a-b for a,b in zip(target_vector,vector))
            if need in left:return [[0,1] if bit==0 else [1,0] for bit in left[need]+bits]
        require(False, '保留现有固定场次后，无法同时满足当日固定同桌和各队桌次完全均分；未作修改')
    best = None
    deadline = time.monotonic()+4
    # Each move exchanges two labels within one simultaneous group/game.
    # Both exclusivity and participant identity are preserved throughout.
    for attempt in range(12):
        assignment = [list(range(len(items))) for items, _ in groups]
        counts = base.copy()
        for g, (items, allowed) in enumerate(groups):
            if attempt: rng.shuffle(assignment[g])
            for i, members in enumerate(items):
                for t in members: counts[t, allowed[assignment[g][i]]] += 1
        cost = sum((v-target)**2 for v in counts.values())
        if cost == 0: return assignment
        movable = [i for i, (items, _) in enumerate(groups) if len(items)>1]
        if not movable: break
        for step in range(140000):
            if step%1000==0 and time.monotonic()>deadline:
                require(False, '均衡计算超时，现有安排未改动，请缩小赛程规模后重试')
            g = rng.choice(movable); items, allowed = groups[g]
            i,j = rng.sample(range(len(items)),2)
            a,b = allowed[assignment[g][i]],allowed[assignment[g][j]]
            changes = Counter()
            for t in items[i]: changes[t,a]-=1;changes[t,b]+=1
            for t in items[j]: changes[t,b]-=1;changes[t,a]+=1
            delta = sum((counts[k]+v-target)**2-(counts[k]-target)**2 for k,v in changes.items())
            temperature = max(.08, 2.5*(1-(step%20000)/20000))
            if delta<=0 or rng.random()<math.exp(-delta/temperature):
                for k,v in changes.items(): counts[k]+=v
                assignment[g][i],assignment[g][j]=assignment[g][j],assignment[g][i]
                cost += delta
                if cost == 0:return assignment
        best = cost if best is None else min(best,cost)
    require(False, '未找到完全均衡方案；现有安排未改动，请检查已固定场次与完整阶段赛程')


def balance(document, stage_id):
    d=copy.deepcopy(document)
    require(not d.get('archive'), '赛事已归档')
    live_stage(d,stage_id)
    rows=[m for m in d['matches'] if m['stageId']==stage_id and m['state']!='cancelled']
    require(bool(rows), '本阶段尚无赛程')
    require(not any(m.get('pairingRound') for m in rows), '高高碰轮次不支持全阶段预排')
    require(all(len(m['seats'])==4 and all(s.get('teamId') for s in m['seats']) and len({s['teamId'] for s in m['seats']})==4 for m in rows), '仅支持四支不同队伍的团体赛')
    tables=sorted({m['number'] for m in rows})
    total=Counter(s['teamId'] for m in rows for s in m['seats'])
    require(len(set(total.values()))==1, '各队半庄总数不一致，请先补全本阶段赛程')
    games=next(iter(total.values()));require(games%4==0 and games%len(tables)==0, '半庄总数不能整除桌数或四个风位，无法完全均分')
    mutable={m['id'] for m in rows if available(d,m) and not m.get('readOnly')}
    require(bool(mutable), '没有可调整的未开赛场次')
    fixed_tables=Counter();fixed_winds=Counter();slots=defaultdict(list)
    for m in rows:
        slots[m['date'],m['time']].append(m)
        if m['id'] not in mutable:
            for w,s in enumerate(m['seats']):fixed_tables[s['teamId'],m['number']]+=1;fixed_winds[s['teamId'],w]+=1
    for slot in slots.values():
        require(len({m['number'] for m in slot})==len(slot), '现有赛程同一时间桌号重复')
        require(len({s['teamId'] for m in slot for s in m['seats']})==4*len(slot), '同一时间队伍重复参赛')
    # A daily four-team group is indivisible: all its half games use one table.
    days=defaultdict(lambda:defaultdict(list))
    for m in rows:days[m['date']][tuple(sorted(s['teamId'] for s in m['seats']))].append(m)
    fixed_tables=Counter();table_groups=[];table_rows=[]
    for day,groups in sorted(days.items()):
        participants=[t for group in groups for t in group]
        require(len(participants)==len(set(participants)), '同一天同一队伍的对手组不一致，请先核对赛程')
        labels=sorted({m['number'] for group in groups.values() for m in group})
        require(len(labels)==len(groups), '当日比赛桌数量与队伍组数不一致，请先配置比赛桌')
        reserved=set();moving_groups=[]
        for members,group in groups.items():
            fixed={m['number'] for m in group if m['id'] not in mutable}
            require(len(fixed)<=1, '同组已有固定场次跨桌，无法在保留战果的同时统一当日桌次')
            if fixed:
                number=next(iter(fixed));require(number not in reserved,'不同队伍组已固定到同一张桌');reserved.add(number)
                for m in group:
                    if m['id'] in mutable:m['number']=number;m['table']=str(number)
                    for t in members:fixed_tables[t,number]+=1
            else:moving_groups.append(group)
        if not moving_groups:continue
        allowed=[n for n in labels if n not in reserved]
        table_rows.append(moving_groups)
        table_groups.append(([[s['teamId'] for m in group for s in m['seats']] for group in moving_groups],allowed))
    plan=_solve(table_groups,fixed_tables,total,tables,games//len(tables),407)
    for groups,assign,(_,labels) in zip(table_rows,plan,table_groups):
        for i,group in enumerate(groups):
            for m in group:m['number']=labels[assign[i]];m['table']=str(m['number'])
    moving=[m for m in rows if m['id'] in mutable]
    wind_groups=[([[s['teamId']] for s in m['seats']],list(range(4))) for m in moving]
    plan=_solve(wind_groups,fixed_winds,total,list(range(4)),games//4,911)
    stamp=timezone.now().isoformat()
    for m,assign in zip(moving,plan):
        old=m['seats'][:];m['seats']=[None]*4
        for i,w in enumerate(assign):m['seats'][w]=old[i]
        m['seatDraw']={'mode':'stage-balanced','at':stamp,'count':m.get('seatDraw',{}).get('count',0)+1}
    # Independent final verification, including cross-stage table conflicts.
    occupied=set()
    for m in d['matches']:
        if m['state']=='cancelled':continue
        key=(m['date'],m['time'],m['number']);require(key not in occupied,'调整后与其他场次桌号冲突');occupied.add(key)
    daily_tables=defaultdict(set)
    for m in rows:
        for seat in m['seats']:daily_tables[m['date'],seat['teamId']].add(m['number'])
    require(all(len(v)==1 for v in daily_tables.values()), '同一比赛日队伍跨桌，校验失败')
    tc=Counter((s['teamId'],m['number']) for m in rows for s in m['seats'])
    wc=Counter((s['teamId'],w) for m in rows for w,s in enumerate(m['seats']))
    require(all(tc[t,n]==games//len(tables) for t in total for n in tables),'桌次校验失败')
    require(all(wc[t,w]==games//4 for t in total for w in range(4)),'风位校验失败')
    return d
