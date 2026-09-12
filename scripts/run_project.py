#!/usr/bin/env python3
"""Single-folder pipeline cho video stroke-story tiếng Việt (Tuyến 1).

Mỗi video là MỘT thư mục tự chứa (mặc định projects/<tên>/):
  script.txt          kịch bản gốc (UTF-8)
  captions.srt        phụ đề tiếng Việt (nguồn timestamp, không gọi API align)
  narration.mp3/.wav  audio thật (hoặc audio câm khi thử nghiệm)
  assets/scene-NN.png ảnh line-art/illustration nguồn
  final.mp4           thành phẩm 1920x1080

Chạy:
  python scripts/run_project.py --dir projects/video-01
  python scripts/run_project.py --dir projects/video-01 --source-overlay always

Script KHÔNG tự gọi API sinh ảnh hay TTS. Nếu thiếu ảnh nguồn, script viết sẵn
prompt vào assets/scene-NN.prompt.txt và dừng (exit 2) để agent/người dùng sinh
ảnh bằng bất kỳ image model nào (hoặc truyền hook qua biến môi trường
IMAGE_GEN_CMD, ví dụ: IMAGE_GEN_CMD="mytool --prompt {prompt_file} --out {out}").
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "vendor" / "srt-whiteboard-animation"
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
RENDERER = BACKEND / "scripts" / "render_stream_whiteboard.py"
SCHEMA = BACKEND / "scripts" / "annotation_schema.py"
FINALIZE = ROOT / "scripts" / "finalize_stroke_video.py"
MEDIA_CHECK = ROOT / "scripts" / "media_check.py"

WIDTH, HEIGHT, FPS = 1920, 1080, 30
FONT = "Be Vietnam Pro"
TARGET_SCENE_S = 8.0      # nhịp đích mỗi cảnh stroke-story (repo: 4-8s)
MIN_TAIL_SCENE_S = 2.0    # cảnh cụt cuối phim được gộp vào cảnh trước
GAZE_MS = 800             # thời gian ngắm bản vẽ hoàn chỉnh cuối mỗi cảnh
OVERLAY_SPECKLE_PCT = 1.0  # % pixel sai khác mạnh (>50/255) ở frame cuối: ngưỡng bật source-overlay
                           # (đo bằng tỷ lệ pixel lệch cao, KHÔNG dùng sai khác trung bình vì lệch nền
                           #  đồng nhất giữa nền giấy render và nền nguồn sẽ làm nhiễu chỉ số)

PROMPT_TEMPLATE = """SCENE — single coherent scene, visual metaphor only (NO text inside the image): {narrative}

CHARACTER LOCK (verbatim, never shorten or drop, include in every scene prompt):
The character is a chibi girl with a black ink #24251F bob haircut with side-swept fringe, wearing a flat sunflower #F0C541 short-sleeve shirt and flat cobalt #2855C7 trousers, with flat natural skin tone #EDB894, two small vertical-oval ink dot eyes and one tiny horizontal line mouth, about 2.2 heads tall including bob hair, drawn with constant-width blunt ink outlines and completely flat fills.
MEASUREMENT CONVENTION: all pixel figures are measured on a 1360x765 canvas (16:9); body height = top of bob hair to heels; one head unit = top of bob hair to chin; face height is not a head unit.

CHARACTER (copied verbatim from references/style-lock.md):
- One chibi girl; proportions follow the MEASUREMENT CONVENTION above.
- Proportion: 2.2 heads tall including bob hair (locked reference measures 434 px body height and 202 px head unit on a 765 px tall canvas). The face-height count (140 px face, about 3.1 face-heights per body) is recorded only to forbid its use as the head unit.
- Hair: flat ink #24251F bob with side-swept fringe covering the forehead, bob ends curling inward at chin level; the hair is one solid flat shape with no strand lines.
- Eyes: exactly two vertical-oval solid ink dots, each about 10 x 15 px on a 1360 px wide canvas, spaced about 53 px apart at mid-face height; no eyebrows, no lashes, no eye white, no pupil highlight.
- Mouth: one horizontal ink line about 13 x 5 px; never an open mouth, never teeth.
- Ears: one simple C-curve about 16 x 21 px on the visible side only.
- Hands: mitten shapes with no finger separation, except a single extended index finger in pointing poses; feet: plain rounded skin-tone shapes with no shoe detail.
- Expression ceiling: neutral to mildly determined; no anger veins, no sweat drops, no blush, no tears, no gritted teeth.
- Costume lock: sunflower #F0C541 short-sleeve T-shirt with a single neckline line, cobalt #2855C7 long trousers; no patterns, no logos, no buttons, no pockets, no collar.

