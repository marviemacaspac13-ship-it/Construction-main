"""Align existing light/outlet proposals; never add counts or infer products."""
from math import hypot
from collections import defaultdict
import threading

from app.electrical_models import box_overlap
from app.vision import template_match
from app.vision.preprocess import preprocess_image

_WORKERS=threading.BoundedSemaphore(2)


def refine_locations(observations, detections, width, height):
    anchors=[]
    for detection in detections:
        family=('light_point' if detection.label in {'CLR01','CLR02','CLR03'} else
                'convenience_outlet' if detection.label in {'OT01','OT02','OT03'} else None)
        if family is None:continue
        x,y,x2,y2=detection.bbox
        if not (0<=x<x2<=width and 0<=y<y2<=height):continue
        anchors.append((family,detection.bbox))
    candidates=[]
    unresolved=[]
    for i,observation in enumerate(observations):
        if observation.device_class not in {'light_point','convenience_outlet'}:continue
        if any(k!=i and box_overlap(observation,other)>.5 for k,other in enumerate(observations)):
            continue
        y,x,y2,x2=observation.box_2d
        cx,cy=(x+x2)*width/2000,(y+y2)*height/2000
        distances=[]
        for j,(family,box) in enumerate(anchors):
            if family!=observation.device_class:continue
            ax,ay,ax2,ay2=box
            distances.append((hypot(cx-(ax+ax2)/2,cy-(ay+ay2)/2),j,max(ax2-ax,ay2-ay)))
        distances.sort()
        if not distances:continue
        distance,j,size=distances[0]
        # Search by symbol size, not page size; leave similarly near alternatives unresolved.
        if distance<=2*size:
            if len(distances)==1 or distances[1][0]>=1.5*max(distance,1):
                candidates.append((distance,i,j))
            else:
                unresolved.append((i,distances))
    refined=list(observations)
    used=set()
    def assign(values):
        competitors=defaultdict(list)
        for distance,_,j in values:competitors[j].append(distance)
        ambiguous=set()
        for j,distances in competitors.items():
            distances.sort()
            if len(distances)>1 and distances[1]<1.5*max(distances[0],1):ambiguous.add(j)
        for _,i,j in sorted(values):
            if j in used or j in ambiguous:continue
            x,y,x2,y2=anchors[j][1]
            original=observations[i]
            adjusted=original.model_copy(update={'box_2d':(y/height*1000,x/width*1000,y2/height*1000,x2/width*1000)})
            # Moving one proposal must not introduce a new same- or cross-class collision.
            if any(k!=i and box_overlap(adjusted,other)>max(.5,box_overlap(original,other))
                   for k,other in enumerate(refined)):
                continue
            refined[i]=adjusted
            used.add(j)
    assign(candidates)
    # Only first-pass ownership can remove an alternative; never change the original nearest.
    locked=set(used)
    first_targets={j for _,_,j in candidates}
    followup=[]
    for i,distances in unresolved:
        distance,j,_=distances[0]
        # A failed or contested first-pass claim still has priority; do not overtake it.
        if j in first_targets:continue
        available=[value for value in distances if value[1] not in locked]
        if len(available)==1 or available[1][0]>=1.5*max(distance,1):
            followup.append((distance,i,j))
    assign(followup)
    return refined


def refine_image_locations(raw, observations, width, height):
    # shortcut: retain native glyph pixels up to 2 MP; larger drawings need tiled grounding.
    if width*height>2_000_000 or not any(o.device_class in {'light_point','convenience_outlet'} for o in observations):
        return observations
    # Keep the slot until real completion, even if the async caller has timed out.
    if not _WORKERS.acquire(blocking=False):return observations
    try:
        image=preprocess_image(raw)
        if image.shape[:2]!=(height,width):return observations
        detections=template_match.match_templates(image)
        if len(detections)>500:return observations
        return refine_locations(observations,detections,width,height)
    finally:
        _WORKERS.release()
