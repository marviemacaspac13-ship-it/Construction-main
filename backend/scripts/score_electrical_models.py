"""Score the frozen development comparison by location and class, not totals."""
import argparse
from collections import Counter
import json
from math import hypot
from pathlib import Path


def center(o,width,height):
    y,x,y2,x2=o['box_2d']
    return ((x+x2)*width/2000,(y+y2)*height/2000)


def score(reference,proposed,width,height,radius):
    # Maximum-cardinality bipartite matching: one proposal cannot cover two devices.
    edges={i:sorted((hypot(center(t,width,height)[0]-center(p,width,height)[0],
                          center(t,width,height)[1]-center(p,width,height)[1]),j)
        for j,p in enumerate(proposed) if t['device_class']==p['device_class']
        and hypot(center(t,width,height)[0]-center(p,width,height)[0],
                  center(t,width,height)[1]-center(p,width,height)[1])<=radius)
        for i,t in enumerate(reference)}
    matched={}
    def assign(i,seen):
        for distance,j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in matched or assign(matched[j],seen):
                matched[j]=i
                return True
        return False
    for i in edges:assign(i,set())
    pairs=[]
    for j,i in sorted(matched.items()):
        tx,ty=center(reference[i],width,height)
        px,py=center(proposed[j],width,height)
        y,x,y2,x2=proposed[j]['box_2d']
        pairs.append(dict(reference_id=reference[i]['id'],proposal_id=proposed[j]['id'],
            distance_px=round(hypot(tx-px,ty-py),2),
            proposal_contains_reference_center=(x*width/1000<=tx<=x2*width/1000 and y*height/1000<=ty<=y2*height/1000)))
    tp=len(pairs)
    return dict(correct=tp,false_or_misplaced=len(proposed)-tp,missed=len(reference)-tp,
        precision=tp/len(proposed) if proposed else 0,recall=tp/len(reference) if reference else 0,
        f1=2*tp/(len(reference)+len(proposed)) if reference or proposed else 0,
        matches=pairs,unmatched_proposal_ids=[p['id'] for j,p in enumerate(proposed) if j not in matched])


def run(directory):
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    result=[]
    reference=manifest['reference'];width=manifest['width'];height=manifest['height']
    primary=manifest['matching_policy']['primary_center_distance_px']
    for model in manifest['models']:
        path=directory/f'{model}.json'
        if not path.exists():
            result.append(dict(model=model,status='not_requested_after_batch_stop'))
            continue
        record=json.loads(path.read_text(encoding='utf-8'));body=record['result']
        row=dict(model=model,elapsed_ms=record['elapsed_ms'],attempts=body['attempts'])
        if not body['available']:
            result.append(dict(**row,status='no_usable_response'))
            continue
        proposed=body['proposed']
        row.update(status='scored_development_only',classes=dict(Counter(p['device_class'] for p in proposed)),
            primary=score(reference,proposed,width,height,primary),
            sensitivity={str(r):score(reference,proposed,width,height,r) for r in manifest['matching_policy']['sensitivity_center_distance_px']},
            by_class={c:score([t for t in reference if t['device_class']==c],
                [p for p in proposed if p['device_class']==c],width,height,primary)
                for c in sorted({t['device_class'] for t in reference}|{p['device_class'] for p in proposed})})
        result.append(row)
    (directory/'location-scores.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    for row in result:
        metrics=row.get('primary',{})
        print(json.dumps(dict(model=row['model'],status=row['status'],seconds=round(row.get('elapsed_ms',0)/1000,2),
            correct=metrics.get('correct'),false_or_misplaced=metrics.get('false_or_misplaced'),missed=metrics.get('missed'),classes=row.get('classes'))))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    run(parser.parse_args().directory)
