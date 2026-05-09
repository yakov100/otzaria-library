#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ניקוי_דטרמיניסטי.py — שלב 5.2 בתוכנית האוטומציה (dicta-automation-plan.md).

מריץ ניקוי אחיד וללא AI על קבצי TXT שיצאו משלב החילוץ של דיקטה,
לפני שהקובץ נשלח לסקריפטים שמייצרים כותרות / לעורך אנושי / ל-LLM.

מטפל בבעיות הבאות (לפי מספור בטבלה 3 שבתוכנית):
  B — שורות שמפוצלות סביב <b>...</b>: ממזג שורה שמתחילה ב-<b> אל השורה
      הקודמת אם זו לא נגמרת בנקודה / נקודותיים / סימן סיום אחר.
  E — <b>X</b> דבוק לאות עברית בלי רווח (הדגשה בטעות באמצע מילה):
      מסיר את התגים סביב הפיסה.
  F — שורה יתומה שכל תוכנה <b>ע"א</b> / <b>ע"ב</b> וכד':
      ממזגת לשורה הקודמת (כדי שלא תיוותר כשורה ערומה לפני יצירת כותרות).
  G — נירמול תווים: BOM, רוחבים אפסיים, סימני RTL/LTR בלתי-נראים, טאבים,
      רווחים כפולים, רווחים בסוף שורה. מבוצע unicodedata.normalize("NFC").
  H — קישוטי דיקטה: <b>ל"ה</b> / <b>ל"ו</b> וכו' (ראשי-תיבות מדומים
      שדיקטה הוסיפה לפני מספרי דפים) — מסיר את התגים סביב הצירוף אם
      הוא לבדו בשורה ומתאים לתבנית גימטריה (שייך לטיפול בכותרות-דף לאחר מכן).

שימוש:
  python3 ניקוי_דטרמיניסטי.py FILE [FILE ...]
  python3 ניקוי_דטרמיניסטי.py --dir PATH [--glob "*.txt"]
  python3 ניקוי_דטרמיניסטי.py FILE --skip B,H --json
  python3 ניקוי_דטרמיניסטי.py FILE --dry-run

קוד יציאה:
  0 = הצלחה (גם אם לא היו שינויים)
  2 = שגיאה (קלט שגוי / IO)

המרה idempotent: הרצה שנייה על קובץ כבר נקי לא תשנה דבר.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ----------------------------------------------------------------------------
# קבועים ותבניות
# ----------------------------------------------------------------------------

# תווים בלתי-נראים שיש להסיר (BOM, ZWJ/ZWNJ, סימני כיווניות, סימוני
# טקסט-בלתי-נראה למיניהם). רווחים אמיתיים ומיוחדים מומרים לרווח רגיל.
_INVISIBLE_DROP = "".join([
    "﻿",  # BOM
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZWNJ
    "‍",  # ZWJ
    "‎",  # LRM
    "‏",  # RLM
    "‪", "‫", "‬", "‭", "‮",  # LRE/RLE/PDF/LRO/RLO
    "⁦", "⁧", "⁨", "⁩",  # LRI/RLI/FSI/PDI
    "­",  # SOFT HYPHEN
])
_INVISIBLE_RE = re.compile(f"[{re.escape(_INVISIBLE_DROP)}]")

# רווחים מיוחדים שממירים לרווח רגיל
_SPACE_LIKE_RE = re.compile(r"[\t  -   　]")

# שורה שמתחילה ב-<b>...</b> (יכולים לבוא רווחים בהתחלה, התג עוטף את האות
# העברית הראשונה — אופייני לפלט דיקטה)
_BOLD_LEAD_RE = re.compile(r"^\s*<b>(?P<first>[^<>\n]+)</b>")

# מילים שכשהן מופיעות מודגשות בתחילת שורה הן כמעט תמיד מסמן כותרת/דף
# וסקריפטי יצירת הכותרות (CreateHeadersOtZria, page-b וכד') מצפים שהן
# יישארו כשורה נפרדת. לא ממזגים שורה כזו לקודמתה גם אם לא הייתה נקודה.
_HEADING_TRIGGERS = {
    "פרק", "סימן", "סעיף", "דף", "מסכת", "פתיחה", "הקדמה", "הקדמת",
    "אות", "סי'", "סי", "פ'", "ס'", "מבוא", "חלק", "ספר", "פתחי",
    "שער", "מאמר", "תשובה", "שאלה", "קונטרס",
}
_AYIN_FORMS = {'ע"א', 'ע"ב', "ע'א", "ע'ב", "ע״א", "ע״ב", "עמוד"}

