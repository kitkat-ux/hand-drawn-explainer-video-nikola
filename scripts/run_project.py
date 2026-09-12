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
TARGET_SCENE_S = 6.0      # nhịp đích mỗi cảnh stroke-story (repo: 4-8s)
MIN_TAIL_SCENE_S = 2.0    # cảnh cụt cuối phim được gộp vào cảnh trước
GAZE_MS = 800             # thời gian ngắm bản vẽ hoàn chỉnh cuối mỗi cảnh
OVERLAY_SPECKLE_PCT = 1.0  # % pixel sai khác mạnh (>50/255) ở frame cuối: ngưỡng bật source-overlay
                           # (đo bằng tỷ lệ pixel lệch cao, KHÔNG dùng sai khác trung bình vì lệch nền
                           #  đồng nhất giữa nền giấy render và nền nguồn sẽ làm nhiễu chỉ số)

PROMPT_TEMPLATE = """16:9 minimalist hand-drawn storybook illustration on warm white paper (#F8F6EF).
Single coherent scene, visual metaphor only (NO text inside the image): {narrative}
Sparse clean dark ink outlines, limited flat colors (cobalt blue, sunflower yellow, at most one tomato-red accent),
very low texture, generous negative space, keep the bottom 18% of the frame empty for subtitles.
No text, no letters, no numbers, no logos, no hatching, no photorealism, no dense small parts."""


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
        "Style: Subtitle,Be Vietnam Pro,48,&H001F2524,&H000000FF,&H00EFF6F8,&H66000000,-1,0,0,0,100,100,0,0,1,3,1,2,120,120,58,1",
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
            narrative = scene["caption"][:160]
            prompt_file.write_text(PROMPT_TEMPLATE.format(narrative=narrative), encoding="utf-8")
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
