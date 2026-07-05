# Rendering & Conversion Guide

Full pipeline for rendering HTML animations to MP4/GIF using Playwright and ffmpeg.

---

## Step 1: Render with Playwright

For each HTML file (EN and HE), render two resolutions using `scripts/capture.mjs`.

### Landscape (1920x1080) — for Twitter/X

```bash
node scripts/capture.mjs \
  social-assets/<TICKET>/animation-en.html 1920 1080 <duration_ms> \
  social-assets/<TICKET>/raw/
```

### Square (1080x1080) — for Instagram

Modify the HTML `body` dimensions to 1080x1080 before recording. You may need to
adjust layout (center content, reduce padding).

```bash
node scripts/capture.mjs \
  social-assets/<TICKET>/animation-en.html 1080 1080 <duration_ms> \
  social-assets/<TICKET>/raw/
```

### All Four Variants

```bash
# English landscape
node scripts/capture.mjs \
  social-assets/<TICKET>/animation-en.html 1920 1080 <duration_ms> \
  social-assets/<TICKET>/raw/

# English square
node scripts/capture.mjs \
  social-assets/<TICKET>/animation-en.html 1080 1080 <duration_ms> \
  social-assets/<TICKET>/raw/

# Hebrew landscape
node scripts/capture.mjs \
  social-assets/<TICKET>/animation-he.html 1920 1080 <duration_ms> \
  social-assets/<TICKET>/raw/

# Hebrew square
node scripts/capture.mjs \
  social-assets/<TICKET>/animation-he.html 1080 1080 <duration_ms> \
  social-assets/<TICKET>/raw/
```

### Alternative: Screenshot Sequence Approach

If video recording is problematic, take screenshots at 30fps intervals then stitch:

```bash
for i in $(seq 0 33 <duration_ms>); do
  npx playwright screenshot \
    --viewport-size="1920,1080" \
    --wait-for-timeout=$i \
    social-assets/<TICKET>/animation-en.html \
    social-assets/<TICKET>/frames/frame-$(printf "%04d" $((i/33))).png
done
```

---

## Step 2: Convert with ffmpeg

Convert Playwright's WebM output to platform-optimized formats.

### MP4 (Twitter/X + Instagram)

```bash
# Landscape MP4 (Twitter/X)
ffmpeg -i social-assets/<TICKET>/raw/<video>.webm \
  -c:v libx264 -pix_fmt yuv420p -preset slow -crf 18 \
  -movflags +faststart -an \
  social-assets/<TICKET>/en-landscape.mp4

# Square MP4 (Instagram)
ffmpeg -i social-assets/<TICKET>/raw/<video-square>.webm \
  -c:v libx264 -pix_fmt yuv420p -preset slow -crf 18 \
  -movflags +faststart -an \
  social-assets/<TICKET>/en-square.mp4
```

### GIF (LinkedIn)

```bash
# Generate palette for quality GIF
ffmpeg -i social-assets/<TICKET>/raw/<video>.webm \
  -vf "fps=15,scale=720:-1:flags=lanczos,palettegen=max_colors=256" \
  -y social-assets/<TICKET>/palette.png

# Render GIF with palette
ffmpeg -i social-assets/<TICKET>/raw/<video>.webm \
  -i social-assets/<TICKET>/palette.png \
  -lavfi "fps=15,scale=720:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5" \
  -y social-assets/<TICKET>/en-landscape.gif
```

Repeat for Hebrew variants (`he-landscape.mp4`, `he-square.mp4`, `he-landscape.gif`).

---

## File Size Check

```bash
# GIF must be < 5MB for LinkedIn
du -h social-assets/<TICKET>/*.gif
```

If GIF exceeds 5MB: reduce fps to 10, scale to 480px width, or shorten duration.

---

## Cleanup

Remove intermediate files after conversion:

```bash
rm -rf social-assets/<TICKET>/raw/ social-assets/<TICKET>/palette.png
```
