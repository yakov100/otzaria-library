#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
אימות שמות הספרים בתיקיית ForDB.

מטרה: לוודא שכל שם ספר המופיע בקבצי ForDB (בעמודות הרלוונטיות) קיים *בדיוק כצורתו*
(בלי שום שינוי תו או אות) ברשימת הספרים שתיבנה ביצירת ה-DB.

שתי קבוצות שמות נבנות:
  A. "sources" - שמות ה*מקור* של הספרים שנכנסים ל-DB:
     1. *מקור האמת*: שמות קבצי הספרים הנארזים ל-release בלבד - הנתיבים תואמים
        בדיוק את .github/workflows/update-library.yml (PACKAGED_PREFIXES). תיקיות
        ביניים/ארכיון (extraBooks, National-Library) אינן נכנסות ל-DB ולכן אינן
        נחשבות. נמנים דרך `git ls-tree` (ללא הורדת תוכן - עובד עם sparse/partial).
     2. all_metadata_with_file_paths.json - בעיקר עבור ספרי ספריא שאינם כקבצים ב-repo.
     3. שמות ספרי *ספריא* הנמשכים חיים מ-API בכל ריצה (רק השמות). כשל במשיכה
        אינו מפיל את הבדיקה (נפילה בטוחה לרשימה המקומית).
  B. "final_canon" - השמות כפי שיהיו ב-DB *אחרי* שינויי השמות: לכל שם מקור
     מוחל srename (sanitize(old)->sanitize(new)) מ-book_renames.csv.
  כל השמות עוברים ניקוי (sanitize) הזהה בדיוק לזה שבונה את שמות הקבצים ב-DB
  (sefariaToOtzaria/.../otzaria/utils.py).

אופן הבדיקה:
  * כל שם מ-generations / sefaria_metadata_changes / ForDB/all_metadata.json /
    book_moves: מנוקה, מוחל עליו srename (כפי שיהיה ב-DB), ונבדק מול final_canon.
  * book_renames.csv: נבדק שם ה*מקור* (העמודה השמאלית) מול sources - הספר שמשנים
    חייב להתקיים (שינוי לא "יתום"). שם היעד אינו נבדק בנפרד (הוא ממילא ב-final_canon).

יציאה בקוד 1 אם נמצא ולו שם אחד שאינו קיים - כך ש-CI נכשל ב-PR / בכל קומיט.
"""

import csv
import json
import os
import re
import subprocess
import sys
import urllib.request

# ---------------------------------------------------------------------------
# נתיבים
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
FORDB = os.path.join(REPO_ROOT, "ForDB")

CANONICAL_METADATA = os.path.join(REPO_ROOT, "all_metadata_with_file_paths.json")

BOOK_RENAMES = os.path.join(FORDB, "book_renames.csv")
GENERATIONS = os.path.join(FORDB, "generations.csv")
SEFARIA_CHANGES = os.path.join(FORDB, "sefaria_metadata_changes.csv")
BOOK_MOVES = os.path.join(FORDB, "book_moves.csv")
FORDB_METADATA = os.path.join(FORDB, "all_metadata.json")

# API של ספריא: עץ התוכן המלא (TOC) - מכיל את כל שמות הספרים, ללא הטקסטים.
SEFARIA_INDEX_URL = "https://www.sefaria.org/api/index/"
SEFARIA_FETCH = os.environ.get("SEFARIA_FETCH", "1") not in ("0", "false", "False", "")


# ---------------------------------------------------------------------------
# עזרי קריאה
# ---------------------------------------------------------------------------
def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_rows(path, has_header):
    """מחזיר (header_or_None, list_of_rows). שומר על השם בדיוק כפי שהוא בקובץ."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return (None, [])
    if has_header:
        return (rows[0], rows[1:])
    return (None, rows)


