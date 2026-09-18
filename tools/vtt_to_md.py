#!/usr/bin/env python3
"""VTT субтитрін тайм-кодты markdown-ға айналдырады + құрылым есебін жасайды.

Қолдану:
    python3 tools/vtt_to_md.py inputs/raw/donor.en.vtt \
        --info inputs/raw/donor.info.json \
        --out inputs/raw/donor.transcript.md \
        --structure inputs/raw/donor.structure.md

Екі бөлек нәтиже:
  --out        тайм-кодты толық транскрипт. Донордың сөзі — авторлық контент,
               сондықтан inputs/raw/ ішінде қалады, репоға коммит етілмейді.
  --structure  тек өлшемдер: ұзақтық, темп (WPM), хук шекарасы, блок картасы.
               Бұл — өз талдауың, репоға кіре береді.
"""
import argparse
import json
import re
import os

TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
TAG = re.compile(r"<[^>]+>")
# YouTube авто-субтитрлері әр жолды келесі кадрда қайталайды — соны кесеміз.


def secs(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def mmss(t):
    return f"{int(t) // 60:02d}:{int(t) % 60:02d}"


def parse_vtt(path):
    """VTT-ден (start, end, text) кесінділерін алады, қайталауларды тазалайды."""
    cues, start, end, buf = [], None, None, []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = TS.match(line.strip())
            if m:
                if start is not None and buf:
                    cues.append((start, end, " ".join(buf).strip()))
                start = secs(*m.groups()[:4])
                end = secs(*m.groups()[4:])
                buf = []
            elif line.strip() and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                txt = TAG.sub("", line).strip()
                if txt:
                    buf.append(txt)
        if start is not None and buf:
            cues.append((start, end, " ".join(buf).strip()))

    # Қайталанған жолдарды алып таста (авто-субтитрдің «roll-up» әсері).
    clean, seen_tail = [], ""
    for s, e, t in cues:
        if not t or t == seen_tail:
            continue
        if seen_tail and t.startswith(seen_tail):
            t = t[len(seen_tail):].strip()
        if t:
            clean.append((s, e, t))
            seen_tail = t
    return clean


def group(cues, window=30):
    """Кесінділерді `window` секундтық блоктарға жинайды."""
    blocks, cur, bstart = [], [], None
    for s, e, t in cues:
        if bstart is None:
            bstart = s
        if s - bstart >= window and cur:
            blocks.append((bstart, cur[-1][1], " ".join(x[2] for x in cur)))
            cur, bstart = [], s
        cur.append((s, e, t))
    if cur:
        blocks.append((bstart, cur[-1][1], " ".join(x[2] for x in cur)))
    return blocks


def load_info(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return dict(title=d.get("title", ""), channel=d.get("channel", ""),
                views=d.get("view_count"), duration=d.get("duration"),
                upload=d.get("upload_date", ""), url=d.get("webpage_url", ""),
                subs=d.get("channel_follower_count"))


def write_transcript(blocks, info, out):
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Донор транскрипті (тайм-кодпен)\n\n")
        f.write("> ⚠️ Бұл файл — донордың авторлық контенті. Тек жергілікті талдауға.\n")
        f.write("> Репоға коммит етілмейді (`inputs/raw/` .gitignore-да).\n\n")
        for k, v in info.items():
            if v:
                f.write(f"- **{k}**: {v}\n")
        f.write("\n---\n\n")
        for s, e, t in blocks:
            f.write(f"**[{mmss(s)}]** {t}\n\n")
    return out


def write_structure(cues, blocks, info, out):
    dur = info.get("duration") or (cues[-1][1] if cues else 0)
    words = sum(len(t.split()) for _, _, t in cues)
    speech = sum(e - s for s, e, _ in cues) or 1
    wpm = words / (speech / 60)

    # Хук = алғашқы 30 секунд; оның ішінде қанша блок/сөз бар.
    hook_words = sum(len(t.split()) for s, _, t in cues if s < 30)

    with open(out, "w", encoding="utf-8") as f:
        f.write("# Донор видеосының құрылым есебі\n\n")
        f.write("> Тек өлшемдер — донордың мәтіні жоқ, сондықтан репоға кіре береді.\n\n")
        f.write("| Көрсеткіш | Мән |\n|---|---|\n")
        if info.get("title"):
            f.write(f"| Видео | {info['title']} |\n")
        if info.get("channel"):
            f.write(f"| Канал | {info['channel']} |\n")
        if info.get("views"):
            f.write(f"| Қаралым | {info['views']:,} |\n")
        if info.get("upload"):
            f.write(f"| Жүктелген | {info['upload']} |\n")
        f.write(f"| Ұзақтық | {mmss(dur)} ({dur/60:.1f} мин) |\n")
        f.write(f"| Сөз саны | {words:,} |\n")
        f.write(f"| Темп | {wpm:.0f} сөз/мин |\n")
        f.write(f"| Хук (0–30 сек) | {hook_words} сөз |\n")
        f.write(f"| 30-сек блок саны | {len(blocks)} |\n")
        f.write("\n## Блок картасы\n\n")
        f.write("Әр блоктың тайм-коды мен көлемі. Мазмұнды өзің толтырасың —\n")
        f.write("осы кесте видеоның қаңқасын (қанша бөлім, қай жерде ауысады) көрсетеді.\n\n")
        f.write("| # | Басы | Сөз | Тақырыбы (қолмен толтыр) |\n|---|---|---|---|\n")
        for i, (s, e, t) in enumerate(blocks, 1):
            f.write(f"| {i} | {mmss(s)} | {len(t.split())} | |\n")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vtt")
    ap.add_argument("--info")
    ap.add_argument("--out", required=True)
    ap.add_argument("--structure")
    ap.add_argument("--window", type=int, default=30, help="блок ұзақтығы, сек")
    a = ap.parse_args()

    cues = parse_vtt(a.vtt)
    if not cues:
        raise SystemExit("VTT бос немесе оқылмады")
    blocks = group(cues, a.window)
    info = load_info(a.info)

    write_transcript(blocks, info, a.out)
    print(f"✓ транскрипт: {a.out}  ({len(blocks)} блок)")
    if a.structure:
        write_structure(cues, blocks, info, a.structure)
        print(f"✓ құрылым   : {a.structure}")


if __name__ == "__main__":
    main()
