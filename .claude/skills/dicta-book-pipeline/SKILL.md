---
name: dicta-book-pipeline
description: Use when the user asks to process a Dicta book — identify headings, validate hierarchy, OCR-compare against the original PDF, or run final QA before pushing to otzaria-library. Triggers: "תעבד ספר דיקטה", "בדיקה סופית", "השוואה מול PDF", "זיהוי כותרות". The skill orchestrates: HebrewBooks DB lookup → PDF download → page OCR → diff → header proposal → QA report.
---

# Dicta Book Processing Pipeline

You are running a multi-stage pipeline that bridges Step 5.3 of [dicta-automation-plan.md](../../../../dicta-automation-plan.md). The deterministic prefix (5.1, 5.2) is already implemented as CLIs. **Your job is the AI-judgment passes**: header identification, OCR comparison, and final QA.

## Inputs you need from the user

Ask for whatever is missing — but only ask once per conversation, and **do not ask** for things already saved in memory or already provided.

| Input | How to obtain |
|---|---|
| הנתיב לקובץ ה‑TXT של דיקטה (לא ערוך או חצי-ערוך) | שאל את המשתמש או קבל בהפעלה |
| נתיב ל‑DB של קטלוג HebrewBooks | **ברירת מחדל**: `/Users/david/Downloads/otzaria_latest/otzaria/otzar-HB_catalog.db`. אל תשאל אלא אם הסקריפט מחזיר שגיאה שהקובץ לא קיים |
| URL + API key של שרת ה‑OCR | env vars `OCRWIN_URL`, `OCRWIN_API_KEY`. אם חסרים — שאל וצור `.claude/skills/dicta-book-pipeline/.env.local` (gitignored) |

## Stage 1 — Locate the book in HebrewBooks

### מבנה ה‑DB (otzar-HB_catalog.db)

ה‑DB מכיל **שתי טבלאות נפרדות**:

| טבלה | תוכן | האם לחפש בה? |
|---|---|---|
| `hebrew_books` | קטלוג HebrewBooks (~60K ספרים) | **כן — הספרי דיקטה כולם משם** |
| `otzar_hahochma` | קטלוג אוצר החכמה (~163K ספרים) | **לא** — דיקטה לא משתמשים בו |

ספרי דיקטה מקורם **אך ורק** ב‑HebrewBooks. אסור לחפש ב‑`otzar_hahochma`. הסקריפט `search_hb.py` כבר מחויב לטבלה הנכונה — אל תיגע בו.

### סכמת `hebrew_books`

```
id_book        INTEGER PRIMARY KEY  ← זה גם ה‑ID להורדת PDF (ראה Stage 2)
title          TEXT
author         TEXT                  ← בפורמט "משפחה - פרטי בן ..."
printing_place TEXT                  ← לדוגמה "לבוב", "ירושלים"
printing_year  TEXT                  ← גימטריה ("תרכו"). הצג למשתמש את זה.
pub_date       INTEGER               ← שנה לועזית (1866). הצג בסוגריים אם מסייע.
pages          INTEGER
tags           TEXT                  ← מערך JSON (הסקריפט פורסר אותו לרשימה)
```

### סדר הפעולות

1. **הסק את שם הספר מה‑TXT הנכנס**: התוכן של `<h1>` בשורה הראשונה. אם הוא מכיל "על מסכת X" / "על X", שווה לנסות גם בלי הסיומת — מחבר עשוי להופיע בקטלוג בצורה אחרת.
2. **הרץ את החיפוש**:
   ```bash
   python .claude/skills/dicta-book-pipeline/scripts/search_hb.py --title "<book>" --json
   ```
   - הסקריפט מחזיר עד 25 תוצאות, ממוינות לפי דמיון (התאמה מדויקת → התחלה → הכלה → מילים משותפות).
   - אם הסקריפט שגיאה "DB not found" — ורק אז שאל את המשתמש על נתיב חלופי, והעבר אותו ב‑`--db`.
3. **אם יש מועמד יחיד** עם score גבוה (כותרת זהה / starts-with) — המשך, אבל הצג למשתמש שורה אחת `[<id>] <title> — <author>, <place> <printing_year>` ואשר לפני הורדה.
4. **אם יש כמה מועמדים** — `AskUserQuestion` עם עד 4 אפשרויות. המידע שצריך להיות בכל אפשרות:
   - **label**: כותרת + מחבר (קצר)
   - **description**: מקום + שנה (גם גימטריה וגם לועזית) + מספר עמודים + תגים
   - השתמש ב‑pub_date (לועזית) לסינון מהיר אם המשתמש מבין יותר מ‑printing_year (גימטריה).
