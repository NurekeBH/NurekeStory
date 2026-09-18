#!/usr/bin/env bash
# Донор материалын бір командамен жинайды.
#
# Қолдану:
#   ./tools/collect.sh                                   # MindToAct (әдепкі)
#   ./tools/collect.sh https://www.youtube.com/@BasqaKanal
#   ./tools/collect.sh <канал URL> <slug> --keep-video
#
# Не істейді:
#   1. Каналды өлшейді           → inputs/raw/donor-scan.json
#   2. Ең үздік видеоны табады
#   3. Транскриптін жүктейді     → inputs/raw/<slug>.transcript.md
#   4. Видеодан 5 кадр кеседі    → inputs/screenshots/frame-0{1..5}.png
#   5. Миниатюра торын жасайды   → inputs/screenshots/thumbnails.png
#   6. Каналдың брендингін алады → inputs/screenshots/channel-branding.png
#   7. Дестенің толықтығын тексереді
#
# Керек: yt-dlp, python3, ffmpeg
#   pip3 install yt-dlp && brew install ffmpeg

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/inputs/raw"
SHOTS="$ROOT/inputs/screenshots"
TMP="$RAW/.tmp"

CHANNEL="https://www.youtube.com/@MindToAct"
SLUG="mindtoact-top"
KEEP_VIDEO=0
for arg in "$@"; do
  case "$arg" in
    --keep-video) KEEP_VIDEO=1 ;;
    http*) CHANNEL="$arg" ;;
    *) SLUG="$arg" ;;
  esac
