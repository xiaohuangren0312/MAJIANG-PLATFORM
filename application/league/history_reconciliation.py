"""Repair verified S2/S3 extraction defects without guessing missing identities."""
import copy,datetime
from collections import defaultdict
from .history_correction import totals

VERSION = 2

def reconcile(source):
    p=copy.deepcopy(source)
    if p.get('reconciliation',{}).get('version')==VERSION:return p
    assert p['id'] in ['s2','s3']
    groups=defaultdict(list)
    for x in p['players']:groups[x['name'].strip().casefold()].append(x)
    aliases={};evidence=copy.deepcopy(p.get('reconciliation',{}).get('aliases',[]))
    if p['id']=='s2':
        people={x['name']:x for x in p['players']}
        for old,new in [('Zing_Coco','COCO'),('菜菜子','神菜菜子'),('404','_404')]:
            if old not in people:continue
            target=people[new];aliases[people[old]['id']]=target
            target.setdefault('aliases',[]).append(old)
            evidence.append(dict(alias=old,name=new,teamId=target['teamId'],basis='用户2026-09-08统一确认'))
        people['楠哥']['bio']='银河蘸酱选手；用户已确认独立身份'
        for m in p['results']:
            if m['id']=='S2-r55':
                for penalty in m['penalties']:
                    assert penalty['amount']==20
                    penalty['explanation']='迟到罚分（2 PT，用户确认）'
    for group in groups.values():
        registered=[x for x in group if x.get('teamId')]
        if len(group)>1 and len(registered)==1:
            target=registered[0]
            for x in group:
                if x['id']!=target['id']:
                    aliases[x['id']]=target
                    target.setdefault('aliases',[]).append(x['name'])
                    evidence.append(dict(alias=x['name'],name=target['name'],teamId=target['teamId'],basis='同赛季名单唯一大小写对应，常规赛出场数及阶段总分交叉校验'))
    for m in p['results']:
        for s in m['seats']:
            if s.get('playerId') in aliases:
                x=aliases[s['playerId']];s['playerId']=x['id'];s['teamId']=s.get('teamId') or x['teamId']
        for key in ['penalties','yakuman']:
            for row in m.get(key,[]):
                if row.get('playerId') in aliases:row['playerId']=aliases[row['playerId']]['id']
        ids=[s['playerId'] for s in m['seats'] if s.get('playerId')]
        assert len(ids)==len(set(ids)),m['id']
    p['players']=[x for x in p['players'] if x['id'] not in aliases]
    for x in p['players']:
        if x.get('teamId'):continue
        known={s['teamId'] for m in p['results'] for s in m['seats'] if s.get('playerId')==x['id'] and s.get('teamId')}
        if len(known)==1:
            x['teamId']=known.pop();x['bio']='队伍归属由本赛季阶段成绩表确认；昵称是否为别名待统一确认'
            for m in p['results']:
                for s in m['seats']:
                    if s.get('playerId')==x['id'] and not s.get('teamId'):s['teamId']=x['teamId']
    if p['id']=='s2':
        for m in p['results']:
            if m['id'] in ['S2-semi-11','S2-semi-12']:
                m['date']=(datetime.date(1899,12,30)+datetime.timedelta(days=46046)).isoformat()
                m['sourceDateNote']='S2半决赛赛程 P1及第6比赛日赛程日期；手填K44重复日期已纠正'
    by_id={m['id']:m for m in p['results']}
    for row in p.get('schedule',[]):
        match=by_id.get(row.get('resultId') or row.get('id'))
        if match:row['date']=match['date']
        if match:row['players']=[dict(playerId=s.get('playerId'),teamId=s.get('teamId')) for s in match['seats']]
    teams={x['name'].strip():x['id'] for x in p['teams']}
    p['statistics']={}
    for stage in ['all','regular','semi','final']:
        raw={}
        for kind,collection in [('player','players'),('team','teams')]:
            rows=[]
            for e in p[collection]:
                values=totals(p,stage,kind,e['id']);value=values.pop('contribution')
                seats=[s for m in p['results'] if stage=='all' or m['stageId']==stage for s in m['seats'] if s.get(kind+'Id')==e['id']]
                penalty=sum(s['penalty'] for s in seats) if all(s.get('penalty') is not None for s in seats) else None
                rows.append(dict(id=e['id'],name=e['name'],total=value,raw=value,carry=0,penalty=penalty,yakuman=None,rank=0,**values))
            raw[kind]=rows
        competitive=copy.deepcopy(raw)
        if stage!='all':
            snapshot=p['snapshots'][['regular','semi','final'].index(stage)]
            competitive['team']=[]
            for r in snapshot['rows']:
                tid=teams[r['name'].strip()];row=copy.deepcopy(next(x for x in raw['team'] if x['id']==tid))
                row.update(total=r['total'],carry=r.get('carry') or 0,raw=r['total']-(r.get('carry') or 0),officialSummary=True,detailTotal=row['total'])
                if stage=='regular' and p['id']=='s3':
                    fine={'t3':120,'t4':200,'t10':20}.get(tid,0)
                    assert row['detailTotal']-fine==r['total'],r
                    row['penalty']=(row['penalty'] or 0)+fine
                    row['stagePenalty']=fine
                elif stage=='regular' or p['id']=='s2':assert row['detailTotal']==row['raw'],(stage,r,row['detailTotal'])
                competitive['team'].append(row)
        else:
            for row in competitive['team']:
                value=sum(r['total']-(r.get('carry') or 0) for snap in p['snapshots'] for r in snap['rows'] if teams[r['name'].strip()]==row['id'])
                row.update(total=value,raw=value,detailTotal=row['total'],officialSummary=True)
        for metric in [raw,competitive]:
            for rows in metric.values():
                rows.sort(key=lambda x:-x['total'])
                for i,row in enumerate(rows):row['rank']=rows[i-1]['rank'] if i and rows[i-1]['total']==row['total'] else i+1
        p['statistics'][stage]=dict(raw=raw,competitive=competitive)
    p['reconciliation']=dict(version=VERSION,aliases=evidence,sourcePolicy='队伍竞技榜采用阶段正式成绩；全赛事合计各阶段净成绩，不重复加带入。原始累计仅为已导入逐场明细。')
    p['reconciliation']['userConfirmation']=dict(unknownPolicy='retain',identitiesConfirmed=True,latePenaltyConfirmed=True,nanGe='银河蘸酱独立选手',date='2026-09-08')
    p['coverage']='队伍竞技榜采用原Excel各阶段正式成绩，含原表罚分和带入；全赛事合计各阶段净成绩，不重复加带入。原始累计仅统计已导入明细。大小写昵称及队伍归属已统一核对。缺失选手、点棒、顺位与罚分明细保持未知，个人榜仅统计已知选手；役满未采集。'
    if p['id']=='s3':p['coverage']+=' 半决赛14场只有比赛日队伍合计，已计入队伍竞技榜，不伪造逐场和个人数据。常规赛队伍罚分：玩你的内阁12PT、旋风宝宝20PT、弯道超车2PT，已按原表扣除。'
    p['correctionNotice']=p['coverage']
    return p
