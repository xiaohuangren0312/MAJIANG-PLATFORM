"""Read extracted workbook cells; publish only competition fields, never registration notes."""
import json, pathlib, re, datetime, collections
from postseason import augment
ROOT=pathlib.Path(__file__).parent
def name(v): return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v or '').strip()
def pt(v): return round(float(v or 0)*10)
def flat(rows): return {k:v for row in rows for k,v in row.items()}
def val(f,c): return f.get(c,{}).get('v')
out={'demo':True,'historical':True,'updatedAt':'2026-09-05','tournaments':[]}
for season in ['S3','S2']:
 d=json.loads((ROOT.parent.parent/'history-analysis'/f'{season}-cells.json').read_text(encoding='utf-8'))
 f=flat(d['超级联赛详细数据']); board=flat(d['S3赛程' if season=='S3' else '赛程'])
 teams=[]; players=[]; index={}; colors=['#23674d','#596e9c','#ac564c','#7f6591','#8e752e','#357f85','#a4687e','#657447','#765946']
 for r in range(3,12 if season=='S3' else 11):
  teams.append({'id':f't{r}', 'name':name(val(board,f'F{r}')),'color':colors[r-3]})
 teamnames={x['name']:x['id'] for x in teams}
 for r in range(2,100):
  n=val(f,f'C{r}')
  if n is None: continue
  n=name(n); p={'id':f'p{r}','name':n,'teamId':teamnames.get(name(val(f,f'B{r}'))),'bio':f'{season} 常规赛历史记录'}
  players.append(p); index[n]=p
 matches=[]; source=flat(d['对局记录'])
 for r in range(3,111 if season=='S3' else 83):
  seats=[]; adjustments=[]; scores=[val(source,f'{c}{r}') for c in ['D','G','J','M']]
  assert all(isinstance(v,(int,float)) for v in scores)
  for i,(nc,sc,pc) in enumerate(zip(['C','F','I','L'],['D','G','J','M'],['E','H','K','N'])):
   n=name(val(source,f'{nc}{r}')); p=index.get(n)
   if not p:
    p={'id':f'extra{len(players)}','name':n,'teamId':None,'bio':'源表昵称，队伍对应关系待核对'}; players.append(p);index[n]=p
   score=scores[i]; same=[k for k,x in enumerate(scores) if x==score]; bonus=sum([50,10,-10,-30][k] for k in same)/len(same)
   base=pt((score-30000)/1000+bonus); points=pt(val(source,f'{pc}{r}')); deduction=base-points
   seats.append({'playerId':p['id'],'teamId':p['teamId'],'score':int(score),'rank':min(same)+1,'tied':len(same)>1,'base':base,'penalty':deduction,'points':points,'teamPoints':points})
   if deduction: adjustments.append({'playerId':p['id'],'amount':deduction,'scope':'both','explanation':'原表 PT 含扣分，原因待补' if season=='S2' and r==18 else '原表 PT 与点棒换算存在差额，原因及影响范围待核对'})
  date=(datetime.datetime(1899,12,30)+datetime.timedelta(days=val(source,f'B{r}'))).date().isoformat()
  matches.append({'id':f'{season}-r{r}','stageId':'regular','date':date,'table':'历史记录','number':r-2,'ruleName':'历史原表 PT（差异保留）','ruleVersion':1,'seats':seats,'penalties':adjustments,'yakuman':[]})
 matches.sort(key=lambda m:(m['date'],m['number']))
 stats={}
 for kind,entities in [('player',players),('team',teams)]:
  rows=[]
  for entity in entities:
   seats=[s for m in matches for s in m['seats'] if s['playerId' if kind=='player' else 'teamId']==entity['id']]; n=len(seats); places=[0.0]*4
   for s in seats:
    match=next(m for m in matches if s in m['seats']); tied=sum(x['score']==s['score'] for x in match['seats'])
    for k in range(s['rank']-1,s['rank']-1+tied): places[k]+=1/tied
   total=sum(s['points'] for s in seats)
   rows.append({'id':entity['id'],'name':entity['name'],'base':sum(s['base'] for s in seats),'penalty':sum(s['penalty'] for s in seats),'carry':0,'total':total,'raw':total,'games':n,'rank':0,'places':places,'avgRank':sum((i+1)*v for i,v in enumerate(places))/n if n else None,'topRate':places[0]/n if n else None,'topTwo':sum(places[:2])/n if n else None,'avoidLast':1-places[3]/n if n else None,'best':max((s['score'] for s in seats),default=None),'avgPoints':sum(s['score'] for s in seats)/n if n else None,'yakuman':None,'last':seats[-1]['points'] if seats else 0,'history':[s['points'] for s in seats]})
  rows.sort(key=lambda x:-x['total'])
  for i,row in enumerate(rows): row['rank']=i+1
  stats[kind]=rows
 snapshots=[]
 for label,sheet,rs,nc,tc,cc in [('常规赛','S3赛程' if season=='S3' else '赛程',range(3,12 if season=='S3' else 11),'F','H',None),('半决赛','S3半决赛' if season=='S3' else 'S2半决赛赛程',range(5,11) if season=='S3' else range(3,9),'F' if season=='S3' else 'G','H','I'),('决赛','S3决赛' if season=='S3' else 'S2决赛',range(5,9) if season=='S3' else range(4,8),'F' if season=='S3' else 'H','H' if season=='S3' else 'I','I' if season=='S3' else 'J')]:
  sf=flat(d[sheet]); rows=[{'name':name(val(sf,f'{nc}{r}')),'total':pt(val(sf,f'{tc}{r}')),'carry':pt(val(sf,f'{cc}{r}')) if cc else None} for r in rs];rows.sort(key=lambda x:-x['total'])
  snapshots.append({'name':label,'rows':rows})
 t={'id':season.lower(),'name':f'欢雀楼超级联赛 {season}','type':'team','season':season,'venue':'欢雀楼','currentStage':'regular','historical':True,'snapshots':snapshots,'stages':[{'id':'regular','name':'常规赛（已导入明细）'}],'teams':teams,'players':players,'results':matches,'schedule':[{'id':m['id'],'stageId':'regular','date':m['date'],'time':'时间未记录','table':m['table'],'number':m['number'],'players':m['seats'],'state':'completed','resultId':m['id']} for m in matches],'statistics':{stage:{'raw':stats,'competitive':stats} for stage in ['all','regular']},'rules':{'name':'历史记录','description':'保留原表 PT，差额原因待核对'},'coverage':'常规赛明细已导入；阶段榜为源表积分快照。个人身份、队伍对应及罚分差异仍在核对，重算榜与源表榜可能不同。役满未采集。'}
 assert len(matches)==(108 if season=='S3' else 80)
 assert sum(r['games'] for r in stats['player'])==len(matches)*4
 # User-confirmed four-game day: source order maps to tables 1..4.
 days=collections.defaultdict(list)
 for m in matches: days[m['date']].append(m)
 for games in days.values():
  if len(games)!=4: continue
  for table,m in enumerate(sorted(games,key=lambda m:m['number']),1):
   m['table']=str(table)
   item=next(s for s in t['schedule'] if s['id']==m['id'])
   item['table']=str(table)
   item['time']='19:30' if table in (1,3) else '21:00'
   item['timeSource']='用户确认的四场比赛日安排'
 t['schedule'].sort(key=lambda s:(s['date'],s['time'],s['table']))
 augment(t,d)
 t['schedule'].sort(key=lambda s:(s['date'],s['time'],s['number']))
 import sys
 sys.path.insert(0,str(ROOT.parents[2]/'application'))
 from league.history_reconciliation import reconcile
 t=reconcile(t)
 out['tournaments'].append(t)
(ROOT/'site/data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('Imported historical preview:',[(t['id'],len(t['results'])) for t in out['tournaments']])
