"""Reproducible S1 archive import. Source cells remain outside Git; default is preview."""
import sys, json, copy, datetime, collections, argparse, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from league.domain import initial,score
from league.history_correction import totals

def build(cells):
    sheets={k:{c:v for row in rows for c,v in row.items()} for k,rows in cells.items()}
    def v(sh,c):return sheets[sh].get(c,{}).get('v')
    def pt(x):return round(float(x)*10)
    def date(x):return (datetime.date(1899,12,30)+datetime.timedelta(days=x)).isoformat()
    teams=[dict(id='t'+str(r),name=v('常规赛','B'+str(r)),color=color) for r,color in zip(range(3,11),['#82463e','#465875','#ad853b','#70608e','#3e7774','#8c5974','#576b40','#a26631'])]
    teamids={t['name']:t['id'] for t in teams};players=[];people={}
    for r in range(2,51):
        p=dict(id='p'+str(r),name=v('超级联赛详细数据','C'+str(r)),teamId=teamids[v('超级联赛详细数据','B'+str(r))],bio='S1 历史比赛记录')
        people[p['name'].casefold()]=p;players.append(p)
    # User confirmed this alias on 2026-09-16; retain source name on each seat.
    people['鹤轩逸']=people['鹤']
    for team in teams:
        row=next(r for r in range(32,40) if v('战队名单','B'+str(r))==team['name'])
        coach=v('战队名单','C'+str(row));person=people.get(str(coach).casefold())
        team['coach']=dict(name=coach,playerId=person['id'] if person else None,playing=coach!='麻神',source='战队名单 教练栏')
    results=[];schedule=[];rule=initial()['rules'][0]
    def add(stage,day,number,names,scores,pts,source):
        calculated=score(rule,scores);seats=[]
        for n,s,pv in zip(names,calculated,pts):
            person=people[str(n).strip().casefold()];s.update(playerId=person['id'],teamId=person['teamId'],sourceName=str(n).strip())
            assert s['base']==pt(pv),(source,n,s['base'],pv)
            seats.append(s)
        assert len({s['teamId'] for s in seats})==4,(source,names)
        m=dict(id=f'S1-{stage}-{number}',stageId=stage,date=day,time='时间未记录',table='A',number=number,ruleName='S1 原表 / M.LEAGUE 计分',ruleVersion=1,seats=seats,penalties=[],yakuman=[],source=source)
        if stage!='regular':m['time']='19:30' if number%2 else '21:00'
        results.append(m)
    for r in range(2,74):
        add('regular',date(v('对局记录','B'+str(r))),r-1,[v('对局记录',c+str(r)) for c in 'CFIL'],[int(v('对局记录',c+str(r))) for c in 'DGJM'],[v('对局记录',c+str(r)) for c in 'EHKN'],f'对局记录 第{r}行')
    # The source player board AND official team board both include this 20 PT deduction.
    penalized=next(m for m in results if m['date']=='2025-06-12' and any(s['playerId']==people['小茵']['id'] for s in m['seats']))
    s=next(s for s in penalized['seats'] if s['playerId']==people['小茵']['id']);s.update(penalty=200,points=s['base']-200,teamPoints=s['base']-200)
    penalized['penalties']=[dict(playerId=s['playerId'],amount=200,scope='both',explanation='判罚记录：小茵红牌个人扣20PT；正式队伍榜亦含该20PT，按原表分别核对保留')]
    for dayindex,nr,cols in [(0,18,'PQRS'),(1,31,'PQRS'),(2,44,'PQRS'),(3,86,'NOPQ'),(4,68,'NOPQ'),(8,100,'NOPQ')]:
        day=date(v('半决赛','A'+str(16+dayindex)))
        for game in range(2):
            r=nr+game*6
            add('semi',day,dayindex*2+game+1,[v('半决赛',c+str(r)) for c in cols],[int(v('半决赛',c+str(r+3))) for c in cols],[v('半决赛',c+str(r+4)) for c in cols],f'半决赛 {cols[0]}{r}:{cols[-1]}{r+4}')
    for dayindex,(day,nr,cols) in enumerate([('2025-08-17',21,'EFGH'),('2025-08-19',21,'LMNO'),('2025-08-21',35,'EFGH'),('2025-08-24',35,'LMNO')]):
        for game in range(2):
            r=nr+game*6
            add('final',day,dayindex*2+game+1,[v('决赛',c+str(r)) for c in cols],[int(v('决赛',c+str(r+3))) for c in cols],[v('决赛',c+str(r+4)) for c in cols],f'决赛 {cols[0]}{r}:{cols[-1]}{r+4}')
    days=collections.defaultdict(list)
    for m in results:
        if m['stageId']=='regular':days[m['date']].append(m)
    for ms in days.values():
        for i,m in enumerate(ms):
            m['table']='ABCD'[i] if len(ms)==4 else chr(65+i)
            if len(ms)==4:m['time']='19:30' if i in [0,2] else '21:00'
    results.sort(key=lambda m:(m['date'],m['number']))
    for m in results:schedule.append(dict(id=m['id'],stageId=m['stageId'],date=m['date'],time=m['time'],table=m['table'],number=m['number'],players=[dict(playerId=s['playerId'],teamId=s['teamId']) for s in m['seats']],lineupPublished=True,state='completed',resultId=m['id']))
    daily=[]
    for i,col in enumerate('GHIJKLMN'):
        entries=[dict(teamId=teamids[v('半决赛','E'+str(r))],points=pt(v('半决赛',col+str(r)))) for r in range(60,66) if v('半决赛',col+str(r)) is not None]
        day=date(v('半决赛','A'+str(16+i)))
        daily.append(dict(stageId='semi',day=day,number=i+1,entries=entries,detailAvailable=i not in [5,6,7]))
        if i in [5,6,7]:
            for game in range(2):schedule.append(dict(id=f'S1-semi-{i*2+game+1}',stageId='semi',date=day,time='19:30' if game==0 else '21:00',table='A',number=i*2+game+1,players=[dict(playerId=None,teamId=e['teamId']) for e in entries],lineupPublished=False,state='completed',resultId=None))
    # Last semifinal day is absent from the stale day-total grid; use its complete details.
    last=[m for m in results if m['stageId']=='semi' and m['number']>=17];day=last[0]['date']
    daily.append(dict(stageId='semi',day=day,number=9,entries=[dict(teamId=tid,points=sum(s['teamPoints'] for m in last for s in m['seats'] if s['teamId']==tid)) for tid in {s['teamId'] for m in last for s in m['seats']}],detailAvailable=True))
    snapshots=[]
    for stage,sh,rs,nc,tc,cc in [('regular','常规赛',range(3,11),'F','G',None),('semi','半决赛',range(109,115),'F','G','H'),('final','决赛',range(7,11),'P','Q',None)]:
        rows=[]
        for r in rs:
            name=v(sh,nc+str(r));carry=pt(v(sh,cc+str(r))) if cc else 0
            if stage=='final':carry=next(pt(v('决赛','G'+str(x))) for x in range(7,11) if v('决赛','E'+str(x))==name)
            rows.append(dict(name=name,total=pt(v(sh,tc+str(r))),carry=carry))
        rows.sort(key=lambda r:-r['total']);snapshots.append(dict(name={'regular':'常规赛','semi':'半决赛','final':'决赛'}[stage],rows=rows))
    t=dict(id='s1',name='欢雀楼超级联赛 S1',type='team',season='S1',venue='欢雀楼',currentStage='final',historical=True,teams=teams,players=players,results=results,schedule=sorted(schedule,key=lambda m:(m['date'],m['time'],m['number'])),dailySummaries=daily,snapshots=snapshots,stages=[dict(id=k,name=n,advanceCount=a) for k,n,a in [('regular','常规赛',6),('semi','半决赛',4),('final','决赛',0)]],rules=dict(name='S1 原表 / M.LEAGUE 计分',description='25000起始点、30000返点，顺位分50/10/-10/-30；保留原表判罚与带入'),statistics={})
    for stage in ['all','regular','semi','final']:
        raw={}
        for kind,entities in [('player',players),('team',teams)]:
            rows=[]
            for e in entities:
                r=totals(t,stage,kind,e['id']);total=r.pop('contribution');r.update(id=e['id'],name=e['name'],total=total,raw=total,carry=0,penalty=(r['base']-total if r['base'] is not None else None),yakuman=None);rows.append(r)
            raw[kind]=rows
        comp=copy.deepcopy(raw)
        if stage!='all':
            snap=snapshots[['regular','semi','final'].index(stage)]
            comp['team']=[]
            for sr in snap['rows']:
                r=copy.deepcopy(next(r for r in raw['team'] if r['id']==teamids[sr['name']]))
                r.update(total=sr['total'],carry=sr['carry'],raw=sr['total']-sr['carry']);comp['team'].append(r)
        else:
            for r in comp['team']:r['total']=r['raw']=sum(sr['total']-sr['carry'] for snap in snapshots for sr in snap['rows'] if teamids[sr['name']]==r['id'])
        for metric in [raw,comp]:
            for rows in metric.values():
                rows.sort(key=lambda r:-r['total'])
                for i,r in enumerate(rows):r['rank']=rows[i-1]['rank'] if i and rows[i-1]['total']==r['total'] else i+1
        t['statistics'][stage]=dict(raw=raw,competitive=comp)
    # Validate against source totals, never stale intermediate snapshots.
    for r in range(2,51):
        p=people[str(v('超级联赛详细数据','C'+str(r))).casefold()];actual=next(x for x in t['statistics']['regular']['raw']['player'] if x['id']==p['id'])
        assert actual['total']==pt(v('超级联赛详细数据','D'+str(r))) and actual['games']==v('超级联赛详细数据','F'+str(r)),p
    for r in t['statistics']['regular']['competitive']['team']:assert r['total']==next(x['total'] for x in t['statistics']['regular']['raw']['team'] if x['id']==r['id'])
    for r in t['statistics']['semi']['competitive']['team']:assert r['raw']==sum(e['points'] for d in daily for e in d['entries'] if e['teamId']==r['id']),(r['name'],r['raw'])
    for r in t['statistics']['final']['competitive']['team']:assert r['raw']==next(x['raw'] for x in t['statistics']['final']['raw']['team'] if x['id']==r['id']),r
    t['coverage']='常规赛72场、半决赛12场、决赛8场完整明细；半决赛另6场仅有队伍日合计，赛程保留，个人统计不推造。小茵20PT按个人榜及正式队伍榜保留。鹤轩逸已按用户确认合并为鹤。少数补赛时间未知。役满未采集。'
    t['reconciliation']=dict(version=1,source='欢雀楼超级联赛S1.xlsx',userConfirmation=dict(unknownPolicy='retain'),notes=['大小写别名统一Dyz/dyz、TOM/Tom','半决赛使用最终109–114行，避免旧快照','决赛使用最终Q7:Q10，不使用6/8中间榜','用户确认鹤轩逸就是鹤，已统一身份，座次sourceName保留原表昵称'])
    assert len(results)==92 and len(schedule)==98
    return t

