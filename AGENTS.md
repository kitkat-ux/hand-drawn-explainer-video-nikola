# AGENTS.md — luật cho mọi phiên agent làm video trong repo này

Đọc trước khi chạm vào bất cứ thứ gì:
1. [INSTRUCTIONS_FOR_NEW_CHAT.md](INSTRUCTIONS_FOR_NEW_CHAT.md) — pipeline single-folder, khối mở đầu phiên, khối SETUP (hoặc chạy `bash scripts/arena_setup.sh`, idempotent).
2. [references/style-lock.md](references/style-lock.md) + [references/style-reference.png](references/style-reference.png) + [references/character-reference.png](references/character-reference.png) — style ĐÃ KHÓA cho toàn bộ series; `scripts/run_project.py` tự nhúng nó vào mọi prompt.

## Quy tắc cứng cho phiên làm video

- **Mỗi phiên chỉ làm 1 video.** Không nhận video thứ hai trong cùng phiên.
- **Chỉ được ghi file trong `projects/<tên>/`** (kịch bản, srt, audio, assets/, timeline, captions.ass, final.mp4 và các file dẫn xuất nhỏ).
- **Không sửa** `scripts/`, `references/`, `vendor/`, hay bất kỳ file nào ở gốc repo (kể cả file này, `.gitignore`, `preferences.json`).
- **Phát hiện bug ở script/pipeline thì BÁO trong mô tả PR** (triệu chứng, lệnh tái hiện, exit code, log liên quan) — **không tự sửa** trong phiên làm video. Phiên hạ tầng/style-lock chỉ tồn tại khi user yêu cầu tường minh.
- Không gọi API TTS; audio do user cung cấp. Không dùng SVG/fade ảnh mạo nhận nét vẽ tay逐笔.

## Quy trình bắt buộc mỗi phiên (kết quả đính vào mô tả PR)

1. Trước render, với TỪNG cảnh:
   ```bash
   vendor/srt-whiteboard-animation/.venv/bin/python scripts/check_drawable_regions.py \
     projects/<tên>/assets/scene-NN.png projects/<tên>/assets/scene-NN.annotation.json \
     --report projects/<tên>/render/drawable-NN.json
   ```
   Dán tóm tắt errors/warnings của từng cảnh vào mô tả PR.
2. Sau render + finalize:
   ```bash
   vendor/srt-whiteboard-animation/.venv/bin/python scripts/boundary_contact_sheet.py \
     --video projects/<tên>/final.mp4 \
     --checks projects/<tên>/render/boundary-checks.json \
     --output projects/<tên>/render/boundary-contact.png
   ```
   (`boundary-checks.json` gồm `checks[{label,timeMs}]` tại các ranh giới ngữ nghĩa; dán ảnh/tóm tắt vào mô tả PR.)
3. Mở `final.mp4`, đọc `verification.json`, kiểm frame cuối và frame biên cảnh; báo cáo trung thực lỗi còn tồn tại. Không tuyên bố hoàn thành khi check chưa đạt.

## Luật nét vẽ / tốc độ tay

- Cảnh nào tay vẽ quá nhanh (nét hoàn thành sớm hơn hẳn lời thoại): **sinh lại ảnh nguồn ĐƠN GIẢN HƠN** cho cảnh đó (bớt đạo cụ, bớt vùng, nét thưa hơn) rồi chạy lại `run_project.py`.
- **Không rút ngắn nét**, không cắt reveal, không dùng hand-follow để giả nét chậm, không kéo dài thời gian cảnh trái `timeline.json` đã khớp audio.

## Style

- Mọi ảnh nguồn sinh qua prompt mà `scripts/run_project.py` ghi vào `assets/scene-NN.prompt.txt` (đã nhúng FIXED STYLE + CHARACTER LOCK + COMPOSITION LAW + FORBIDDEN từ `references/style-lock.md`).
- Bố cục cảnh theo chu kỳ 3 (A/B/C) trong mục COMPOSITION LAW của style-lock; giữ nguyên CHARACTER LOCK ở mọi cảnh kể cả cảnh không có nhân vật.
- Ảnh nguồn phải đúng 16:9 và ≥1920x1080; công cụ sinh ảnh không ra được 16:9 thì BÁO user, không sinh ảnh vuông rồi kéo méo bằng ffmpeg.

## Đồng bộ GitHub

- Làm việc trên branch của phiên; commit file project mới + push branch đó; mở/cập nhật PR vào `main` khi user yêu cầu đồng bộ.
- Mô tả PR bắt buộc gồm: danh file đổi, kết quả `check_drawable_regions.py` từng cảnh, kết quả `boundary_contact_sheet.py`, trạng thái `verification.json` (0 errors hoặc lỗi còn lại).
- Không tự merge PR.
