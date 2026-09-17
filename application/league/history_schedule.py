"""Display historical match order as physical tables, without rewriting source data."""
from collections import defaultdict

def normalize(payload):
    if payload.get('id') not in ('s1','s2','s3'):
        return payload
    days=defaultdict(list)
    for m in payload.get('schedule',[]):
        days[(m.get('stageId'),m.get('date'))].append(m)
    linked={}
    for rows in days.values():
        groups=defaultdict(list)
        for m in rows:
            # Old 1/2 and 3/4 identify two rounds on the same physical table.
            m.setdefault('sourceTable',m.get('table'))
            m['table']={'1':'A','2':'A','3':'B','4':'B','A':'A','B':'A','C':'B','D':'B'}.get(str(m.get('sourceTable')),m.get('table'))
            teams=tuple(sorted(s.get('teamId') or '' for s in m.get('players',[])))
            groups[teams].append(m)
        # Correct round times only when a complete same-day pairing proves them.
        # Incomplete/mixed-date source rows keep their dates and times.
        complete=(len(groups)<=2 and all(len(k)==4 and len(set(k))==4 and '' not in k and len(v)==2 for k,v in groups.items()))
        if complete:
            ordered=sorted(groups.values(),key=lambda group:min(m.get('number',0) for m in group))
            for i,group in enumerate(ordered):
                for j,m in enumerate(sorted(group,key=lambda row:row.get('number',0))):
                    m['table']='AB'[i];m['time']=('19:30','21:00')[j]
        for m in rows:linked[m.get('resultId') or m['id']]=m
    for m in payload.get('results',[]):
        if m['id'] in linked:
            row=linked[m['id']];m['table']=row['table'];m['time']=row['time']
    return payload
