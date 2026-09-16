"""Historical bond enrollment is stage-scoped; never transfer prior scores."""
import copy
from .domain import require,find
from .history_correction import effective
from .history_roster import add_player

def register(document,body):
    require(bool(document.get('historySnapshot')),'仅支持历史赛事')
    require(not document.get('archive'),'赛事已归档')
    require(effective(document).get('type')=='team','仅团体赛支持羁绊登记')
    result=copy.deepcopy(document)
    if not body.get('playerId'):
        result=add_player(result,{'name':body.get('name')})
        player_id=effective(result)['players'][-1]['id']
    else:player_id=body['playerId']
    payload=copy.deepcopy(effective(result))
    player=find(payload['players'],player_id);stage=find(payload['stages'],body.get('stageId'));team=find(payload['teams'],body.get('teamId'))
    require(stage['id'] not in player.get('bondStages',{}),'该阶段已登记羁绊，不重复登记或覆盖代表队伍')
    seats=[s for m in payload['results'] if m['stageId']==stage['id'] for s in m['seats'] if s.get('playerId')==player_id]
    require(all(s.get('teamId')==team['id'] for s in seats),'该阶段已有赛果归属不同或未知，请先在历史核证编辑中核对当场队伍；登记不会转移积分')
    player.setdefault('bondStages',{})[stage['id']]=team['id']
    result['historyCurrent']=payload
    return result

def mark(payload):
    """Derived labels follow match identity even after a score correction."""
    players={p['id']:p for p in payload.get('players',[])}
    for m in payload.get('results',[]):
        for s in m['seats']:
            p=players.get(s.get('playerId'),{})
            if 'bondStages' in p:s['bond']=m['stageId'] in p['bondStages'] and p['bondStages'][m['stageId']]==s.get('teamId')
    for stage,metrics in payload.get('statistics',{}).items():
        for kinds in metrics.values():
            for r in kinds.get('player',[]):
                p=players.get(r['id'],{})
                if 'bondStages' in p:r['bond']=bool(p['bondStages']) if stage=='all' else stage in p['bondStages']
    return payload