{layout_block}

FIXED STYLE — the sections below are copied verbatim from references/style-lock.md:

LINE:
- Every contour is a single solid ink stroke in hex #24251F; no colored outlines.
- Stroke width is constant at 6 px on a 1360 px wide canvas (0.44% of frame width); allowed range 6-8 px; 11-14 px only at corner joins and T-intersections.
- Stroke ends are blunt round caps; no taper, no calligraphic thick-thin variation.
- Hand tremor is minimal: a straight run may deviate at most +/-1 px per 100 px of length; no wavy oscillation, no nervous jitter.
- No double contours, no overdrawn sketch lines, no hatching, no cross-hatching, no pencil noise, no dashed or broken lines anywhere.
- Walls and planes are drawn as one single ink line, never as double lines, filled bands or shaded edges.

FILL:
- Every shape is one completely flat color: zero gradients, zero shading, zero highlights, zero cast shadows, zero texture, zero opacity variation.
- Exact palette: paper #F8F6EF (background and interior of open shapes), ink #24251F (outlines, hair, dot eyes, optional trousers), cobalt #2855C7, sunflower #F0C541, tomato #D64B36, plus one flat natural skin tone #EDB894 used only on character skin.
- Per-scene budget: paper and ink always; at most two large fills chosen from cobalt and sunflower; tomato reserved for annotation arrows or circles only, total tomato area at most 0.5% of the frame.
- Fill edges sit exactly on the centerline of the ink outline: no white gap, no halo, no bleed outside the outline.
- Background is 100% paper color: no scenery, no floor line, no horizon, no room, no sky, no wash; measured paper coverage of the locked reference is 87.3% of frame area.

COMPOSITION:
- Canvas aspect exactly 16:9; scene images at least 1920x1080, rendered at the highest resolution the image tool supports.
- If the image tool cannot emit a true 16:9 frame, stop and report to the user; never generate a square image and never stretch one with ffmpeg.
- Negative space: paper coverage at least 85% of frame area in every scene (locked reference measures 87.3%); 35% is the absolute rejection floor, not a target.
- Subtitle safe zone: the bottom 18% of frame height (y >= 82% of height) contains zero non-paper pixels: no stroke, no fill, no arrow tip and no foot may cross into it (locked reference measures 0.000%).
- Subject band: all characters and props sit inside y from 10% to 80% of frame height, with at least 15% paper margin on the left and right edges.
- Maximum 3 props per scene; a wall line with its hole counts as one prop; an annotation arrow counts as one prop.
- Exactly one tomato #D64B36 annotation accent (arrow or circle) per scene, stroke 6-8 px, never labeled.
- One action per scene; no collage, no panel splits, no frames, no borders, no background scenery.

FORBIDDEN: text, letters, numbers, logos, watermark, photorealism, 3D render, glossy shading, gradients, cast shadows, pastel children's-book look, sticker sheet, icon grid, collage, dense small parts, pencil noise.

identical across every image in this series, do not reinterpret

