"""Permanent management read model, shared by imported and newly created events."""
import copy
from .projection import public_event

def document_for(event):
    source=event.document
    if not source.get('historySnapshot'):return copy.deepcopy(source)
    p=public_event(event)
    d={k:copy.deepcopy(v) for k,v in source.items() if not k.startswith('history')}
    from .domain import initial
    d.setdefault('rules',initial()['rules']);d.setdefault('settlements',[])
    d['teams']=[dict(t,active=t.get('active',True)) for t in p['teams']]
    d['players']=[dict(x,active=x.get('active',True),number=x.get('number',''),teamId=x.get('teamId'),bio=x.get('bio',''),bond=bool(x.get('bond') or x.get('bondStages'))) for x in p['players']]
    d['stages']=[dict(s,locked=False) for s in p['stages']]
    results={m['id']:m for m in p['results']};matches=[];seen=set()
    for scheduled in p.get('schedule',[])+p['results']:
        mid=scheduled.get('resultId') or scheduled['id']
        if mid in seen:continue
        seen.add(mid);m=copy.deepcopy(results.get(mid,scheduled))
        table=m.get('table') or scheduled.get('table') or 'A'
        number=0
        for c in str(table).upper():
            if 'A'<=c<='Z':number=number*26+ord(c)-64
        m.update(number=number or 1,table=table,date=m.get('date') or '',time=m.get('time') or '',
                 state='published' if mid in results or scheduled.get('state')=='completed' else 'cancelled' if scheduled.get('state')=='cancelled' else 'draft',
                 seats=copy.deepcopy(m.get('seats',scheduled.get('players',[]))),readOnly=True,hasResult=mid in results,
                 rule=copy.deepcopy(m.get('correctionRule') or d['rules'][-1]),penalties=m.get('penalties') or [],yakuman=m.get('yakuman') or [])
        matches.append(m)
    d['matches']=matches
    stage=next((s for s in p['stages'] if s['id']==p.get('currentStage')),p['stages'][-1] if p['stages'] else {'id':'all','name':'最终排名'})
    kind='team' if event.kind=='team' else 'player'
    rows=p.get('statistics',{}).get(stage['id'],{}).get('competitive',{}).get(kind,[])
    d['completion']={'standings':{'stageId':stage['id'],'stageName':stage['name'],'kind':kind,'rows':copy.deepcopy(rows)}}
    return d


def update_identity(document,body):
    from .history_roster import update
    from .domain import require,find
    from .roster import update_roster
    from types import SimpleNamespace
    # The permanent command uses the shared roster validation; PT and source snapshots stay intact.
    event=SimpleNamespace(document=document,name='',kind=document['historySnapshot'].get('type','team'))
    adapted=document_for(event)
    kind=body['kind'];entity=find(adapted['teams' if kind=='team' else 'players'],body.get('id'))
    values=dict(body)
    if kind=='player' and not values.get('number') and not entity.get('number'):
        # Legacy missing numbers remain missing until explicitly entered.
        entity['number']='__unassigned__'+entity['id'];values['number']=entity['number']
    if kind=='player' and entity.get('bond'):entity['teamId']=None;values['teamId']=None
    updated=update_roster(adapted,event.kind,kind+'-update',values)
    result=update(document,body)
    saved=find(updated['teams' if kind=='team' else 'players'],body['id'])
    target=find(result['historyCurrent']['teams' if kind=='team' else 'players'],body['id'])
    for key in (['active','color'] if kind=='team' else ['active','bio','teamId','membershipHistory']):
        if key in saved:target[key]=copy.deepcopy(saved[key])
    return result