5. **אם אין מועמדים** — דווח למשתמש. הצע:
   - לחפש מילה אחת מהכותרת בלבד.
   - אם המשתמש מכיר את המחבר — לחפש לפי שם המחבר (יש לתמוך בזה דרך `--title` כי הסקריפט מחפש בכותרת בלבד; להחיפוש לפי מחבר אפשר לבקש זמני להריץ `sqlite3` ידני).
   - לבקש id ישירות מהמשתמש.

> אל תנחש id. אם המשתמש סיפק id ישירות — דלג על שלבים 1‑5.

## Stage 2 — Download the PDF

URL ההורדה: `https://download.hebrewbooks.org/downloadhandler.ashx?req=<ID>` — זהה לכל הספרים.

```bash
python scripts/download_pdf.py --id <ID> --out /tmp/dicta_pipeline/<book>/source.pdf
```

הסקריפט שומר ל‑cache; אם הקובץ קיים — לא יוריד שוב.

## Stage 3 — Convert PDF to images and OCR

```bash
python scripts/pdf_to_pages.py --pdf <pdf> --out-dir /tmp/dicta_pipeline/<book>/pages --dpi 300
python scripts/ocr_batch.py --in-dir <pages> --out /tmp/dicta_pipeline/<book>/ocr.txt --concurrency 8
```

- ה‑OCR יוצר קובץ אחד שמרכז את כל העמודים, עם מפריד `\n\n=== PAGE N ===\n\n`.
- שרת ה‑OCR מקבל בקשה אחת לעמוד (multipart `file` + header `X-API-Key`). הסקריפט שולח במקביל.
- אם השרת לא זמין → דלג על שלבים 5 ו‑6 והודע למשתמש שאי אפשר להשוות מול המקור.

## Stage 4 — Header proposal (LLM Pass A)

**זה אתה.** טען את [prompts/headers.md](prompts/headers.md), קרא את הקובץ הנכנס, והפק הצעות כותרות.

עקרונות מחייבים:
- אסור לערוך את הקובץ ישירות. הפק רק `headers.proposed.json` במבנה:
  ```json
  [{"line": 142, "current": "...", "proposed": "<h3>דף ב.</h3>", "level": 3, "confidence": "high|medium|low"}]
  ```
- אל תוסיף תוכן שלא קיים. אסור להמציא טקסט.
- שמור על היררכיה קוהרנטית: אסור `<h3>` להופיע ישירות בתוך `<h1>` אם אין `<h2>` באמצע. אם זוהתה הפרה — סמן `confidence: low` והסבר ב‑note.
- כללי טיפוס שכיחים (מבוסס דוגמאות מאוצריא):
  - שם הספר → `<h1>` (קיים, אל תיגע)
  - חלק / מסכת / "הקדמה" / "מסכת אור תורה" וכד' → `<h2>`
  - פרק / דף → `<h3>` (לדוגמה `<h3>דף ב.</h3>`)
  - סימן / סעיף → `<h4>`–`<h5>`
- בש"ס: צמד `דף ב.` ו‑`דף ב:` הם שתי כותרות `<h3>` נפרדות, לא אחת.

לאחר ההפקה — הצג למשתמש סיכום: כמה כותרות הוצעו, התפלגות רמות, וכמה ב‑confidence נמוך. שאל אם להחיל אוטומטית את ה‑high או רק לסקור הכל.

## Stage 5 — OCR diff (LLM Pass D — only on flagged regions)

```bash
python scripts/diff_texts.py --dicta <dicta.txt> --ocr <ocr.txt> --out /tmp/dicta_pipeline/<book>/diff.json --threshold 0.85
```

הסקריפט מציג רק קטעים שבהם דמיון פאזי < threshold. עבור כל פער:

1. הצג את 3 השורות לפני, השורה החשודה, 3 שורות אחרי — משלושת המקורות (Dicta / OCR / לפני‑ניקוי אם זמין).
2. תפקידך כ‑LLM: לקבוע מי נכון. השתמש בשיקול דעת הנדסי:
   - **Dicta צודק** ברוב המכריע. מטה‑prior: ~85% Dicta נכון.
   - **OCR צודק** רק כאשר יש שגיאה ברורה ב‑Dicta (אות מוחלפת מסקנית — ד↔ר, ה↔ח — והעמוד ב‑OCR ברור).
   - **שניהם שגויים** קורה. אם משהו לא מסתדר — סמן ב‑manual_review.
