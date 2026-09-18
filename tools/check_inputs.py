#!/usr/bin/env python3
"""2-қадамға кіріс дестесі дайын ба — тексереді.

Қолдану: python3 tools/check_inputs.py
"""
import os
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OK, MISS, WARN = "✅", "❌", "⚠️ "


def p(*a):
    return os.path.join(ROOT, *a)


def check_file(path, label, min_bytes=1):
    full = p(path)
    if os.path.exists(full) and os.path.getsize(full) >= min_bytes:
        kb = os.path.getsize(full) / 1024
        return True, f"{OK} {label}  ({kb:.1f} KB)"
    return False, f"{MISS} {label}  — жоқ: {path}"


def check_glob(*patterns, label, need=1):
    """Бірнеше шаблонның кез келгені сәйкес келсе — жарайды."""
    hits = []
    for pat in patterns:
        hits += glob.glob(p(pat))
    hits = sorted(set(hits))
    if len(hits) >= need:
        return True, f"{OK} {label}  ({len(hits)} файл)"
    shown = " не ".join(patterns)
    return False, f"{MISS} {label}  — {len(hits)}/{need}: {shown}"


CHECKS = [
    ("Құжаттар", [
        lambda: check_file("docs/01-donor-mindtoact.md", "Донор досьесі"),
        lambda: check_file("docs/03-master-prompt.md", "Мастер-промпт"),
        lambda: check_file("docs/05-kanal-pasporty.md", "Канал паспорты"),
    ]),
    ("Транскрипт", [
        lambda: check_file("inputs/raw/mindtoact-top.transcript.md",
                           "Тайм-кодты транскрипт", min_bytes=2000),
        lambda: check_file("inputs/raw/mindtoact-top.structure.md",
                           "Құрылым есебі"),
    ]),
    ("Скриншоттар", [
        lambda: check_glob("inputs/screenshots/channel-home.*",
                           "inputs/screenshots/channel-branding*.*",
                           label="Канал брендингі"),
        lambda: check_glob("inputs/screenshots/thumbnails.*", label="Миниатюралар"),
        lambda: check_glob("inputs/screenshots/frame-*.*",
                           label="Видеодан 5 кадр", need=5),
    ]),
]


def main():
    print("\n2-ҚАДАМҒА КІРІС ДЕСТЕСІ\n" + "=" * 46)
    total = ready = 0
    for section, checks in CHECKS:
        print(f"\n{section}:")
        for c in checks:
            ok, msg = c()
            print(f"  {msg}")
            total += 1
            ready += ok

    print("\n" + "=" * 46)
    print(f"Дайын: {ready}/{total}")

    if ready == total:
        print("\n🎉 Десте толық. 2-қадамды бастауға болады:")
        print("   docs/02-kiris-deste.md → «2-қадамды қалай бастау»")
        return 0

    print("\nҚалғанын жинау — бір команда:")
    print("  ./tools/collect.sh")
    return 1


if __name__ == "__main__":
    sys.exit(main())
