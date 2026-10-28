# Manual labeling pilot

This is a small format and visibility pilot, not a training-ready annotation set.

`door_boxes.csv` contains four approximate boxes around visible doors in two raw PNG tiles. `fixture_boxes.csv` contains three approximate boxes around one toilet and two sinks in a third tile. The fixture shapes were checked directly against the raw raster; [`0486-0013-fixture-review.png`](0486-0013-fixture-review.png) shows the boxes. The `coco_vis` previews were used only as clues for selecting examples; their rendered boxes were not treated as source labels.

The annotations are deliberately marked `exploratory_manual`. They have not been checked by a second reviewer or measured against source COCO coordinates. The samples may come from a small number of source plans, and the door tiles were not exhaustively labeled. Therefore, these files must not be used to train or score a detector. They demonstrate that a human can identify several drawn objects in the raster and record bounding boxes, while leaving open the annotation cost, consistency, class definitions, and source-plan grouping questions.

Doors are adjacent to TRACE's current openings assumption, but not an existing priced symbol class. Before expanding this pilot, define how door/window counts should alter a floor-plan estimate and how to handle clipped or ambiguous openings. For useful training data, annotate every instance in each selected tile and group tiles by original drawing before splitting train and evaluation sets.