# סימני סוף משפט (אם השורה הקודמת מסתיימת באלה — לא ממזגים B)
_SENTENCE_END = (".", ":", "!", "?", "׃", ";", ")", "]", "}")
# תגים סוגרים שאחריהם נחשב סוף-משפט (סוף כותרת, סוף הדגשה גדולה וכד')
_CLOSING_TAGS = ("</h1>", "</h2>", "</h3>", "</h4>", "</h5>", "</h6>",
                 "</big>", "</small>")

# צורות "ע\"א" / "ע\"ב" (כולל גרשיים בודדים, מקפים שונים, רווחים)
_AYIN_AB_RE = re.compile(
    r'^\s*(?:<b>\s*)?'
    r'(?:ע["\'״׳]+?[אב]|עמוד\s+[אב])'
    r'\s*(?:</b>\s*)?[\.,:]?\s*$'
)

# מילה / שתיים בודדות בתוך <b>...</b> בלבד (שורה שכל תוכנה הדגשה)
_BOLD_ONLY_LINE_RE = re.compile(r"^\s*(?:<b>[^<>\n]+</b>\s*){1,3}$")

# גימטריה לעמוד: 1–2 אותיות, אופציונלי גרשיים, אופציונלי אות נוספת.
# מטרה: לזהות "<b>ל\"ה</b>" / "<b>קי\"א</b>" כעמוד-מדומה.
_GEMATRIA_PAGE_RE = re.compile(
    r'^\s*<b>\s*[א-ת]{1,3}["\'״׳]?[א-ת]?\s*</b>\s*$'
)

# E: <b>X</b> דבוק לאות עברית מצד כלשהו ללא רווח (הדגשה בתוך מילה).
# נתפוס רק כשמדובר באות-בודדת או 2-3 בתוך התג, כדי לא לפגוע בהדגשות אמיתיות
# של מילים שלמות שנדבקו לסימן פיסוק.
_MIDWORD_BOLD_RE = re.compile(
    r'(?P<before>[א-ת])'
    r'<b>(?P<inner>[א-ת]{1,3})</b>'
    r'(?P<after>[א-ת])'
)


# ----------------------------------------------------------------------------
# תוצאות
# ----------------------------------------------------------------------------

@dataclass
class FileReport:
    file: str
    changed: bool = False
    counts: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)
    error: str | None = None


def _bump(report: FileReport, key: str, n: int = 1) -> None:
    if n:
        report.counts[key] = report.counts.get(key, 0) + n


# ----------------------------------------------------------------------------
# G — נירמול תווים
# ----------------------------------------------------------------------------

def fix_g_normalize(text: str, report: FileReport) -> str:
    original = text
    # NFC
    nfc = unicodedata.normalize("NFC", text)
    if nfc != text:
        _bump(report, "G_nfc_normalized", 1)
        text = nfc
    # תווים בלתי-נראים
    new = _INVISIBLE_RE.sub("", text)
    if new != text:
        _bump(report, "G_invisible_removed",
              len(text) - len(new))
        text = new
    # רווחים מיוחדים → רווח רגיל
    new = _SPACE_LIKE_RE.sub(" ", text)
    if new != text:
        _bump(report, "G_special_spaces_collapsed",
              sum(1 for _ in _SPACE_LIKE_RE.finditer(text)))
        text = new
    # רווחים בסוף שורה + רווחים כפולים בתוך שורה
    fixed_lines = []
    trailing = 0
    multi = 0
    for ln in text.splitlines():
        stripped = re.sub(r" {2,}", " ", ln.rstrip())
        if stripped != ln:
            if ln.rstrip() != ln:
                trailing += 1
            if " " * 2 in ln:
                multi += 1
        fixed_lines.append(stripped)
    text = "\n".join(fixed_lines)
    _bump(report, "G_trailing_ws_lines", trailing)
    _bump(report, "G_double_spaces_lines", multi)
    if text != original:
        report.changed = True
    return text


# ----------------------------------------------------------------------------
# E — הסרת <b>...</b> שדבוק באמצע מילה
# ----------------------------------------------------------------------------

