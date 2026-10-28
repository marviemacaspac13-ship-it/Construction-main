from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import threading
import numpy as np

from app.electrical_grounding import refine_locations, refine_image_locations
from app.electrical_models import ElectricalObservation
from app.schemas import Detection


def observation(identifier='a',box=(100,100,200,200),kind='light_point'):
    return ElectricalObservation(id=identifier,assembly_id=identifier,box_2d=box,device_class=kind)


def anchor(box=(130,120,150,140),sku='CLR02'):
    return Detection(label=sku,bbox=list(box),confidence=.9)


def test_alignment_changes_only_box_and_retains_original_objects():
    before=observation(); original=before.model_dump()
    result=refine_locations([before],[anchor()],1000,1000)
    assert result[0].box_2d==(120,130,140,150)
    assert result[0].model_dump(exclude={'box_2d'})==before.model_dump(exclude={'box_2d'})
    assert before.model_dump()==original


def test_wrong_class_switch_AC_and_distant_candidates_are_unchanged():
    values=[observation(),observation('s',(400,400,420,420),'switch'),
        observation('ac',(700,700,720,720),'ac_outlet')]
    detections=[anchor((120,100,140,120),'OT03'),anchor((800,800,820,820)),
        anchor((400,400,420,420),'SW01'),anchor((700,700,720,720),'ACO01')]
    assert refine_locations(values,detections,1000,1000)==values


def test_two_similarly_near_candidates_remain_ambiguous():
    before=observation(box=(140,140,160,160))
    assert refine_locations([before],[anchor((120,140,140,160)),anchor((160,140,180,160))],1000,1000)==[before]


def test_one_local_anchor_cannot_move_two_proposals_or_add_a_device():
    values=[observation('a',(100,100,200,200)),observation('b',(160,160,180,180))]
    result=refine_locations(values,[anchor((140,140,160,160))],1000,1000)
    assert len(result)==2
    assert sum(a.box_2d!=b.box_2d for a,b in zip(values,result))==1
    assert [o.id for o in result]==['a','b']


def test_alignment_cannot_create_a_new_cross_class_overlap():
    values=[observation(box=(100,100,120,120)),observation('s',(100,125,120,145),'switch')]
    assert refine_locations(values,[anchor((125,100,145,120))],1000,1000)==values


def test_pixel_axes_and_scale_are_converted_independently_for_rectangular_images():
    before=observation(box=(100,100,200,200))
    result=refine_locations([before],[anchor((120,50,140,70),'OT01')],1000,500)
    assert result==[before] # Wrong family cannot relabel a light as an outlet.
    result=refine_locations([before],[anchor((120,50,140,70))],1000,500)
    assert result[0].box_2d==(100,120,140,140)


def test_no_anchors_never_means_a_zero_inventory():
    values=[observation()]
    assert refine_locations(values,[],1000,1000)==values
    assert refine_locations([], [anchor()],1000,1000)==[]


def test_switch_only_or_oversized_image_skips_expensive_optional_matching():
    with patch('app.electrical_grounding.preprocess_image',side_effect=AssertionError('not needed')):
        values=[observation(kind='switch')]
        assert refine_image_locations(b'not-decoded',values,1000,1000)==values
        values=[observation()]
        assert refine_image_locations(b'not-decoded',values,2000,2000)==values


def test_refinement_cannot_hide_a_preexisting_conflicting_duplicate():
    values=[observation('a'),observation('b')]
    values[0].raw_mark='A';values[1].raw_mark='B'
    assert refine_locations(values,[anchor((140,140,160,160))],1000,1000)==values


def test_two_equally_plausible_proposals_cannot_claim_one_local_symbol():
    values=[observation('a',(145,125,155,135)),observation('b',(145,165,155,175))]
    assert refine_locations(values,[anchor((140,140,160,160))],1000,1000)==values


