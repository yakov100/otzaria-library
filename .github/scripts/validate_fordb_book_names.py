#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
אימות שמות הספרים בתיקיית ForDB.

מטרה: לוודא שכל שם ספר המופיע בקבצי ForDB (בעמודות הרלוונטיות) קיים *בדיוק כצורתו*
(בלי שום שינוי תו או אות) ברשימת הספרים שתיבנה ביצירת ה-DB.

קבוצות השמות הנבנות (כל השמות עוברים ניקוי sanitize הזהה לזה שבונה את שמות הקבצים ב-DB,
sefariaToOtzaria/.../otzaria/utils.py):
  מרכיבים:
     1. *מקור האמת* לאוצריא: שמות קבצי הספרים הנארזים ל-release בלבד - הנתיבים תואמים
        בדיוק את .github/workflows/update-library.yml (PACKAGED_PREFIXES). תיקיות
        ביניים/ארכיון (extraBooks, National-Library, KSK) אינן נכנסות ל-DB ולכן אינן
        נחשבות. נמנים דרך `git ls-tree` (ללא הורדת תוכן - עובד עם sparse/partial).
     2. שמות ספרי *ספריא*: נמשכים חיים מ-API + רשומות sefaria מ-all_metadata (גיבוי).
        ספרי ספריא נוצרים בבנייה ואין להם קובץ מקומי, לכן זה מקורם. כשל במשיכה החיה
        אינו מפיל את הבדיקה (גיבוי לרשומות ה-sefaria שבמטא-דאטה).
     3. שאר רשומות all_metadata_with_file_paths.json (אוצריא) - לבדיקות מטא-דאטה בלבד.
  A. "db_final" = (1)+(2) אחרי שינויי השמות - מה שבאמת מגיע ל-DB. ספר אוצריא נכנס ל-DB
     רק כקובץ נארז, ולכן שם במטא-דאטה לבדו (בלי קובץ נארז) אינו נכלל. כך נתפס ספר שהוזז
     לתיקייה לא-נארזת (כגון KSK) ושומר מטא-דאטה ישנה.
  B. "final_canon" = (1)+(2)+(3) אחרי שינויי השמות - רשימה רחבה לבדיקות המטא-דאטה.
     ("sources" = אותם מרכיבים לפני שינויי השמות; משמש לבדיקת book_renames.)
  שינויי השם (srename) נלקחים מ-book_renames.csv: sanitize(old)->sanitize(new).