def col_index(header, name):
    """אינדקס עמודה לפי שם כותרת מדויק."""
    if not header:
        raise ValueError(f"כותרת ריקה/חסרה - לא ניתן לאתר את העמודה {name!r}")
    for i, h in enumerate(header):
        if h == name:
            return i
    raise KeyError(f"לא נמצאה עמודה בשם {name!r} בכותרת {header!r}")


# ---------------------------------------------------------------------------
# ניקוי שם - חייב להיות זהה *בדיוק* ל-sanitize_filename שבונה את שמות הספרים ב-DB
# (sefariaToOtzaria/סקריפטים/otzaria/utils.py). זה מה שקובע כיצד ייראה שם הספר ב-DB:
#   * הסרת טעמים/ניקוד (֑-ׇ)
#   * הסרת התווים \ / : * " ״ ? < > |
#   * המרת '_' לרווח, והסרת ' ו-''
# כך למשל 'גליון הש"ס' הופך ל'גליון השס' - כפי שהספר נשמר ב-DB.
# ---------------------------------------------------------------------------
def sanitize_title(name):
    if name is None:
        return None
    s = re.sub("[֑-ׇ]", "", name)            # טעמים וניקוד
    s = re.sub("[\\\\/:*\"״?<>|]", "", s)          # \ / : * " ״ ? < > |
    s = s.replace("_", " ").replace("''", "").replace("'", "")
    return s.strip()


# ---------------------------------------------------------------------------
# מקור האמת: קבצי הספרים בפועל הנארזים ל-release/DB.
# הנתיבים תואמים *בדיוק* לאלו שנארזים ב-.github/workflows/update-library.yml
# (שלבי "Create otzaria Release Archive" + "Create dicta Release Archive").
# חשוב: לא כל תיקייה שבה רכיב 'אוצריא' נכנסת ל-DB - תיקיות ביניים/ארכיון כמו
# extraBooks ו-National-Library *אינן* נארזות, ולכן אינן נחשבות.
# ---------------------------------------------------------------------------
BOOK_EXTS = (".txt", ".pdf", ".docx")
PACKAGED_PREFIXES = (
    "Ben-YehudaToOtzaria/ספרים/אוצריא/",
    "DictaToOtzaria/ערוך/ספרים/אוצריא/",
    "DictaToOtzaria/לא ערוך/ספרים/אוצריא/",
    "OnYourWayToOtzaria/ספרים/אוצריא/",
    "OraytaToOtzaria/ספרים/אוצריא/",
    "tashmaToOtzaria/ספרים/אוצריא/",
    "sefariaToOtzaria/sefaria_export/ספרים/אוצריא/",
    "sefariaToOtzaria/sefaria_api/ספרים/אוצריא/",
    "MoreBooks/ספרים/אוצריא/",
    "wikiJewishBooksToOtzaria/ספרים/אוצריא/",
    "wikisourceToOtzaria/ספרים/אוצריא/",
    "ToratEmetToOtzaria/ספרים/אוצריא/",
    "pninimToOtzaria/ספרים/אוצריא/",
)


def tracked_book_basenames():
    """
    מחזיר set של שמות-בסיס מנוקים של קבצי הספרים הנארזים ל-release (לפי
    PACKAGED_PREFIXES בלבד). משתמש ב-`git ls-tree -r HEAD` שקורא את עץ הקומיט
    בלבד - אין צורך בהורדת תוכן הקבצים (עובד עם partial-clone + sparse-checkout).
    אם git אינו זמין, נופל ל-os.walk על עץ העבודה.
    """
    paths = []
    try:
        result = subprocess.run(
            ["git", "-C", REPO_ROOT, "ls-tree", "-r", "HEAD", "--name-only", "-z"],
            capture_output=True,
            check=True,
        )
        paths = result.stdout.decode("utf-8").split("\0")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::git ls-tree נכשל ({e}); נופלים ל-os.walk על עץ העבודה.")
        for root, _dirs, files in os.walk(REPO_ROOT):
            for fn in files:
                rel = os.path.relpath(os.path.join(root, fn), REPO_ROOT)
                paths.append(rel)

    names = set()
    for p in paths:
        if not p:
            continue
        norm = p.replace("\\", "/")
        if not any(norm.startswith(prefix) for prefix in PACKAGED_PREFIXES):
            continue
        base, ext = os.path.splitext(norm.rsplit("/", 1)[-1])
        if ext.lower() in BOOK_EXTS:
            clean = sanitize_title(base)
            if clean:
                names.add(clean)
    return names