def test_owned_alternative_can_resolve_ambiguity_without_changing_nearest_symbol():
    values=[observation('ambiguous',(146,154,154,162)),
            observation('strong',(140,170,160,190))]
    before=[o.model_dump() for o in values]
    result=refine_locations(values,[anchor((130,140,150,160)),anchor((170,140,190,160))],1000,1000)
    assert result[0].box_2d==(140,130,160,150)
    assert result[1]==values[1]
    assert [o.model_dump() for o in values]==before
    assert [o.model_dump(exclude={'box_2d'}) for o in result]==[o.model_dump(exclude={'box_2d'}) for o in values]


def test_owned_nearest_symbol_never_pushes_a_duplicate_to_a_different_symbol():
    values=[observation('ambiguous',(146,154,154,162)),
            observation('strong',(140,130,160,150))]
    assert refine_locations(values,[anchor((130,140,150,160)),anchor((170,140,190,160))],1000,1000)==values


def test_second_pass_does_not_chain_its_own_claims_into_more_moves():
    values=[observation('a',(146,154,154,162)),observation('b',(146,194,154,202)),
            observation('strong',(140,210,160,230))]
    result=refine_locations(values,[anchor((130,140,150,160)),anchor((170,140,190,160)),
                                    anchor((210,140,230,160))],1000,1000)
    assert result[0]==values[0]
    assert result[1].box_2d==(140,170,160,190)
    assert result[2]==values[2]


def test_second_pass_keeps_similarly_plausible_competitors_unresolved():
    values=[observation('a',(149,156.5,151,157.5)),observation('b',(149,158.5,151,159.5)),
            observation('strong',(140,170,160,190))]
    assert refine_locations(values,[anchor((130,140,150,160)),anchor((170,140,190,160))],1000,1000)==values


def test_second_pass_retains_unresolved_first_pass_competitors():
    values=[observation('competing-a',(77,99,79,101)),observation('competing-b',(75,99,77,101)),
            observation('followup',(99,117,101,119)),observation('strong',(90,130,110,150))]
    assert refine_locations(values,[anchor((90,90,110,110)),anchor((130,90,150,110))],1000,1000)==values


def test_second_pass_cannot_overtake_a_closer_first_pass_claim_after_collision_clears():
    values=[observation('closer',(99,89,101,91)),observation('followup',(99,117,101,119)),
            observation('strong',(90,130,110,150)),observation('outlet',(90,90,110,110),'convenience_outlet')]
    result=refine_locations(values,[anchor((90,90,110,110)),anchor((130,90,150,110)),
                                   anchor((90,120,110,140),'OT01')],1000,1000)
    assert result[:3]==values[:3]
    assert result[3].box_2d==(120,90,140,110)


def test_second_pass_cannot_introduce_a_new_cross_class_collision():
    values=[observation('ambiguous',(146,154,154,162)),observation('strong',(140,170,160,190)),
            observation('switch',(140,130,160,150),'switch')]
    assert refine_locations(values,[anchor((130,140,150,160)),anchor((170,140,190,160))],1000,1000)==values


def test_owned_alternative_does_not_relax_symbol_size_search_distance():
    values=[observation('far',(146,54,154,56)),observation('strong',(140,90,160,110))]
    assert refine_locations(values,[anchor((0,140,20,160)),anchor((90,140,110,160))],1000,1000)==values


def test_matching_worker_limit_holds_until_processing_actually_finishes():
    values=[observation()]
    release=threading.Event();two_entered=threading.Event();lock=threading.Lock();entered=[]
    def preprocess(_):
        with lock:
            entered.append(1)
            if len(entered)>=2:two_entered.set()
        assert release.wait(3)
        return np.zeros((100,100,3),dtype=np.uint8)
    with patch('app.electrical_grounding.preprocess_image',side_effect=preprocess),ThreadPoolExecutor(max_workers=4) as executor:
        first=[executor.submit(refine_image_locations,b'image',values,100,100) for _ in range(2)]
        try:
            assert two_entered.wait(1)
            extra=[executor.submit(refine_image_locations,b'image',values,100,100) for _ in range(2)]
            assert all(future.result(timeout=1)==values for future in extra)
            assert len(entered)==2
        finally:release.set()
        assert all(future.result(timeout=1)==values for future in first)
