# Hướng dẫn cho phiên chat mới — pipeline video手绘 tiếng Việt

Copy nguyên khối bên dưới vào khung chat mới để agent bắt tay làm ngay.

---

## Khối copy-paste mở đầu phiên mới

```text
Bạn đang làm việc trong repo hand-drawn-explainer-video-nikola (Skill video手绘 tiếng Việt).
Nhiệm vụ: sản xuất video stroke-story theo pipeline single-folder. Hãy:
1) Chạy SETUP môi trường theo INSTRUCTIONS_FOR_NEW_CHAT.md (idempotent, bỏ qua bước đã đạt).
2) Với mỗi video tôi yêu cầu: tạo projects/<tên>/ từ projects/_template/, nhận 3 file
   (script.txt, captions.srt, narration audio) từ tôi, chạy:
   python3 scripts/run_project.py --dir projects/<tên>
3) Nếu script thoát mã 2 (thiếu ảnh nguồn): đọc assets/scene-NN.prompt.txt, dùng image model
   sinh ảnh line-art đúng ràng buộc tách nét, lưu vào assets/scene-NN.png rồi chạy lại.
4) Nghiệm thu: mở final.mp4, xem verification.json, kiểm frame cuối và frame biên cảnh;
   báo cáo trung thực lỗi còn tồn tại (không tuyên bố hoàn thành khi check chưa đạt).
5) Commit + push branch hiện tại và mở/cập nhật Pull Request khi tôi yêu cầu đồng bộ.
Không gọi API TTS nào; audio do tôi cung cấp. Không dùng SVG/fade ảnh mạo nhận nét vẽ tay.
```

---

## SETUP môi trường (một lần mỗi sandbox; bỏ qua bước đã đạt)

```bash
cd <repo>
python3 scripts/setup_check.py                      # xem capability hiện tại
python3 vendor/srt-whiteboard-animation/scripts/prepare_env.py   # venv backend (PyAV/OpenCV/...)
# FFmpeg (nếu setup_check báo ffmpeg false):
python3 -m pip install --target /tmp/ffmod imageio-ffmpeg
sudo cp "$(python3 -c "import sys;sys.path.insert(0,'/tmp/ffmod');import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")" /usr/local/bin/ffmpeg
# Font (nếu chưa có): Be Vietnam Pro + Noto CJK
curl -sL -o /tmp/bvp.tar.gz https://codeload.github.com/bettergui/BeVietnamPro/tar.gz/refs/heads/main
tar xzf /tmp/bvp.tar.gz -C /tmp && sudo mkdir -p /usr/local/share/fonts/bevietnampro
sudo cp /tmp/BeVietnamPro-main/fonts/ttf/BeVietnamPro-{Regular,Medium,SemiBold,Bold,Italic}.ttf /usr/local/share/fonts/bevietnampro/
# (chữ Trung cho case cũ, tùy chọn): blob API notofonts/noto-cjk → /usr/local/share/fonts/notocjk/
sudo tee /etc/fonts/fonts.conf >/dev/null <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias><family>Microsoft YaHei</family><prefer><family>Noto Sans CJK SC</family></prefer></alias>
  <alias><family>sans-serif</family><prefer><family>Be Vietnam Pro</family><family>Noto Sans CJK SC</family></prefer></alias>
</fontconfig>
EOF
python3 scripts/stroke_story_preflight.py --report /tmp/preflight.json   # phải passed:true
```

## Quy tắc single-folder

- Mỗi video = 1 thư mục `projects/<tên>/` tự chứa: `script.txt`, `captions.srt`,
  `narration.mp3|.wav|.m4a`, `assets/scene-NN.png` (+ `.prompt.txt`, `.annotation.json`),
  `timeline.json`, `captions.ass`, `final.mp4`.
- Git track: kịch bản, srt, audio, ảnh line-art + text dẫn xuất nhỏ; `final.mp4` lấy qua `/download-workspace`, không commit.
- Git ignore (đã cấu hình): `*.raw`, `projects/*/render/`, `projects/*/frames/`, cache ffmpeg,
  `verification.json`, `contact.jpg`, `stroke-finalize.json`.
- Muốn tinh chỉnh nghệ thuật (đa vùng ngữ nghĩa, keyword layer, hand-height…): sửa
  `assets/scene-NN.annotation.json` / `captions.ass` rồi chạy lại `run_project.py`
  (script không ghi đè annotation/ảnh đã tồn tại).
- Tay vẽ sạch: đặt `assets/drawing-hand.png` trong project để override tay mặc định của
  vendor (bút của asset mặc định có chữ Trung thượng nguồn). Nguồn sạch: giải nén
  `examples/stroke-story/yuefa-sanzhang/editable-project.zip` → `assets/drawing-hand-clean.png`.

## Đồng bộ GitHub

- Luôn làm việc trên branch của phiên (xem `git branch --show-current`); commit file project mới,
  push, rồi `gh pr create --base main` (hoặc push vào branch của PR đang mở).
- Message commit nêu rõ video nào thêm/sửa và kết quả verification (0 errors hoặc lỗi còn lại).
