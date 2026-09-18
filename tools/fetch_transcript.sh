#!/usr/bin/env bash
# Донордың ең үздік видеосының транскриптін тайм-кодпен жүктейді.
#
# Қолдану:
#   ./tools/fetch_transcript.sh "https://www.youtube.com/watch?v=VIDEO_ID"
#   ./tools/fetch_transcript.sh "<URL>" mindtoact-top
#
# Нәтиже (бәрі inputs/raw/ ішінде — репоға кірмейді, .gitignore-да):
#   <slug>.en.vtt        — шикі субтитр
#   <slug>.info.json     — видео метадеректері
#   <slug>.transcript.md — тайм-кодты транскрипт (2-қадамға осыны саласың)
#   <slug>.structure.md  — құрылым есебі (репоға кіруге жарайды)
#
# Керек: pip install yt-dlp

set -euo pipefail

URL="${1:-}"
SLUG="${2:-donor-top}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/inputs/raw"

if [[ -z "$URL" ]]; then
  echo "Қолдану: $0 <VIDEO_URL> [slug]" >&2
  exit 1
fi

command -v yt-dlp >/dev/null 2>&1 || { echo "yt-dlp жоқ. pip install yt-dlp" >&2; exit 1; }

mkdir -p "$OUT"

echo "→ Транскрипт жүктелуде: $URL"
yt-dlp --no-update \
       --skip-download \
       --write-auto-subs --write-subs \
       --sub-langs "en.*" --sub-format "vtt" \
       --write-info-json \
       -o "$OUT/$SLUG.%(ext)s" \
       "$URL"

VTT="$(ls -1 "$OUT/$SLUG".*.vtt 2>/dev/null | head -1 || true)"
if [[ -z "$VTT" ]]; then
  echo "❌ Субтитр табылмады. Бұл видеода авто-субтитр өшірулі болуы мүмкін." >&2
  echo "   Балама: YouTube-та видео астындағы «Show transcript» → қолмен көшір," >&2
  echo "   немесе: pip install openai-whisper && whisper <audio> --language en" >&2
  exit 2
fi

echo "→ VTT → markdown: $VTT"
python3 "$(dirname "$0")/vtt_to_md.py" "$VTT" \
        --info "$OUT/$SLUG.info.json" \
        --out "$OUT/$SLUG.transcript.md" \
        --structure "$OUT/$SLUG.structure.md"

echo
echo "✅ Дайын:"
echo "   $OUT/$SLUG.transcript.md   ← 2-қадамда Claude Code-қа осыны бер"
echo "   $OUT/$SLUG.structure.md    ← құрылым метрикалары"
