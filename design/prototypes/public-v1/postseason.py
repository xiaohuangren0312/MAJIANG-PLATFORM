"""Import only attributable postseason records; never infer players from PT."""
import collections, copy, datetime, re

def augment(t, sheets):
    season=t['season']
    def flat(sheet): return {c:v for row in sheets[sheet] for c,v in row.items()}
    def value(f,c): return f.get(c,{}).get('v')
    def text(v): return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v or '').strip()
    def pt(v): return round(float(v)*10)
    def date(v): return (datetime.date(1899,12,30)+datetime.timedelta(days=v)).isoformat()
    teams={x['name'].strip():x['id'] for x in t['teams']}
    people={x['name']:x for x in t['players']}
    def person(n):
        if not n: return None
        if n not in people:
            p={'id':f'post{len(people)}','name':n,'teamId':None,'bio':'淘汰赛原表昵称，队伍对应待核对'}
            people[n]=p; t['players'].append(p)
        return people[n]
    def seat(n,points,team_id=None,score=None,rank=None):
        p=person(n)
        return dict(playerId=p['id'] if p else None,teamId=team_id or (p['teamId'] if p else None),score=score,rank=rank,tied=False,base=None,penalty=None,points=points,teamPoints=points)
    def add(stage,day,num,seats,source):
        m=dict(id=f'{season}-{stage}-{num}',stageId=stage,date=day,table='历史记录',number=num,ruleName='原表逐场 PT；未记录字段不推算',ruleVersion=1,seats=seats,penalties=[],yakuman=[],source=source)
        t['results'].append(m)
        t['schedule'].append(dict(id=m['id'],stageId=stage,date=day,time='时间未记录',table=m['table'],number=num,players=[dict(playerId=s['playerId'],teamId=s['teamId']) for s in seats],lineupPublished=True,state='completed',resultId=m['id']))

    # S2 has a dedicated name / PT block. Later undated scratch calculations
    # in the finals worksheet do not agree with the official daily totals.
    if season=='S2':
        for stage,sheet,blocks in [('semi','S2半决赛赛程',[(r,'K','LMNO') for r in [14,20,26,32,38,44,50,57,63]]),('final','S2决赛',[(11,'G','HJKL'),(17,'G','HIJK'),(23,'G','HIJK')])]:
            f=flat(sheet)
            for day_index,(r,dc,cols) in enumerate(blocks):
                for game in range(2):
                    nr=r+1+game*2; seats=[]
                    for c in cols:
                        n=value(f,f'{c}{nr}'); points=value(f,f'{c}{nr+1}')
                        # H18 contains PT in the name cell; no recoverable name.
                        missing=stage=='final' and nr==18 and c=='H'
                        if missing: points=n; n=None
                        assert isinstance(points,(int,float)), (sheet,c,nr)
                        seats.append(seat(text(n) if n is not None else None,pt(points),teams['Asoul'] if missing else None))
                    # Where all four board formulas agree with this game's
                    # four PT values, use the board's actual team assignments.
                    board_col=('KLMNOPQRS' if stage=='semi' else 'KLM')[day_index]
                    board_rows=range(3,9) if stage=='semi' else range(4,8)
                    board_name='G' if stage=='semi' else 'H'
                    terms=[]
                    for br in board_rows:
                        formula=f.get(f'{board_col}{br}',{}).get('f') or ''
                        pair=re.fullmatch(r'=([+-]?\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)',formula)
                        if pair: terms.append((teams[text(value(f,f'{board_name}{br}'))],pt(float(pair.groups()[game]))))
                    if len(terms)==4 and sorted(p for _,p in terms)==sorted(s['points'] for s in seats) and len(set(p for _,p in terms))==4:
                        for s in seats: s['teamId']=next(tid for tid,p in terms if p==s['points'])
                    add(stage,date(value(f,f'{dc}{r}')),day_index*2+game+1,seats,f'{sheet} 第 {nr}–{nr+1} 行')

    t['dailySummaries']=[]
    for stage,sheet,rs,nc,cols,datecells in (
        [('semi','S3半决赛',range(5,11),'F','KLMNOPQRSTUV',[f'C{r}' for r in range(31,43)]),('final','S3决赛',range(5,9),'F','KLMN',[f'C{r}' for r in range(17,21)])]
        if season=='S3' else [('final','S2决赛',range(4,8),'H','N',['N3'])]
    ):
        f=flat(sheet)
        for day_index,(col,dc) in enumerate(zip(cols,datecells)):
            entries=[]; pairs=[]
            for r in rs:
                cell=f.get(f'{col}{r}',{}); v=cell.get('v')
                if v is None: continue
                tid=teams[text(value(f,f'{nc}{r}'))]
                entries.append(dict(teamId=tid,points=pt(v)))
                formula=cell.get('f') or ''
                match=re.fullmatch(r'=([+-]?\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)',formula)
                if match:
                    a,b=map(float,match.groups())
                    assert pt(a)+pt(b)==pt(v)
                    pairs.append((tid,[pt(a),pt(b)]))
            day=date(value(f,dc))
            complete=len(pairs)==4
            t['dailySummaries'].append(dict(stageId=stage,day=day,number=day_index+1,entries=entries,detailAvailable=complete))
            if not complete: continue
            for game in range(2):
                seats=[seat(None,points[game],tid) for tid,points in pairs]
                # S3 semifinal day7 calculator matches the board's two terms.
                if season=='S3' and stage=='semi' and day_index==6:
                    nr=17 if game==0 else 24
                    for c in 'PQRS':
                        points=pt(value(f,f'{c}{nr+4}'))
                        target=next(s for s in seats if s['points']==points)
                        target.update(playerId=person(text(value(f,f'{c}{nr}')))['id'],score=int(value(f,f'{c}{nr+3}')),rank=int(value(f,f'{c}{nr+2}')))
                if season=='S3' and stage=='final' and day_index==2 and game==0:
                    assert sorted(pt(value(f,f'{c}21')) for c in 'QRST')==sorted(s['points'] for s in seats)
                    for c in 'QRST':
                        target=next(s for s in seats if s['points']==pt(value(f,f'{c}21')))
                        target.update(score=int(value(f,f'{c}20')),rank=int(value(f,f'{c}19')))
                add(stage,day,(day_index*2+game+1) if season=='S3' else 7+game,seats,f'{sheet} {col}列两项公式，姓名缺失时保留为空')

    t['stages']=[{'id':k,'name':n} for k,n in [('regular','常规赛'),('semi','半决赛'),('final','决赛')]]
    t['currentStage']='final'
    # Statistics use known fields only. Unknown player seats never create a
    # fictional athlete; missing ranks/point sticks do not become zeroes.
    def stats(matches,kind):
        rows=[]
        for e in t['players' if kind=='player' else 'teams']:
            seats=[s for m in matches for s in m['seats'] if s[kind+'Id']==e['id']]
            places=[0.0]*4
            for m in matches:
                for s in m['seats']:
                    if s[kind+'Id']!=e['id'] or s['rank'] is None: continue
                    tied=sum(x['score']==s['score'] for x in m['seats']) if s['tied'] else 1
                    for k in range(s['rank']-1,s['rank']-1+tied): places[k]+=1/tied
            n=len(seats); ranked=sum(places); scores=[s['score'] for s in seats if s['score'] is not None]; total=sum(s['points'] for s in seats)
            rows.append(dict(id=e['id'],name=e['name'],base=None if any(s['base'] is None for s in seats) else sum(s['base'] for s in seats),penalty=None if any(s['penalty'] is None for s in seats) else sum(s['penalty'] for s in seats),carry=0,total=total,raw=total,games=n,rank=0,places=places,rankedGames=ranked,avgRank=sum((i+1)*v for i,v in enumerate(places))/ranked if ranked else None,topRate=places[0]/ranked if ranked else None,topTwo=sum(places[:2])/ranked if ranked else None,avoidLast=1-places[3]/ranked if ranked else None,best=max(scores,default=None),avgPoints=sum(scores)/len(scores) if scores else None,yakuman=None,last=seats[-1]['points'] if seats else 0,history=[s['points'] for s in seats]))
        rows.sort(key=lambda r:-r['total'])
        for i,r in enumerate(rows): r['rank']=i+1
        return rows
    t['results'].sort(key=lambda m:(m['date'],m['number']))
    t['statistics']={}
    for stage in ['all','regular','semi','final']:
        matches=[m for m in t['results'] if stage=='all' or m['stageId']==stage]
        raw={kind:stats(matches,kind) for kind in ['player','team']}
        competitive=copy.deepcopy(raw)
        if stage in ['semi','final']:
            snapshot=t['snapshots'][1 if stage=='semi' else 2]
            competitive['team']=[]
            for sr in snapshot['rows']:
                tid=teams[sr['name'].strip()]
                row=copy.deepcopy(next(r for r in raw['team'] if r['id']==tid))
                row.update(carry=sr['carry'],total=sr['total'],raw=sr['total']-sr['carry'])
                competitive['team'].append(row)
            for i,r in enumerate(competitive['team']): r['rank']=i+1
        t['statistics'][stage]=dict(raw=raw,competitive=competitive)
    counts=collections.Counter(m['stageId'] for m in t['results'])
    t['coverage']=f"已导入常规赛 {counts['regular']} 场、半决赛 {counts['semi']} 场、决赛 {counts['final']} 场逐场 PT。缺失姓名、点棒和顺位不推算；个人榜只统计已知选手，顺位指标只统计已知顺位。队伍阶段竞技分保留源表结转及总分；原始累计仅含已导入明细，部分差异待核对。役满未采集。"
    if season=='S3': t['coverage']+=' 半决赛另有 7 个比赛日仅有队伍合计，尚缺 14 场逐场明细。'
    if season=='S2': t['coverage']+=' 半决赛源表两组日期重复，暂保留原值；决赛末日使用队伍公式，选手待补。'
    assert counts==({'regular':108,'semi':10,'final':8} if season=='S3' else {'regular':80,'semi':18,'final':8}),counts
    assert len({m['id'] for m in t['results']})==len(t['results'])
    for m in t['results']: assert len(m['seats'])==4
