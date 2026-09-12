# STYLE LOCK — natural-skin chibi editorial line-art (locked 2026-09-12)

Locked reference artifacts:
- `references/style-reference.png` — scene reference (1360x765, 16:9).
- `references/character-reference.png` — four-pose character sheet of the same character.

MEASUREMENT CONVENTION (applies to every number in this file and to every future check):
- All pixel figures are measured on a 1360x765 canvas (16:9); scale linearly for other resolutions.
- Body height = from the top of the bob hair to the heels.
- One "head unit" = from the top of the bob hair to the chin; the bob hair IS part of the head unit.
- Face height (hairline fringe to chin) is NOT a head unit and must never be used as one.

## Line

- Every contour is a single solid ink stroke in hex #24251F; no colored outlines.
- Stroke width is constant at 6 px on a 1360 px wide canvas (0.44% of frame width); allowed range 6-8 px; 11-14 px only at corner joins and T-intersections.
- Stroke ends are blunt round caps; no taper, no calligraphic thick-thin variation.
- Hand tremor is minimal: a straight run may deviate at most +/-1 px per 100 px of length; no wavy oscillation, no nervous jitter.
- No double contours, no overdrawn sketch lines, no hatching, no cross-hatching, no pencil noise, no dashed or broken lines anywhere.
- Walls and planes are drawn as one single ink line, never as double lines, filled bands or shaded edges.

## Fill

- Every shape is one completely flat color: zero gradients, zero shading, zero highlights, zero cast shadows, zero texture, zero opacity variation.
- Exact palette: paper #F8F6EF (background and interior of open shapes), ink #24251F (outlines, hair, dot eyes, optional trousers), cobalt #2855C7, sunflower #F0C541, tomato #D64B36, plus one flat natural skin tone #EDB894 used only on character skin.
- Per-scene budget: paper and ink always; at most two large fills chosen from cobalt and sunflower; tomato reserved for annotation arrows or circles only, total tomato area at most 0.5% of the frame.
- Fill edges sit exactly on the centerline of the ink outline: no white gap, no halo, no bleed outside the outline.
- Background is 100% paper color: no scenery, no floor line, no horizon, no room, no sky, no wash; measured paper coverage of the locked reference is 87.3% of frame area.

## Character

- One chibi girl; proportions follow the MEASUREMENT CONVENTION above.
- Proportion: 2.2 heads tall including bob hair (locked reference measures 434 px body height and 202 px head unit on a 765 px tall canvas). The face-height count (140 px face, about 3.1 face-heights per body) is recorded only to forbid its use as the head unit.
- Hair: flat ink #24251F bob with side-swept fringe covering the forehead, bob ends curling inward at chin level; the hair is one solid flat shape with no strand lines.
- Eyes: exactly two vertical-oval solid ink dots, each about 10 x 15 px on a 1360 px wide canvas, spaced about 53 px apart at mid-face height; no eyebrows, no lashes, no eye white, no pupil highlight.
- Mouth: one horizontal ink line about 13 x 5 px; never an open mouth, never teeth.
- Ears: one simple C-curve about 16 x 21 px on the visible side only.
- Hands: mitten shapes with no finger separation, except a single extended index finger in pointing poses; feet: plain rounded skin-tone shapes with no shoe detail.
- Expression ceiling: neutral to mildly determined; no anger veins, no sweat drops, no blush, no tears, no gritted teeth.
- Costume lock: sunflower #F0C541 short-sleeve T-shirt with a single neckline line, cobalt #2855C7 long trousers; no patterns, no logos, no buttons, no pockets, no collar.

## Composition

- Canvas aspect exactly 16:9; scene images at least 1920x1080, rendered at the highest resolution the image tool supports.
- If the image tool cannot emit a true 16:9 frame, stop and report to the user; never generate a square image and never stretch one with ffmpeg.
- Negative space: paper coverage at least 85% of frame area in every scene (locked reference measures 87.3%); 35% is the absolute rejection floor, not a target.
- Subtitle safe zone: the bottom 18% of frame height (y >= 82% of height) contains zero non-paper pixels: no stroke, no fill, no arrow tip and no foot may cross into it (locked reference measures 0.000%).
- Subject band: all characters and props sit inside y from 10% to 80% of frame height, with at least 15% paper margin on the left and right edges.
- Maximum 3 props per scene; a wall line with its hole counts as one prop; an annotation arrow counts as one prop.
- Exactly one tomato #D64B36 annotation accent (arrow or circle) per scene, stroke 6-8 px, never labeled.
- One action per scene; no collage, no panel splits, no frames, no borders, no background scenery.

## CHARACTER LOCK

The sentence below is the character identity law. It must appear verbatim, in full, in the prompt of EVERY scene of every video produced under this lock; it must never be shortened, paraphrased or dropped, including scenes where the character does not appear.

The character is a chibi girl with a black ink #24251F bob haircut with side-swept fringe, wearing a flat sunflower #F0C541 short-sleeve shirt and flat cobalt #2855C7 trousers, with flat natural skin tone #EDB894, two small vertical-oval ink dot eyes and one tiny horizontal line mouth, about 2.2 heads tall including bob hair, drawn with constant-width blunt ink outlines and completely flat fills.

## COMPOSITION LAW

- The layout cycle repeats every 3 scenes, chosen by scene index modulo 3 (scene-01 = A, scene-02 = B, scene-03 = C, scene-04 = A, and so on).
- Layout A: full-body character offset into the left or right third of the frame; all props on the opposite side; character width at most 45% of frame width.
- Layout B: close-up of one object or tool only; no character appears in the frame; the object fills at most 50% of frame width; the single tomato annotation accent may point at it.
- Layout C: half-body character cropped at the waist (no legs visible) with one oversized prop on the side opposite the character's facing direction.
- Every layout keeps the CHARACTER LOCK sentence, the palette, the stroke width and the subtitle safe zone unchanged; Layout B still carries the CHARACTER LOCK sentence in its prompt so any body part that appears stays identical.