# ---------------------------------------------------------------------------
# בניית הרשימה הקנונית
# ---------------------------------------------------------------------------
def build_sanitized_rename(rename_pairs):
    """מיפוי שינויי-שם במרחב המנוקה: sanitize(old) -> sanitize(new) (ללא זהויות)."""
    smap = {}
    for _line, old, new in rename_pairs:
        so, sn = sanitize_title(old), sanitize_title(new)
        if so and sn and so != sn:
            smap[so] = sn
    return smap


def load_canonical(srename):
    """
    מחזיר (sources, final_canon):
      * sources    = שמות ה*מקור* (מנוקים) של הספרים שנכנסים ל-DB:
                     קבצי ספרים נארזים (PACKAGED_PREFIXES) + all_metadata + ספריא חיה.
      * final_canon = שמות הספרים כפי ש*יהיו ב-DB* אחרי החלת שינויי השמות:
                     לכל שם מקור מחילים את srename (sanitize(old)->sanitize(new)).
    ה-book_renames נבדק מול sources (קיום שם המקור); שאר הקבצים מול final_canon.
    """
    sources = set()

    def add(raw):
        clean = sanitize_title(raw)
        if clean:
            sources.add(clean)

    book_files = tracked_book_basenames()
    sources |= book_files
    print(f"[canonical] {len(book_files)} שמות מקבצי ספרים נארזים (PACKAGED_PREFIXES)")

    meta = read_json(CANONICAL_METADATA)
    before = len(sources)
    for entry in meta:
        add(entry.get("title"))
    print(f"[canonical] נוספו {len(sources) - before} שמות מ-all_metadata_with_file_paths.json")

    if SEFARIA_FETCH:
        live = fetch_sefaria_titles()
        if live is not None:
            before = len(sources)
            for raw in live:
                add(raw)
            print(
                f"[canonical] נמשכו {len(live)} שמות חיים מספריא; "
                f"נוספו {len(sources) - before} חדשים (union)"
            )
    else:
        print("[canonical] משיכת ספריא מושבתת (SEFARIA_FETCH=0)")

    final_canon = {srename.get(s, s) for s in sources}
    print(f"[canonical] {len(sources)} שמות מקור, {len(final_canon)} שמות סופיים (אחרי שינויי שם)")
    return sources, final_canon