Technical constraints: aspect ratio exactly 16:9 (width = height x 16 / 9); render at the highest resolution the image tool supports and never below 1920x1080; if the tool cannot output a true 16:9 frame, stop and report to the user instead of generating a square or stretched image that ffmpeg would have to distort."""


def clip_words(text: str, limit: int = 240) -> str:
    """Cắt narrative ở ranh giới từ, tối đa `limit` ký tự (không cắt giữa từ)."""
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    end = cut.rfind(" ")
    return (cut[:end] if end > 0 else cut).rstrip()


# Mô tả layout nguyên văn từ mục COMPOSITION LAW của references/style-lock.md.
LAYOUT_DESCRIPTIONS = {
    "A": "Layout A: full-body character offset into the left or right third of the frame; all props on the opposite side; character width at most 45% of frame width.",
    "B": "Layout B: close-up of one object or tool only; no character appears in the frame; the object fills at most 50% of frame width; the single tomato annotation accent may point at it.",
    "C": "Layout C: half-body character cropped at the waist (no legs visible) with one oversized prop on the side opposite the character's facing direction.",
}
LAYOUT_B_NO_CHARACTER = ("Layout B has NO character in the frame; the CHARACTER LOCK sentence is included only "
                         "as a style anchor for line width, palette and fill, and must NOT cause any character "
                         "or body part to be drawn.")


def layout_block(scene_n: int) -> str:
    """Khối layout cụ thể cho cảnh: model không được tự suy ra bố cục."""
    layout = "ABC"[(scene_n - 1) % 3]
    others = [x for x in "ABC" if x != layout]
    block = (f"THIS SCENE USES LAYOUT {layout}. Ignore the rules for layouts {others[0]} and {others[1]}.\n"
             f"{LAYOUT_DESCRIPTIONS[layout]}")
    if layout == "B":
        block += f"\n{LAYOUT_B_NO_CHARACTER}"
    return block


def run(cmd: list[str], desc: str) -> None:
    print(f"── {desc}")
    completed = subprocess.run(cmd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise SystemExit(f"LỖI ở bước: {desc}\n{tail}")


def parse_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[dict] = []
    stamp = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        m = stamp.search("\n".join(lines))
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        joined = "\n".join(lines)
        body = re.sub(r"\s+", " ", joined[m.end():]).strip()
        if body and end > start:
            cues.append({"start": start, "end": end, "text": body})
    if not cues:
        raise SystemExit(f"SRT không có cue hợp lệ: {path}")
    return cues


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"Không phải PNG: {path}")
    w, h = struct.unpack(">II", head[16:24])
    return int(w), int(h)


def audio_duration(path: Path, venv_py: Path) -> float:
    code = "import av,sys; c=av.open(sys.argv[1]); print(float(c.duration)/av.time_base)"
    out = subprocess.run([str(venv_py), "-c", code, str(path)], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"Không đọc được audio {path}: {out.stderr.strip()[-500:]}")
    return float(out.stdout.strip())


def group_scenes(cues: list[dict]) -> list[list[dict]]:
    scenes: list[list[dict]] = [[cues[0]]]
    for cue in cues[1:]:
        if cue["end"] - scenes[-1][0]["start"] > TARGET_SCENE_S:
            scenes.append([cue])
        else:
            scenes[-1].append(cue)
    if len(scenes) > 1 and (scenes[-1][-1]["end"] - scenes[-1][0]["start"]) < MIN_TAIL_SCENE_S:
        scenes[-2].extend(scenes.pop())
    return scenes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", required=True, help="Thư mục project tự chứa, vd: projects/video-01")
    parser.add_argument("--source-overlay", choices=("auto", "never", "always"), default="auto",
                        help="auto: bật fade nguồn cuối màn chỉ khi frame cuối thiếu màu so với nguồn")
    args = parser.parse_args()

    project = Path(args.dir).resolve()
    if not project.is_dir():
        raise SystemExit(f"Thư mục không tồn tại: {project} (tạo từ projects/_template/)")

    script_path = project / "script.txt"
    srt_path = project / "captions.srt"
    audio_path = next((p for p in (project / "narration.mp3", project / "narration.wav", project / "narration.m4a") if p.is_file()), None)
    missing = [p.name for p, ok in ((script_path, script_path.is_file()), (srt_path, srt_path.is_file()), (audio_path or project / "narration.mp3", audio_path is not None)) if not ok]
    if missing:
        raise SystemExit(f"Thiếu file đầu vào trong {project}: {', '.join(missing)}")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("Không thấy ffmpeg trong PATH. Xem INSTRUCTIONS_FOR_NEW_CHAT.md mục SETUP.")
    if not VENV_PY.is_file():
        raise SystemExit("Thiếu venv backend. Chạy: python vendor/srt-whiteboard-animation/scripts/prepare_env.py")

    assets = project / "assets"
    render = project / "render"
    assets.mkdir(exist_ok=True)
    render.mkdir(exist_ok=True)

    cues = parse_srt(srt_path)
    audio_dur = audio_duration(audio_path, VENV_PY)
    duration = round(max(audio_dur, cues[-1]["end"] + 0.2), 3)

    groups = group_scenes(cues)
    scenes: list[dict] = []
    prev_end = 0.0
    for i, group in enumerate(groups, start=1):
        end = duration if i == len(groups) else round(group[-1]["end"], 3)
        scenes.append({
            "n": i,
            "start": prev_end,
            "end": end,
            "caption": " ".join(c["text"] for c in group),
        })
        prev_end = end

    timeline = {
        "duration": duration,
        "audio_duration": round(audio_dur, 3),
        "narration_text": " ".join(c["text"] for c in cues),
        "alignment": "srt_cue_timestamps",
        "scenes": scenes,
    }
    (project / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── ASS phụ đề Be Vietnam Pro (mỗi cue một Dialogue, khớp audio thật) ──
    def ts(value: float) -> str:
        # ASS/Libass dùng H:MM:SS.CS (centi-giây, 2 chữ số) — KHÔNG phải mili-giây.
        cs = int(round(value * 100))
        return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"

    ass_lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {WIDTH}", f"PlayResY: {HEIGHT}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Subtitle,Be Vietnam Pro,56,&H001F2524,&H000000FF,&H00EFF6F8,&H66000000,-1,0,0,0,100,100,0,0,1,3,1,2,120,120,58,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        ass_lines.append(f"Dialogue: 0,{ts(cue['start'])},{ts(cue['end'])},Subtitle,,0,0,0,,{cue['text']}")
    ass_path = project / "captions.ass"
    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")

    # ── Prompt + ảnh nguồn + annotation cho từng cảnh ──
    hook = os.environ.get("IMAGE_GEN_CMD")
    missing_images: list[str] = []
    for scene in scenes:
        idx = f"{scene['n']:02d}"
        image = assets / f"scene-{idx}.png"
        prompt_file = assets / f"scene-{idx}.prompt.txt"
        if not prompt_file.is_file():
            narrative = clip_words(scene["caption"], 240)
            prompt_file.write_text(PROMPT_TEMPLATE.format(narrative=narrative, layout_block=layout_block(scene["n"])),
                                   encoding="utf-8")
        if not image.is_file():
            if hook:
                cmd = hook.replace("{prompt_file}", str(prompt_file)).replace("{out}", str(image))
                run(["sh", "-c", cmd], f"sinh ảnh {image.name} qua IMAGE_GEN_CMD")
            else:
                missing_images.append(str(image))
        if not image.is_file():
            continue
        w, h = png_size(image)
        ann_path = assets / f"scene-{idx}.annotation.json"
        if not ann_path.is_file():  # giữ bản annotation do agent tinh chỉnh nếu đã có
            scene_ms = int(round((scene["end"] - scene["start"]) * 1000))
            reveal_ms = max(1000, scene_ms - GAZE_MS)
            ann = {
                "sceneId": f"{project.name}-scene-{idx}",
                "canvas": {"width": w, "height": h},
                "storyBasis": scene["caption"][:200],
                "sceneDurationMs": scene_ms,
                "elements": [{
                    "id": f"scene-{idx}-full",
                    "label": scene["caption"][:80],
                    "sequence": 1,
                    "narrativeRole": "Vẽ toàn cảnh theo thứ tự nét rồi bổ màu",
                    "subtitle": scene["caption"][:120],
                    "type": "story_island",
                    "region": {"x": 0, "y": 0, "width": w, "height": h},
                    "reveal": {"direction": "top_to_bottom", "startMs": 0, "durationMs": reveal_ms,
                               "maskPaddingPx": 20, "protectedRegions": []},
                    "handPath": {"start": [int(w * 0.3), int(h * 0.3)], "end": [int(w * 0.75), int(h * 0.75)],
                                 "easing": "easeInOut"},
                }],
            }
            ann_path.write_text(json.dumps(ann, ensure_ascii=False, indent=2), encoding="utf-8")

    if missing_images:
        print("THIẾU ẢNH NGUỒN. Prompt đã viết sẵn tại:")
        for path in missing_images:
            print(f"  - {path.replace('.png', '.prompt.txt')}")
        print("Hãy sinh ảnh line-art theo prompt (image model bất kỳ) rồi chạy lại lệnh này.")
        return 2

    # ── Schema check + render + normalize + kiểm tra thiếu màu cuối màn ──
    manifest_scenes: list[dict] = []
    overlay_needed = False
    for scene in scenes:
        idx = f"{scene['n']:02d}"
        image = assets / f"scene-{idx}.png"
        ann = assets / f"scene-{idx}.annotation.json"
        raw = render / f"scene-{idx}.mp4"
        norm = render / f"norm-{idx}.mp4"
        run([str(VENV_PY), str(SCHEMA), str(ann)], f"annotation_schema scene-{idx}")
        hand = assets / "drawing-hand.png"  # override tay vẽ sạch của project (mặc định vendor có chữ Trung trên bút)
        deps = [image, ann] + ([hand] if hand.is_file() else [])
        stale = (not raw.is_file()) or raw.stat().st_mtime < max(p.stat().st_mtime for p in deps)
        if stale:
            cmd = [str(VENV_PY), str(RENDERER), str(image), str(ann), str(raw)]
            if hand.is_file():
                cmd.append(str(hand))
            cmd += ["--ink-path", "skeleton", "--color-fill", "contour-wipe", "--hand-follow", "0.35"]
            run(cmd, f"render nét scene-{idx}")
        if stale or not norm.is_file():
            run([ffmpeg, "-loglevel", "error", "-y", "-i", str(raw),
                 "-vf", f"fps=60,scale={WIDTH}:{HEIGHT}:flags=lanczos,format=yuv420p",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-an", str(norm)],
                f"normalize scene-{idx} về {WIDTH}x{HEIGHT}")
        tail_png = render / f"tail-{idx}.png"
        run([ffmpeg, "-loglevel", "error", "-y", "-sseof", "-0.15", "-i", str(norm),
             "-update", "1", "-frames:v", "1", str(tail_png)], f"trích frame cuối scene-{idx}")
        code = (
            "import sys; from PIL import Image; import numpy as np;"
            "a=np.asarray(Image.open(sys.argv[1]).convert('RGB'),dtype=float);"
            "b=np.asarray(Image.open(sys.argv[2]).convert('RGB').resize((a.shape[1],a.shape[0])),dtype=float);"
            "d=np.abs(a-b).mean(axis=2);"
            "print(round(float((d>50).mean())*100,3))"
        )
        out = subprocess.run([str(VENV_PY), "-c", code, str(tail_png), str(image)], capture_output=True, text=True)
        speckle = float(out.stdout.strip() or "100")
        print(f"   scene-{idx}: speckle frame cuối = {speckle}% (ngưỡng {OVERLAY_SPECKLE_PCT}%)")
        if speckle > OVERLAY_SPECKLE_PCT:
            overlay_needed = True
        manifest_scenes.append({
            "video": f"render/norm-{idx}.mp4",
            "image": f"assets/scene-{idx}.png",
            "durationMs": int(round((scene["end"] - scene["start"]) * 1000)),
        })

    overlay = args.source_overlay
    if overlay == "auto":
        overlay = "always" if overlay_needed else "never"

    manifest = {
        "width": WIDTH, "height": HEIGHT, "fps": FPS,
        "narration": audio_path.name,
        "ass": "captions.ass",
        "scenes": manifest_scenes,
    }
    manifest_path = project / "stroke-finalize.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    output = project / "final.mp4"
    run([sys.executable, str(FINALIZE), "--manifest", str(manifest_path), "--ffmpeg", ffmpeg,
         "--source-overlay", overlay, "--output", str(output)], f"finalize → {output.name} (overlay={overlay})")

    report = project / "verification.json"
    completed = subprocess.run(
        [str(VENV_PY), str(MEDIA_CHECK), "--video", str(output), "--timeline", str(project / "timeline.json"),
         "--report", str(report), "--width", str(WIDTH), "--height", str(HEIGHT), "--fps", str(FPS)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(completed.stdout.strip() or completed.stderr.strip()[-800:])
    data = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    errors = data.get("errors", [])
    silent_expected = errors == ["No audible narration detected."] and data.get("audio_peak", 1) < 0.001
    print(json.dumps({
        "final": str(output),
        "duration": data.get("video_duration"),
        "frames_decoded": data.get("frames_decoded"),
        "errors": errors,
        "warnings": data.get("warnings", []),
        "note": "audio câm có chủ đích" if silent_expected else None,
    }, ensure_ascii=False, indent=2))
    if errors and not silent_expected:
        return 3
    print("HOÀN TẤT: " + str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