def fix_e_midword_bold(text: str, report: FileReport) -> str:
    count = 0

    def _repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return m.group("before") + m.group("inner") + m.group("after")

    new = _MIDWORD_BOLD_RE.sub(_repl, text)
    # החלה חוזרת — תיקון מקרים שחפפו (כי כל החלפה צורכת תו מצד שמאל וימין)
    while True:
        nxt = _MIDWORD_BOLD_RE.sub(_repl, new)
        if nxt == new:
            break
        new = nxt
    if count:
        _bump(report, "E_midword_bold_unwrapped", count)
        report.changed = True
    return new


# ----------------------------------------------------------------------------
# H — הסרת תגי <b> מסביב לראשי-תיבות מדומים בשורה בודדת (שייך לתהליך
# יצירת כותרות-דף; פה רק מסירים את התג כדי שהאיתור הבא יעבוד).
# ----------------------------------------------------------------------------

def fix_h_fake_bold_pages(text: str, report: FileReport) -> str:
    out_lines = []
    count = 0
    for ln in text.splitlines():
        m = _GEMATRIA_PAGE_RE.match(ln)
        if m:
            inner = re.sub(r"</?b>", "", ln).strip()
            out_lines.append(inner)
            count += 1
        else:
            out_lines.append(ln)
    if count:
        _bump(report, "H_fake_bold_pages_unwrapped", count)
        report.changed = True
    return "\n".join(out_lines)


# ----------------------------------------------------------------------------
# B — מיזוג שורות שמתחילות ב-<b> אל השורה הקודמת
# ----------------------------------------------------------------------------

def _ends_sentence(line: str) -> bool:
    s = line.rstrip()
    if not s:
        return True  # שורה ריקה = גבול בין פסקאות
    if s.endswith(_SENTENCE_END):
        return True
    for tag in _CLOSING_TAGS:
        if s.endswith(tag):
            return True
    return False


def _is_protected_line(line: str) -> bool:
    """שורה שאסור למזג אליה או ממנה (כותרות / שורת מחבר / שורה ריקה)."""
    s = line.strip()
    if not s:
        return True
    # כותרת קיימת
    if re.match(r"^<h[1-6]>", s):
        return True
    return False


def fix_b_merge_bold_continuations(text: str, report: FileReport) -> str:
    lines = text.splitlines()
    if len(lines) < 3:
        return text

    # שמירה על שורה 1 (שם הספר / <h1>) ושורה 2 (שם המחבר) ללא שינוי
    # כפי שמובטח ע"י סקריפט המיזוג של דיקטה.
    head = lines[:2]
    body = lines[2:]

    merged: list[str] = []
    count = 0
    for ln in body:
        if not merged:
            merged.append(ln)
            continue
        prev = merged[-1]
        if _is_protected_line(prev) or _is_protected_line(ln):
            merged.append(ln)
            continue
        m = _BOLD_LEAD_RE.match(ln)
        if not m:
            merged.append(ln)
            continue
        if _ends_sentence(prev):
            merged.append(ln)
            continue
        first_word = m.group("first").strip()
        # אל תמזג שורה שמתחילה במילת-טריגר של כותרת או בסימן עמוד
        if first_word in _HEADING_TRIGGERS or first_word in _AYIN_FORMS:
            merged.append(ln)
            continue
        # מיזוג: השורה הנוכחית נדבקת לקודמת עם רווח
        merged[-1] = prev.rstrip() + " " + ln.lstrip()
        count += 1

    if count:
        _bump(report, "B_bold_continuations_merged", count)
        report.changed = True
        return "\n".join(head + merged)
    return text


# ----------------------------------------------------------------------------
# F — מיזוג ע"א / ע"ב יתום לשורה הקודמת
# ----------------------------------------------------------------------------

def fix_f_orphan_ayin(text: str, report: FileReport) -> str:
    lines = text.splitlines()
    if len(lines) < 3:
        return text

    head = lines[:2]
    body = lines[2:]
    out: list[str] = []
    count = 0

    for ln in body:
        if _AYIN_AB_RE.match(ln) and out and not _is_protected_line(out[-1]):
            # הוצא את הצירוף בלי תגים ובלי פיסוק עוטף
            inner = re.sub(r"</?b>", "", ln).strip(" .,:")
            out[-1] = out[-1].rstrip() + " " + inner
            count += 1
            continue
        out.append(ln)

    if count:
        _bump(report, "F_orphan_ayin_merged", count)
        report.changed = True
        return "\n".join(head + out)
    return text


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