def fetch_sefaria_titles():
    """מושך את עץ התוכן של ספריא ומחזיר set של heTitle *גולמיים*. None בכשל."""
    try:
        req = urllib.request.Request(
            SEFARIA_INDEX_URL,
            headers={"User-Agent": "otzaria-library-ci/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - כל כשל תקשורת/פענוח -> נפילה בטוחה לרשימה המקומית
        print(f"::warning::משיכת השמות מספריא נכשלה ({e}); ממשיכים עם הרשימה המקומית בלבד.")
        return None

    titles = set()

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if "contents" in node:
                walk(node["contents"])
            else:
                he = node.get("heTitle")
                if he:
                    titles.add(he)

    walk(data)
    return titles


# ---------------------------------------------------------------------------
# שינויי השמות (book_renames.csv): שם-מקור (עמודה שמאלית) -> שם-יעד (עמודה ימנית)
# ---------------------------------------------------------------------------
def load_rename_pairs():
    """מחזיר רשימת (line_no, old, new) מתוך book_renames.csv (ללא כותרת)."""
    _, rows = read_csv_rows(BOOK_RENAMES, has_header=False)
    pairs = []
    for i, row in enumerate(rows, start=1):
        if len(row) < 2:
            continue
        pairs.append((i, row[0], row[1]))
    return pairs


# ---------------------------------------------------------------------------
# הבדיקה
# ---------------------------------------------------------------------------
def main():
    rename_pairs = load_rename_pairs()
    srename = build_sanitized_rename(rename_pairs)
    sources, final_canon = load_canonical(srename)

    # failures[file] = list of (line/identifier, raw_name, checked_name)
    failures = {}

    def check_db_name(file_label, identifier, raw_name):
        """
        בודק שם 'כפי שיהיה ב-DB': מנקה (sanitize), מחיל את שינוי-השם (srename),
        ומוודא קיום ברשימת השמות הסופיים (final_canon).
        """
        if raw_name is None or raw_name == "":
            return
        clean = sanitize_title(raw_name)
        final = srename.get(clean, clean)
        if final not in final_canon:
            failures.setdefault(file_label, []).append((identifier, raw_name, final))

    # 1) book_renames.csv - נבדק שם ה*מקור* (העמודה השמאלית) מול שמות המקור:
    #    יש לוודא שהספר שאותו משנים אכן קיים (שינוי לא "יתום"). שם היעד אינו נבדק
    #    כאן - הוא ממילא נכלל ב-final_canon כתוצאת השינוי.
    for line_no, old, _new in rename_pairs:
        clean = sanitize_title(old)
        if clean and clean not in sources:
            failures.setdefault("ForDB/book_renames.csv", []).append(
                (f"שורה {line_no} (שם מקור)", old, clean)
            )

    # 2) generations.csv - עמודה "שם ספר" (לפי הכותרת, לא לפי מיקום קבוע)
    header, rows = read_csv_rows(GENERATIONS, has_header=True)
    name_idx = col_index(header, "שם ספר")
    for line_no, row in enumerate(rows, start=2):
        if len(row) > name_idx:
            check_db_name("ForDB/generations.csv", f"שורה {line_no}", row[name_idx])

    # 3) sefaria_metadata_changes.csv - עמודה "title"
    header, rows = read_csv_rows(SEFARIA_CHANGES, has_header=True)
    t_idx = col_index(header, "title")
    for line_no, row in enumerate(rows, start=2):
        if len(row) > t_idx:
            check_db_name("ForDB/sefaria_metadata_changes.csv", f"שורה {line_no}", row[t_idx])

    # 4) book_moves.csv - עמודה "name" (כרגע ריק; ייכלל אוטומטית כשיתמלא)
    header, rows = read_csv_rows(BOOK_MOVES, has_header=True)
    n_idx = col_index(header, "name")
    for line_no, row in enumerate(rows, start=2):
        if len(row) > n_idx:
            check_db_name("ForDB/book_moves.csv", f"שורה {line_no}", row[n_idx])

    # 5) ForDB/all_metadata.json - שדה "title"
    for idx, entry in enumerate(read_json(FORDB_METADATA)):
        check_db_name("ForDB/all_metadata.json", f"רשומה {idx}", entry.get("title"))

    # ----- דוח -----
    total = sum(len(v) for v in failures.values())
    if total == 0:
        print("\n✅ כל שמות הספרים ב-ForDB קיימים ברשימת הספרים הקנונית.")
        return 0

    print(f"\n❌ נמצאו {total} שמות ספרים ב-ForDB שאינם קיימים ברשימת הספרים הקנונית:\n")
    for file_label in sorted(failures):
        items = failures[file_label]
        print(f"  📄 {file_label} ({len(items)}):")
        for identifier, raw_name, checked in items:
            if checked != raw_name:
                print(f"     - {identifier}: {raw_name!r} (כפי שב-DB: {checked!r}) — לא נמצא")
            else:
                print(f"     - {identifier}: {raw_name!r} — לא נמצא")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