def main():
    ap=argparse.ArgumentParser();ap.add_argument('cells');ap.add_argument('--write-fixture',action='store_true');ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    t=build(json.loads(Path(args.cells).read_text(encoding='utf8')))
    print(json.dumps(dict(teams=len(t['teams']),players=len(t['players']),results=len(t['results']),schedule=len(t['schedule']),final=t['snapshots'][-1]),ensure_ascii=False))
    if args.write_fixture:
        dest=Path(__file__).resolve().parents[2]/'design/history-analysis/S1-public.json';dest.write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf8')
    if args.apply:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE','hql.settings');import django;django.setup()
        from django.db import transaction
        from django.contrib.auth import get_user_model
        from league.models import HistoricalArchive,HistoryImport,Event,Audit
        from league.history_review import fingerprint
        with transaction.atomic():
            if HistoricalArchive.objects.filter(pk='s1').exists():raise RuntimeError('S1 already exists; refusing to overwrite')
            archive=HistoricalArchive.objects.create(key='s1',payload=t,public=True);digest=fingerprint(t);d=initial();d.update(season='S1',venue='欢雀楼',historySnapshot=copy.deepcopy(t),historySource=dict(key='s1',fingerprint=digest,reason='S1原表历史导入'))
            actor=get_user_model().objects.get(username='hql-admin');e=Event.objects.create(name=t['name'],kind='team',document=d,public=False);e.editors.add(actor)
            HistoryImport.objects.create(archive=archive,event=e,fingerprint=digest);Audit.objects.create(event=e,actor=actor,revision=1,action='history-import',reason='S1原表历史导入',before={},after=dict(document=d))
            print('Imported event',e.id)
if __name__=='__main__':main()
