import json, pathlib, collections

data=json.loads((pathlib.Path(__file__).parent/'site/data.json').read_text(encoding='utf-8'))
for t in data['tournaments']:
    matches=t['results']
    assert len({m['id'] for m in matches})==len(matches)
    assert {s['id'] for s in t['stages']}=={'regular','semi','final'}
    assert {s['resultId'] for s in t['schedule']}=={m['id'] for m in matches}
    assert sum(r['games'] for r in t['statistics']['all']['raw']['player'])==sum(bool(s['playerId']) for m in matches for s in m['seats'])
    for stage in ['regular','semi','final']:
        ms=[m for m in matches if m['stageId']==stage]
        for kind in ['player','team']:
            for r in t['statistics'][stage]['raw'][kind]:
                seats=[s for m in ms for s in m['seats'] if s[kind+'Id']==r['id']]
                assert r['raw']==sum(s['points'] for s in seats)
                assert r['games']==len(seats)
                if not any(s['rank'] is not None for s in seats): assert r['avgRank'] is None
        if stage!='regular':
            for r in t['statistics'][stage]['competitive']['team']:
                assert r['total']==r['raw']+r['carry']
    if t['id']=='s3':
        assert len([d for d in t['dailySummaries'] if not d['detailAvailable']])==7
        assert sum(r['games'] for r in t['statistics']['final']['raw']['player'])==0
        for r in t['statistics']['final']['competitive']['team']:
            raw=next(x for x in t['statistics']['final']['raw']['team'] if x['id']==r['id'])
            assert raw['raw']==r['raw']
        known=next(m for m in matches if m['id']=='S3-semi-13')
        assert sorted(s['score'] for s in known['seats'])==[-6400,6600,44800,55000]
    else:
        broken=next(m for m in matches if m['id']=='S2-final-3')
        unknown=next(s for s in broken['seats'] if s['playerId'] is None)
        assert unknown['points']==-464
        assert len([m for m in matches if m['stageId']=='semi'])==18
print('Postseason: unique games, stage filters, known-player counts, carry isolation and final team totals verified.')
