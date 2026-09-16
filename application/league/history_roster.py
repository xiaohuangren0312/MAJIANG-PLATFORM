"""Historical identity labels change without rewriting any score or membership."""
import copy
from .domain import require, label, find
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