אופן הבדיקה:
  * generations / book_moves: חייבים להתאים בדיוק ל-book.title שב-DB -> נבדקים מול db_final.
  * sefaria_metadata_changes / ForDB/all_metadata.json: מטא-דאטה -> נבדקים מול final_canon.
  * book_renames.csv: שם ה*מקור* (העמודה השמאלית) מול sources - הספר שמשנים חייב להתקיים
    (שינוי לא "יתום"). שם היעד אינו נבדק בנפרד.

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
    מחזיר (sources, final_canon, db_final):
      * sources    = כל שמות המקור (מנוקים): קבצי ספרים נארזים + all_metadata (כל הרשומות) + ספריא חיה.
      * final_canon = sources אחרי החלת שינויי השמות. רשימה רחבה לבדיקות מטא-דאטה.
      * db_final    = השמות שבאמת *מגיעים ל-DB* אחרי שינויי שם: קבצים נארזים בפועל +
                      ספרי ספריא בלבד. ספרי אוצריא נכנסים ל-DB רק כקובץ נארז — ולכן שם
                      במטא-דאטה לבדו (בלי קובץ נארז) אינו נכלל כאן. כך נתפס ספר שהוזז
                      לתיקייה לא-נארזת (כגון KSK) ושומר מטא-דאטה ישנה.
    ספרי ספריא נוצרים בבנייה (אין להם קובץ מקומי), לכן הם נלקחים מה-API החי + המטא-דאטה.
    book_renames נבדק מול sources; generations/book_moves מול db_final; השאר מול final_canon.
    """
    def clean_titles(raws):
        return {c for c in (sanitize_title(r) for r in raws) if c}

    packaged = tracked_book_basenames()
    print(f"[canonical] {len(packaged)} שמות מקבצי ספרים נארזים (PACKAGED_PREFIXES)")

    meta = read_json(CANONICAL_METADATA)
    sefaria_meta = clean_titles(e.get("title") for e in meta if e.get("Sourcefolder") == "sefaria")
    other_meta = clean_titles(e.get("title") for e in meta if e.get("Sourcefolder") != "sefaria")
    print(f"[canonical] all_metadata: {len(sefaria_meta)} ספריא + {len(other_meta)} אוצריא")

    sefaria = set(sefaria_meta)
    if SEFARIA_FETCH:
        live = fetch_sefaria_titles()
        if live is not None:
            before = len(sefaria)
            sefaria |= clean_titles(live)
            print(f"[canonical] נמשכו {len(live)} שמות חיים מספריא; נוספו {len(sefaria) - before} חדשים (union)")
    else:
        print("[canonical] משיכת ספריא מושבתת (SEFARIA_FETCH=0)")

    sources = packaged | sefaria | other_meta
    db = packaged | sefaria  # מה שבאמת ב-DB: קבצים נארזים + ספריא (ללא מטא-דאטה לא-מגובה)
    final_canon = {srename.get(s, s) for s in sources}
    db_final = {srename.get(s, s) for s in db}
    print(f"[canonical] מקור: {len(sources)} | ב-DB: {len(db)} | סופיים: {len(final_canon)}/{len(db_final)} (אחרי שינויי שם)")
    return sources, final_canon, db_final


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
    sources, final_canon, db_final = load_canonical(srename)

    # failures[file] = list of (line/identifier, raw_name, checked_name)
    failures = {}

    def check_db_name(file_label, identifier, raw_name, canon):
        """
        בודק שם 'כפי שיהיה ב-DB': מנקה (sanitize), מחיל את שינוי-השם (srename),
        ומוודא קיום ב-canon (final_canon למטא-דאטה, db_final למה שחייב להתאים ל-book.title).
        """
        if raw_name is None or raw_name == "":
            return
        clean = sanitize_title(raw_name)
        final = srename.get(clean, clean)
        if final not in canon:
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

    # 2) generations.csv - עמודה "שם ספר". נבדק מול db_final: ה-seeder מתאים בדיוק
    #    ל-book.title שב-DB, ולכן ספר שאינו נארז (כגון שהוזז ל-KSK) ייתפס כאן.
    header, rows = read_csv_rows(GENERATIONS, has_header=True)
    name_idx = col_index(header, "שם ספר")
    for line_no, row in enumerate(rows, start=2):
        if len(row) > name_idx:
            check_db_name("ForDB/generations.csv", f"שורה {line_no}", row[name_idx], db_final)

    # 3) sefaria_metadata_changes.csv - עמודה "title" (מטא-דאטה -> final_canon)
    header, rows = read_csv_rows(SEFARIA_CHANGES, has_header=True)
    t_idx = col_index(header, "title")
    for line_no, row in enumerate(rows, start=2):
        if len(row) > t_idx:
            check_db_name("ForDB/sefaria_metadata_changes.csv", f"שורה {line_no}", row[t_idx], final_canon)

    # 4) book_moves.csv - עמודה "name" (חייב להתאים ל-book.title -> db_final)
    header, rows = read_csv_rows(BOOK_MOVES, has_header=True)
    n_idx = col_index(header, "name")
    for line_no, row in enumerate(rows, start=2):
        if len(row) > n_idx:
            check_db_name("ForDB/book_moves.csv", f"שורה {line_no}", row[n_idx], db_final)

    # 5) ForDB/all_metadata.json - שדה "title" (מטא-דאטה -> final_canon)
    for idx, entry in enumerate(read_json(FORDB_METADATA)):
        check_db_name("ForDB/all_metadata.json", f"רשומה {idx}", entry.get("title"), final_canon)

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