3. הפק `corrections.proposed.json` באותו מבנה כמו headers.

> **חוק זהב**: לעולם לא להחליף אוטומטית על בסיס OCR. רק להציע. אישור אנושי הוא דרישה.

## Stage 6 — Final QA pass (LLM Pass B)

טען את [prompts/qa.md](prompts/qa.md). קרא את הקובץ במלואו (אחרי שלב 4) ודאג ל‑:

- α — קטעים גדולים ללא כותרת (>800 מילים בין כותרות צמודות).
- β — רמת כותרת לא תקינה (קפיצה מ‑h2 ל‑h4).
- γ, ζ — תגים פתוחים/סגורים לא מאוזנים. **השתמש קודם בסקריפט הקיים** — `python /Users/david/Documents/EditingDictaBooks/edit_dicta_cli.py validate-tags --file <path> --json`. רק אם הוא מצא משהו, תן ל‑LLM להציע תיקון.
- η — `דף ב`, `דף ג` כשורה רגילה (לא `<h3>`) — דגל לכל מופע.
- θ — שורות עם תווים מוזרים, רצפים מתחלפים שלא הגיוניים — חשוד ל‑OCR.

הפק דו"ח סופי `report.md` עם הסעיפים: סיכום מנהל, רשימה מסודרת לפי רמת חומרה, והמלצה — האם הספר מוכן לדחיפה ל‑repo, או דורש בקרת אדם.

## Stage 7 — Output and handoff

```
/tmp/dicta_pipeline/<book>/
├── source.pdf              (Stage 2)
├── pages/                  (Stage 3)
├── ocr.txt                 (Stage 3)
├── headers.proposed.json   (Stage 4)
├── diff.json               (Stage 5 — automated)
├── corrections.proposed.json (Stage 5 — your output)
└── report.md               (Stage 6)
```

**אסור** לדחוף ל‑repo `otzaria-library` בלי אישור מפורש מהמשתמש. גם עם אישור — תמיד ב‑branch נפרד, לא ב‑main.

## Conventions

- כל קריאה לסקריפט: גם אם הוא משכתב קובץ — הראה למשתמש מה קרה, על איזה קובץ עבדת, וכמה שינויים. השתמש בפלט `--json` של הסקריפטים הקיימים.
- אם משימה כלשהי נכשלה (DB לא נמצא, OCR לא מגיב) — דווח, אל תמשיך עם נתונים שגויים.
- שמור על הסדר: סטייג'ים 1‑3 הם תשתית; 4‑6 דורשים שיקול דעת. אם הסטייג' תשתית נכשל, סטייג' השיקול לא יבוצע.
- בכל שלב הצג למשתמש סיכום קצר (1‑2 משפטים): מה רץ, מה התוצאה, מה הצעד הבא. אל תהיה מילולי מדי.

## Failure modes — what to do

| תרחיש | תגובה |
|---|---|
| `OCRWIN_URL` לא מוגדר | בקש מהמשתמש URL+key, שמור ל‑`.env.local`, המשך |
| ה‑PDF לא יורד (404, חיבור) | ייתכן ID שגוי. הצג את ה‑URL והתבקש שוב מהמשתמש |
| `pdftoppm` לא מותקן | אמור: `brew install poppler` |
| OCR מחזיר טקסט ריק לעמוד | רשום אזהרה, המשך לשאר העמודים, וציין בדו"ח |
| יותר מ‑1000 עמודים | אזהר את המשתמש לפני התחלה — זה ייקח זמן |
| המשתמש מבקש לקפוץ ישר ל‑Stage 6 | לגיטימי. אבל בלי OCR אין יכולת לזהות θ. הסבר. |

## Scripts in this skill

- [scripts/search_hb.py](scripts/search_hb.py) — sqlite חיפוש בכותרת, עם זיהוי סכמה דינמי
- [scripts/download_pdf.py](scripts/download_pdf.py) — הורדת PDF (cache + retry)
- [scripts/pdf_to_pages.py](scripts/pdf_to_pages.py) — pdftoppm wrapper
- [scripts/ocr_batch.py](scripts/ocr_batch.py) — שליחת עמודים במקביל ל‑OCR
- [scripts/diff_texts.py](scripts/diff_texts.py) — השוואה fuzzy

הסקריפטים תומכים ב‑`--json` להוצאת פלט שמיש לעיבוד שלך.

## Prompts

- [prompts/headers.md](prompts/headers.md) — להפעלה כשאתה ב‑Stage 4
- [prompts/qa.md](prompts/qa.md) — להפעלה כשאתה ב‑Stage 6
