#!/usr/bin/env python3
"""Донор канал скринері.

Қолдану:
    python3 tools/donor_scan.py https://www.youtube.com/@HANDLE [...]
    python3 tools/donor_scan.py --json https://www.youtube.com/@HANDLE

Керек: pip install yt-dlp

Әр канал үшін жасын, жүктеу жиілігін, жеделдеуін (соңғы 10 видеоның медианасы /
алғашқы 10-ның медианасы), views/sub қатынасын және аутлаер барын өлшейді.

⚠️ Жаңалық бұрмалауы: соңғы 14 күндік видеолар әлі қаралым жинап үлгермеген.
   Скрипт оларды бөлек көрсетеді — шешім қабылдағанда `жетілген медиана` бағанын ал.
"""
import argparse
import datetime
import json
import statistics
import subprocess
import sys

FIELDS = "%(upload_date)s|%(view_count)s|%(duration)s|%(channel_follower_count)s|%(channel)s|%(id)s|%(title)s"
MATURITY_DAYS = 14


def _run(args, timeout=900):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def fetch(url, rng):
    """Каналдың rng ауқымындағы видеоларының метадеректерін алады."""
    r = _run(["yt-dlp", "--no-update", "--ignore-errors", "-I", rng,
              "--print", FIELDS, url.rstrip("/") + "/videos"])
    rows = []
    for ln in r.stdout.strip().split("\n"):
        p = ln.split("|", 6)
        if len(p) == 7 and p[0].isdigit():
            rows.append(dict(
                date=p[0],
                views=int(p[1]) if p[1].isdigit() else 0,
                dur=int(float(p[2])) if p[2] not in ("NA", "") else 0,
                subs=int(p[3]) if p[3].isdigit() else 0,
                chan=p[4], vid=p[5], title=p[6],
            ))
    return rows


def count_videos(url):
    r = _run(["yt-dlp", "--no-update", "--flat-playlist", "--print", "%(id)s",
              url.rstrip("/") + "/videos"])
    return len([x for x in r.stdout.strip().split("\n") if x.strip()])


def d2(s):
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))


def median(vals):
    vals = list(vals)
    return statistics.median(vals) if vals else 0


def analyse(url):
    today = datetime.date.today()
    total = count_videos(url)
    new = fetch(url, "1:10")
    if not new:
        raise RuntimeError("деректер жоқ (хендл қате ме? жеке канал ма?)")
    old = fetch(url, f"{max(1, total - 9)}:{total}")

    mature = [v for v in new if (today - d2(v["date"])).days >= MATURITY_DAYS]
    fresh = [v for v in new if (today - d2(v["date"])).days < MATURITY_DAYS]

    subs = new[0]["subs"]
    m_new = median(v["views"] for v in (mature or new))
    m_old = median(v["views"] for v in old)
    best = max((v for v in new), key=lambda v: v["views"])
    first = d2(old[-1]["date"]) if old else d2(new[-1]["date"])
    age = (today - first).days
    span = (d2(new[0]["date"]) - d2(new[-1]["date"])).days or 1

    return dict(
        url=url, channel=new[0]["chan"], videos=total, subs=subs,
        age_days=age, age_months=round(age / 30.4, 1), first_video=str(first),
        cadence_per_week=round(len(new) / span * 7, 1),
        median_mature=round(m_new), median_first10=round(m_old),
        mature_sample=len(mature), fresh_excluded=len(fresh),
        acceleration=round(m_new / m_old, 1) if m_old else None,
        views_per_sub=round(m_new / subs, 2) if subs else None,
        best_views=best["views"], best_title=best["title"],
        best_url=f"https://www.youtube.com/watch?v={best['vid']}",
        median_duration_min=round(median(v["dur"] for v in new) / 60, 1),
    )


def flags(d):
    out = []
    if d["age_days"] < 400:
        out.append("жас канал ✓")
    if d["acceleration"] and d["acceleration"] > 5:
        out.append(f"қатты жеделдеген ✓ (x{d['acceleration']})")
    if d["views_per_sub"] and d["views_per_sub"] > 0.3:
        out.append("views/sub > 0.3 ✓")
    if d["median_mature"] and d["best_views"] > 5 * d["median_mature"]:
        out.append("аутлаер бар ✓")
    return out


def report(d):
    print(f"\n{'=' * 68}\n{d['channel']}  ({d['url']})")
    print(f"  Жасы             : {d['age_days']} күн ({d['age_months']} ай), бірінші видео {d['first_video']}")
    print(f"  Видео саны       : {d['videos']}   |  Жазылушы: {d['subs']:,}")
    print(f"  Жүктеу жиілігі   : {d['cadence_per_week']} видео/апта")
    print(f"  Медиана (жетілген): {d['median_mature']:,}  "
          f"[{d['mature_sample']} видео, {d['fresh_excluded']} жаңасы есепке алынбады]")
    print(f"  Медиана (алғашқы): {d['median_first10']:,}")
    print(f"  ЖЕДЕЛДЕУ         : {'x' + str(d['acceleration']) if d['acceleration'] else 'n/a'}")
    print(f"  Views/Sub        : {d['views_per_sub'] if d['views_per_sub'] else 'n/a'}")
    print(f"  Ұзақтық (медиана): {d['median_duration_min']} мин")
    print(f"  Үздік видео      : {d['best_views']:,} — {d['best_title']}")
    print(f"                     {d['best_url']}")
    f = flags(d)
    print(f"  Белгілер         : {', '.join(f) if f else '—'}")


def main():
    ap = argparse.ArgumentParser(description="Донор канал скринері")
    ap.add_argument("urls", nargs="+", help="канал URL-дері")
    ap.add_argument("--json", action="store_true", help="JSON шығару")
    a = ap.parse_args()

    results = []
    for url in a.urls:
        try:
            d = analyse(url)
            results.append(d)
            if not a.json:
                report(d)
        except Exception as e:
            print(f"\n{url}: қате — {e}", file=sys.stderr)
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
