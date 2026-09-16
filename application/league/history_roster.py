"""Historical identity labels change without rewriting any score or membership."""
import copy
from .domain import require, label, find, uid
from .history_correction import effective

def update(document, body):
    require(bool(document.get('historySnapshot')), '仅支持历史赛事')
    require(not document.get('archive'), '赛事已归档')
    kind=body.get('kind');require(kind in ['team','player'], '名单类型错误')
    result=copy.deepcopy(document);payload=copy.deepcopy(effective(document))
    rows=payload['teams' if kind=='team' else 'players'];entity=find(rows,body.get('id'))
    name=label(body.get('name'))
    require(not any(x['id']!=entity['id'] and x['name'].strip().casefold()==name.casefold() for x in rows), '名称重复；如为同一选手，请先核对身份，不直接合并')
    entity['name']=name
    if kind=='player' and 'number' in body:
        number=body['number'];require(isinstance(number,str),'报名编号格式错误')
        if number.strip():
            number=label(number)
            require(not any(x['id']!=entity['id'] and str(x.get('number','')).strip().casefold()==number.casefold() for x in rows),'报名编号重复')
            entity['number']=number
        else:require(not entity.get('number'),'已有报名编号不能清空')
    for metrics in payload.get('statistics',{}).values():
        for kinds in metrics.values():
            for row in kinds.get(kind,[]):
                if row['id']==entity['id']:row['name']=name
    if kind=='player':
        for team in payload['teams']:
            if team.get('coach',{}).get('playerId')==entity['id']:team['coach']['name']=name
    payload['correctionNotice']='名单名称及编号以管理员当前更正为准；原表积分快照保留当时名称，积分和当场归属未改写。'
    result['historyCurrent']=payload
    return result


def add_player(document, body):
    require(bool(document.get('historySnapshot')), '仅支持历史赛事')
    require(not document.get('archive'), '赛事已归档')
    result=copy.deepcopy(document);payload=copy.deepcopy(effective(document))
    name=label(body.get('name'));players=payload['players']
    require(not any(p['name'].strip().casefold()==name.casefold() for p in players),'选手姓名重复，请使用现有选手')
    team_id=body.get('teamId') or None
    require(team_id is None or isinstance(team_id,str),'队伍格式错误')
    if team_id:
        require(payload.get('type')=='team','个人赛不能指定队伍')
        find(payload['teams'],team_id)
    # Legacy rows may have no number. Reserve their existing list positions.
    numbers=[str(p.get('number','')).strip() for p in players]
    numeric=[int(n) for n in numbers if n.isascii() and n.isdecimal()]
    number=str(max([len(players),*numeric],default=0)+1)
    players.append(dict(id=uid(),name=name,number=number,teamId=team_id,bio='历史名单补录'))
    payload['correctionNotice']='历史名单已补充；新增选手须在历史核证编辑中关联对应赛果后计入成绩，原表及当场归属保留。'
    result['historyCurrent']=payload
    return result