done

ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m⚠\033[0m  %s\n' "$*"; }
die()  { printf '\033[31m✗\033[0m %s\n' "$*"; exit 1; }
step() { printf '\n\033[1m── %s\033[0m\n' "$*"; }

# ── 0. Тәуелділіктер ────────────────────────────────────────────────
step "0/7  Құралдарды тексеру"
command -v python3 >/dev/null || die "python3 жоқ"
command -v yt-dlp  >/dev/null || die "yt-dlp жоқ →  pip3 install yt-dlp"
ok "python3, yt-dlp"

HAVE_FFMPEG=1
if ! command -v ffmpeg >/dev/null; then
  HAVE_FFMPEG=0
  warn "ffmpeg жоқ → кадрлар мен миниатюра торы жасалмайды"
  warn "орнату:  brew install ffmpeg   (сосын осы скриптті қайта қос)"
else
  ok "ffmpeg"
fi

mkdir -p "$RAW" "$SHOTS" "$TMP"

# ── 1. Каналды өлшеу ────────────────────────────────────────────────
step "1/7  Канал өлшенуде: $CHANNEL"
if ! python3 "$ROOT/tools/donor_scan.py" --json "$CHANNEL" > "$RAW/donor-scan.json"; then
  die "скринер істемеді — хендл дұрыс па?"
fi
python3 - "$RAW/donor-scan.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if not d:
    sys.exit("канал деректері бос")
c = d[0]
print(f"  Канал      : {c['channel']}")
print(f"  Жасы       : {c['age_months']} ай   Жазылушы: {c['subs']:,}")
print(f"  ЖЕДЕЛДЕУ   : x{c['acceleration']}" if c['acceleration'] else "  ЖЕДЕЛДЕУ   : n/a")
print(f"  Views/Sub  : {c['views_per_sub']}")
print(f"  Үздік видео: {c['best_views']:,} — {c['best_title'][:60]}")
acc = c['acceleration'] or 0
if acc < 5:
    print(f"\n  ⚠️  ЖЕДЕЛДЕУ x{acc} — критерий x5+. Донор суып қалған болуы мүмкін.")
    print("     Резервті де өлше: ./tools/collect.sh https://www.youtube.com/@SimpleWaysofLife")
PY
BEST_URL=$(python3 -c "import json;print(json.load(open('$RAW/donor-scan.json'))[0]['best_url'])")
ok "Үздік видео: $BEST_URL"

# ── 2. Транскрипт ───────────────────────────────────────────────────
step "2/7  Транскрипт"
if "$ROOT/tools/fetch_transcript.sh" "$BEST_URL" "$SLUG" >/dev/null 2>&1; then
  ok "$RAW/$SLUG.transcript.md"
else
  warn "авто-субтитр алынбады"
  warn "қолмен: YouTube → видео → ...more → Show transcript → көшір →"
  warn "         $RAW/$SLUG.transcript.md"
fi

# ── 3. Видеоны жүктеу (кадр кесу үшін) ──────────────────────────────
VIDEO=""
if [ "$HAVE_FFMPEG" = 1 ]; then
  step "3/7  Видео жүктелуде (480p, кадр кесуге ғана)"
  yt-dlp --no-update -q --no-warnings \
         -f 'bv*[height<=480]/b[height<=480]/b' \
         -o "$RAW/$SLUG.video.%(ext)s" "$BEST_URL" 2>/dev/null
  VIDEO=$(ls -1 "$RAW/$SLUG.video."* 2>/dev/null | head -1)
  [ -n "$VIDEO" ] && ok "$(basename "$VIDEO")" || warn "видео жүктелмеді — кадрлар қолмен керек"
else
  step "3/7  Видео — өткізілді (ffmpeg жоқ)"
fi

# ── 4. 5 кадр ───────────────────────────────────────────────────────
step "4/7  Кадрлар"
if [ -n "$VIDEO" ]; then
  DUR=$(python3 -c "
import json,sys
try: print(int(json.load(open('$RAW/$SLUG.info.json'))['duration']))
except Exception: print(0)")
  if [ "$DUR" -gt 0 ]; then
    i=1
    for PCT in 8 25 45 65 88; do
      T=$(( DUR * PCT / 100 ))
      OUT="$SHOTS/frame-0$i.png"
      if ffmpeg -y -loglevel error -ss "$T" -i "$VIDEO" -frames:v 1 -q:v 2 "$OUT" 2>/dev/null \
         && [ -s "$OUT" ]; then
        printf '  frame-0%d.png  ← %02d:%02d\n' "$i" $((T/60)) $((T%60))
      else
        warn "frame-0$i кесілмеді"
      fi
      i=$((i+1))
    done
    ok "кадрлар видеоның әр жерінен алынды (8%, 25%, 45%, 65%, 88%)"
  else
    warn "ұзақтық білінбеді — кадр кесілмеді"
  fi
else
  warn "видео жоқ — кадрларды қолмен ал (Cmd+Shift+4)"
fi

# ── 5. Миниатюра торы ───────────────────────────────────────────────
step "5/7  Миниатюра торы"
if [ "$HAVE_FFMPEG" = 1 ]; then
  rm -f "$TMP"/thumb-*.jpg 2>/dev/null
  yt-dlp --no-update -q --no-warnings --skip-download \
         --write-thumbnail --convert-thumbnails jpg \
         -I 1:9 -o "$TMP/thumb-%(playlist_index)02d.%(ext)s" \
         "${CHANNEL%/}/videos" 2>/dev/null
  COUNT=$(ls -1 "$TMP"/thumb-*.jpg 2>/dev/null | wc -l | tr -d ' ')
  if [ "$COUNT" -ge 4 ]; then
    ffmpeg -y -loglevel error -start_number 1 -i "$TMP/thumb-%02d.jpg" \
           -vf "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2,tile=3x3" \
           -frames:v 1 "$SHOTS/thumbnails.png" 2>/dev/null \
      && ok "thumbnails.png ($COUNT миниатюра, 3x3 тор)" \
      || warn "тор жасалмады"
  else
    warn "миниатюра жеткіліксіз ($COUNT)"
  fi
else
  warn "өткізілді (ffmpeg жоқ)"
fi

# ── 6. Каналдың брендингі ───────────────────────────────────────────
step "6/7  Канал брендингі (аватар/баннер)"
yt-dlp --no-update -q --no-warnings --skip-download \
       --write-thumbnail --convert-thumbnails png \
       --playlist-items 0 \
       -o "$SHOTS/channel-branding.%(ext)s" "$CHANNEL" 2>/dev/null
if ls "$SHOTS"/channel-branding*.png >/dev/null 2>&1; then
  ok "channel-branding.png"
else
  warn "алынбады — каналдың басты бетін қолмен түсір → channel-home.png"
fi

# ── 7. Тазалау және тексеру ─────────────────────────────────────────
step "7/7  Тексеру"
if [ -n "$VIDEO" ] && [ "$KEEP_VIDEO" = 0 ]; then
  rm -f "$VIDEO"
  ok "видео файлы өшірілді (кадрлар қалды) — сақтау үшін: --keep-video"
fi
rm -rf "$TMP"

echo
python3 "$ROOT/tools/check_inputs.py"
