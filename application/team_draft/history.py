"""Explicit cross-event player identities; never match players by display name."""
from league.models import Event, HistoricalArchive, HistoryImport
from league.domain import require
from league.projection import public_event, rank_metrics

def history_options():
    rows=[]
    for event in Event.objects.filter(public=True).order_by('created_at'):
        source=event.document.get('historyCurrent',event.document.get('historySnapshot',event.document))
        rows.append(dict(id=str(event.pk),name=event.name,players=[dict(id=p['id'],name=p['name']) for p in source.get('players',[])]))
    imported=set(HistoryImport.objects.filter(event__public=True).values_list('archive_id',flat=True))
    for archive in HistoricalArchive.objects.filter(public=True).exclude(key__in=imported).order_by('key'):
        source=archive.payload
        rows.append(dict(id='archive:'+archive.key,name=source.get('name',archive.key),players=[dict(id=p['id'],name=p['name']) for p in source.get('players',[])]))
    return rows

def public_source(source_id):
    if source_id.startswith('archive:'):
        archive=HistoricalArchive.objects.filter(key=source_id.split(':',1)[1],public=True).first()
        return rank_metrics(archive.payload) if archive else None
    event=Event.objects.filter(pk=source_id,public=True).first()
    return public_event(event) if event else None

def validate_links(candidates,user):
    options={e['id']:e for e in history_options()}
    result={}
    for candidate in candidates:
        links=candidate.get('historyLinks',[])
        require(isinstance(links,list) and len(links)<=30,'历史身份关联格式错误')
        seen=set();clean=[]
        for link in links:
            require(isinstance(link,dict),'历史身份关联格式错误')
            event=options.get(link.get('eventId'))
            require(event is not None,'历史来源须为已公开赛事')
            pid=link.get('playerId')
            require(any(p['id']==pid for p in event['players']),'历史选手不属于所选赛事')
            require(event['id'] not in seen,'同一历史赛事只能关联一个选手身份')
            seen.add(event['id']);clean.append(dict(eventId=event['id'],playerId=pid))
        result[candidate['playerId']]=clean
    return result

def candidate_history(draft):
    result={};cache={}
    for current,links in (draft or {}).get('historyLinks',{}).items():
        rows=[]
        for link in links:
            eid=link['eventId']
            if eid not in cache:
                cache[eid]=public_source(eid)
            source=cache[eid]
            if not source:continue
            person=next((p for p in source.get('players',[]) if p['id']==link['playerId']),None)
            if not person:continue
            stages=[]
            for stage in source.get('stages',[]):
                stat=next((r for r in source.get('statistics',{}).get(stage['id'],{}).get('raw',{}).get('player',[]) if r['id']==person['id']),None)
                if not stat:continue
                games=stat.get('games')
                total=stat.get('raw',stat.get('total'))
                stages.append(dict(name=stage['name'],games=games,total=total/10 if total is not None else None,average=round(total/10/games,2) if total is not None and games else None,avgRank=stat.get('avgRank')))
            rows.append(dict(eventId=eid,name=source['name'],playerName=person['name'],stages=stages))
        result[current]=rows
    return result