# סדר ההפעלה: G קודם (מנקה רעש שיכול לבלבל את התבניות),
# אחר כך E ו-H (מסירים תגים שגויים), ואז F ו-B (מיזוגי שורות).
PIPELINE = [
    ("G", fix_g_normalize),
    ("E", fix_e_midword_bold),
    ("H", fix_h_fake_bold_pages),
    ("F", fix_f_orphan_ayin),
    ("B", fix_b_merge_bold_continuations),
]


def clean_text(text: str, skip: set[str] | None = None,
               report: FileReport | None = None) -> tuple[str, FileReport]:
    if report is None:
        report = FileReport(file="<memory>")
    skip = skip or set()
    for name, fn in PIPELINE:
        if name in skip:
            report.skipped.append(name)
            continue
        text = fn(text, report)
    return text, report


def process_file(path: Path, skip: set[str], dry_run: bool) -> FileReport:
    report = FileReport(file=str(path))
    if not path.exists():
        report.error = f"הקובץ לא נמצא: {path}"
        return report
    if path.suffix.lower() != ".txt":
        report.error = "סוג הקובץ אינו נתמך - נדרש .txt"
        return report
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error = f"קריאה נכשלה: {exc}"
        return report

    cleaned, _ = clean_text(original, skip=skip, report=report)

    if cleaned != original and not dry_run:
        try:
            path.write_text(cleaned, encoding="utf-8")
        except OSError as exc:
            report.error = f"כתיבה נכשלה: {exc}"
            return report
    return report


def _iter_targets(args: argparse.Namespace) -> list[Path]:
    targets: list[Path] = []
    for f in args.files:
        targets.append(Path(f))
    if args.dir:
        d = Path(args.dir)
        if not d.exists():
            sys.stderr.write(f"שגיאה: הספרייה לא קיימת: {d}\n")
            sys.exit(2)
        targets.extend(sorted(d.rglob(args.glob)))
    return targets


def _format_human(report: FileReport) -> str:
    if report.error:
        return f"[שגיאה] {report.file} :: {report.error}"
    if not report.changed:
        return f"[ללא שינוי] {report.file}"
    parts = [f"{k}={v}" for k, v in sorted(report.counts.items()) if v]
    return f"[נוקה] {report.file} :: " + ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="ניקוי דטרמיניסטי לקבצי TXT של דיקטה (שלב 5.2 בתוכנית)."
    )
    p.add_argument("files", nargs="*", help="קבצי TXT לניקוי")
    p.add_argument("--dir", help="ספרייה — מעבד רקורסיבית את כל הקבצים בה")
    p.add_argument("--glob", default="*.txt",
                   help='תבנית קבצים בתוך --dir (ברירת מחדל: "*.txt")')
    p.add_argument("--skip", default="",
                   help="רשימת תווים מופרדי-פסיק של שלבים לדלג עליהם "
                        "(אפשרויות: B,E,F,G,H)")
    p.add_argument("--dry-run", action="store_true",
                   help="רק דיווח, ללא שמירה")
    p.add_argument("--json", action="store_true",
                   help="פלט JSON ל-stdout (אחת לקובץ או רשימה כוללת)")
    args = p.parse_args(argv)

    targets = _iter_targets(args)
    if not targets:
        sys.stderr.write("שגיאה: לא צוינו קבצים. השתמש ב-FILE או --dir\n")
        return 2

    skip = {s.strip().upper() for s in args.skip.split(",") if s.strip()}
    unknown = skip - {n for n, _ in PIPELINE}
    if unknown:
        sys.stderr.write(
            f"שגיאה: שלב לא מוכר ב--skip: {','.join(sorted(unknown))}\n")
        return 2

    reports = [process_file(t, skip, args.dry_run) for t in targets]

    if args.json:
        print(json.dumps([asdict(r) for r in reports],
                         ensure_ascii=False, indent=2))
    else:
        for r in reports:
            sys.stderr.write(_format_human(r) + "\n")

    return 0 if all(r.error is None for r in reports) else 2


if __name__ == "__main__":
    sys.exit(main())
