---
name: dicta-book-pipeline
description: Use when the user asks to process a Dicta book — identify headings, validate hierarchy, OCR-compare against the original PDF, or run final QA before pushing to otzaria-library. Triggers: "תעבד ספר דיקטה", "בדיקה סופית", "השוואה מול PDF", "זיהוי כותרות". The skill orchestrates: HebrewBooks DB lookup → PDF download → page OCR → diff → header proposal → QA report.
---

# Dicta Book Processing Pipeline

You are running a multi-stage pipeline that bridges Step 5.3 of [dicta-automation-plan.md](../../../../dicta-automation-plan.md). The deterministic prefix (5.1, 5.2) is already implemented as CLIs. **Your job is the AI-judgment passes**: header identification, OCR comparison, and final QA.

## מוסכמות הפלט (חובה)

הקובץ נפתח בעורך `scripts/עריכת ספר באוצריא.html`, שעובד שורה‑אחר‑שורה. הקובץ תקין רק אם הוא עומד בכל הכללים הבאים. **כולם נאכפים בקריאת CLI אחת** — `validate-otzaria` (ראה Stage 6). אכוף בסקריפט, אל תאכוף "בעין".

1. **כותרת לבד בשורה** — אסור טקסט אחרי `</hN>` באותה שורה.
2. **בלי `<big>` בכותרות** — `<h2><big>מסכת קדושין</big></h2>` ⇒ `<h2>מסכת קדושין</h2>`. שורות `<big>` דקורטיביות בודדות בראש קטע (`<big>חדושי</big>`) — להסיר; קולופון `<big>תם ונשלם...</big>` בסוף — להשאיר.
3. **קובץ אחד לכל מסכת** — פצל קובץ רב‑מסכתי, `<h1>` נפרד לכל מסכת בתבנית `<שם ספר> על <מסכת>`. בלי גרשיים (`"`/`”`/`’`) ב‑`<h1>`.
4. **כותרת `דף` מנוקדת, בלי גרש** — עמוד א = `.`, עמוד ב = `:` (`דף ט'`⇒`דף ט.`, `דף ח':`⇒`דף ח:`).
5. **קטע = שורה אחת, המסתיימת ב‑`:`** — כל הערה/דיבור הוא שורת body אחת שלמה. הגולמי של דיקטה לרוב שובר זאת בשתי צורות, ושתיהן מתוקנות לאותו יעד:
   - **מילים בודדות בשורות נפרדות** (`<b>אמר</b>` / `<b>המעתיק</b>` ...) ⇒ **אַחֵד** לשורה אחת.
   - **כמה הערות דחוסות בשורה אחת**, מופרדות ב‑`: ` ⇒ **פַּצֵּל** לשורה לכל הערה.
   קטע מסתיים ב‑`:` (סוף עניין); קטע נושא־דיבור מסתיים ב‑`.` בתוך ההדגשה ואז `:` בסוף.
6. **דיבור־המתחיל מודגש** — תחילת כל קטע: עטוף את **הלמה כולה** (לא רק מילה אחת) ב‑`<b>`. בפירושי תלמוד הלמה היא הציטוט מהגמרא, ומסתיימת בנקודה בתוך התג: `<b>ורבא אמר משום שאין עדים מצויים לקיימו.</b> פירוש...`. אַחֵד `<b>` עוקבים של למה/שם אחד (`<b>אמר</b> <b>המעתיק</b>` ⇒ `<b>אמר המעתיק</b>`); אל תאחד למות/מקורות נפרדים (`<b>תוס'</b> <b>ד"ה ולא</b>` נשארים שניים).
7. **רמות יחסיות** — דף = רמה אחת מתחת לפרק; פרק = רמה אחת מתחת למסכת/חלק. אם פרק=`<h2>` אז דף=`<h3>`; אם פרק=`<h3>` אז דף=`<h4>`. כשהדף הוא יחידת המבנה העליונה (אין כותרת פרק/מסכת מעליו) — דף=`<h2>`. בלי מספר רמה גלובלי קבוע.
8. **שם כותרת מנורמל** — תוכן הכותרת עצמה נכתב בצורה הקנונית, לא כפי שהופיע בדפוס:
   - **הסר שם מחבר** מכותרת — הוא כבר ב‑`<h1>` (`חדושי פרקא קמא דכתובות מהרי"ט` ⇒ `חדושי פרקא קמא דכתובות`).
   - **פתח קיצורים** — `פ' האומר` ⇒ `פרק האומר`.
   - **הוסף `מסכת ` לכותרת מסכת** כשחסר — `<h2>ברכות</h2>` ⇒ `<h2>מסכת ברכות</h2>`.
   - **כותרת פרק בפורמט `<שם הפרק> - פרק <מספר>`** — שם הפרק המקובל בש"ס תחילה, מקף, ואז "פרק" + מספר. מספר חשוף ⇒ הוסף את שם הפרק הקנוני (`פרק ח'` בכתובות ⇒ `האשה שנפלו - פרק שמיני`). אורדינל 1–10 במילים (שביעי/שמיני/עשירי), 11+ בגימטריה (יא/יב/יג). זו עבודת שיקול‑דעת ב‑Stage 4 (דורשת ידע בשמות פרקי הש"ס), לא נורמול דטרמיניסטי.
9. **נרמול גרשיים** — `''` (גרש כפול) ⇒ `"`, גרשיים טיפוגרפיים `”`/`“` ⇒ `"`. (נאכף ע"י `clean-text`.)

## Inputs you need from the user

Ask for whatever is missing — but only ask once per conversation, and **do not ask** for things already saved in memory or already provided.

| Input | How to obtain |
|---|---|
| הנתיב לקובץ ה‑TXT של דיקטה (לא ערוך או חצי-ערוך) | שאל את המשתמש או קבל בהפעלה |
| נתיב ל‑DB של קטלוג HebrewBooks | **ברירת מחדל**: `~/Downloads/otzaria_latest/otzaria/otzar-HB_catalog.db` (נתון חיצוני לפרויקט; `~` עובד לכל שם משתמש). אל תשאל אלא אם הסקריפט מחזיר שגיאה שהקובץ לא קיים — ואז שאל את המשתמש על המיקום |
| URL + API key של שרת ה‑OCR | env vars `OCRWIN_URL`, `OCRWIN_API_KEY`. אם חסרים — שאל וצור `.claude/skills/dicta-book-pipeline/.env.local` (gitignored) |
| **שם משתמש + סיסמה ל‑otzaria.org** | **רק אם** המשתמש מבקש להוריד ספר מהאתר (Stage 0). **שאל את המשתמש בכל פעם.** אסור לשמור/לכתוב לקובץ/לזכור — ראה Stage 0 |

## Stage 0 — הורדת ספר מאתר otzaria.org (אופציונלי)

הרץ שלב זה **רק** כשהמשתמש מבקש "תוריד ספר מהאתר" / מצביע על `https://otzaria.org/library/admin/uploads`. אם המשתמש כבר נתן נתיב לקובץ TXT — דלג ישר ל‑Stage 3.5/1.

> **אבטחה — חובה**: עמוד ה‑uploads מוגן בהתחברות (next‑auth). **בקש מהמשתמש שם משתמש + סיסמה בכל הפעלה** (למשל ב‑`AskUserQuestion`). **לעולם אל** תכתוב את הפרטים לקובץ, ל‑`.env`, ל‑memory, או לתוך ה‑SKILL הזה. השתמש בהם רק בתוך הבקשה הרצה. ה‑session cookie אפשר לשמור בקובץ זמני (`/tmp/...jar.txt`).

האתר הוא אפליקציית Next.js עם next‑auth, provider מסוג `credentials`, basePath `/api/auth` בשורש הדומיין. שדות ההתחברות: `identifier` (שם המשתמש) + `password`.

### א. התחברות (פעם אחת)

```bash
JAR=/tmp/otz_jar.txt; rm -f "$JAR"
CSRF=$(curl -s -c "$JAR" "https://otzaria.org/api/auth/csrf" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['csrfToken'])")
curl -s -b "$JAR" -c "$JAR" \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "identifier=<USERNAME>" \
  --data-urlencode "password=<PASSWORD>" \
  --data-urlencode "callbackUrl=https://otzaria.org/library/admin/uploads" \
  --data-urlencode "json=true" \
  "https://otzaria.org/api/auth/callback/credentials"
# אימות: צריך להחזיר user עם role:"admin"
curl -s -b "$JAR" "https://otzaria.org/api/auth/session"
```

אם ה‑session ריק (`{}`) — ההתחברות נכשלה (סיסמה שגויה / אין הרשאת admin). דווח למשתמש ועצור.

### ב. רשימת ההעלאות + סינון

```bash
curl -s -b "$JAR" "https://otzaria.org/api/admin/uploads/list" -o /tmp/otz_list.json
```

מחזיר `{"success":true,"uploads":[{id, bookName, originalFileName, uploadedBy, uploadedByEmail, uploadedAt, uploadType, status, bookStatus, editCopy, isOcr}, ...]}`.

- **מתויג דיקטה** = `uploadType == "dicta"` (או `originalFileName` מסתיים ב‑`_dicta.txt`).
- **`bookStatus`** — ערכי הסטטוס בשדה זה (כפי שמופיעים ב‑list בפועל): `not_checked` (לא נבדק), `In_treatment` (בטיפול), `ready` (מוכן), `needs_attention` (דורש טיפול), `Website_editing` (עריכת אתר), `added_to_library` (נוסף לספרייה / הוכנס לאוצריא). הפייפליין משתמש בשניים בלבד: `In_treatment` ו‑`added_to_library` (ראה שלב ו והנדבך ב‑Stage 7).
- מיין לפי `uploadedAt` יורד ל"החדש ביותר".

החל את **כל** הקריטריונים שהמשתמש ביקש (סוג דיקטה, סטטוס, וכו'). אם נשארו כמה מועמדים — הצג ב‑`AskUserQuestion`. אם המשתמש אמר "לא משנה איזה" — קח את החדש ביותר.

### ג. הורדת הקובץ

```bash
curl -s -b "$JAR" "https://otzaria.org/api/download/<UPLOAD_ID>" \
  -o "/tmp/dicta_pipeline/<book>/dicta.txt"
```

(הורדה מרובה: `POST /api/download/batch` עם `{"uploadIds":[...]}` → zip.)

### ד. בדיקת המקור ב'לא ערוך'

לפני המעבר לפייפליין, אתר את המקור הגולמי של הספר תחת
`DictaToOtzaria/לא ערוך/ספרים/אוצריא/<קטגוריה>/<שם>.txt` (חיפוש ב‑`list.txt` או `find`).
הקובץ שהורד מ‑uploads עשוי להיות **חצי‑ערוך** (כותרות כבר זוהו), בעוד שהמקור הוא הייצוא הגולמי — הוא ישמש כ"רפרנס לפני‑ניקוי" ל‑Stage 5. סכם למשתמש את ההבדל (שורות, מספר כותרות, `<big>`).

### ה. שינוי שם + העלאה ל‑stage (כדי שהמשתמש יראה את השינויים)

שם הקובץ ב‑uploads הוא מקווקו עם סיומת `_dicta` (`תלמוד_בבלי_אחרונים_מלא_הרועים__חלק_ב_dicta.txt`). שנה אותו ל**שם הקנוני כפי שהוא מופיע ב'לא ערוך'** (שאותר בשלב ד) — השם הנקי עם רווחים, בלי `_dicta`, למשל `מלא הרועים  חלק ב.txt`.

1. **העתק את הקובץ שהורד לשורש הפרויקט** עם השם מ'לא ערוך'. הפקודות בשלב זה רצות מתיקיית שורש הפרויקט (cwd), לכן השתמש בנתיב **יחסי** — בלי נתיב מוחלט תלוי‑מכונה:
   ```bash
   cp "/tmp/dicta_pipeline/<book>/dicta.txt" "./<שם מ'לא ערוך'>.txt"
   ```
   (שמור על הריווח המדויק של השם ב'לא ערוך', כולל רווח כפול אם קיים.)
2. **העלה ל‑stage את הקובץ הגולמי** מיד לאחר ההעתקה, **לפני** הרצת שאר הפייפליין:
   ```bash
   git add "<שם מ'לא ערוך'>.txt"
   ```
   כך ה‑staged הוא הגרסה **הגולמית** שהורדה, ועריכות הפייפליין שיבואו אחר כך יישארו **לא‑staged** — וכל `git diff` יראה למשתמש בדיוק מה הפייפליין שינה.
3. **אל תעשה `git add` שוב** אחרי עריכות הפייפליין, אלא אם המשתמש ביקש זאת במפורש.

### ו. סימון הסטטוס ל‑"בטיפול" (`In_treatment`) — מיד לאחר ההורדה

**מיד אחרי שהקובץ הורד** (וזוהה ה‑`UPLOAD_ID`), עדכן את הסטטוס שלו ב‑otzaria.org ל‑`In_treatment` ("בטיפול"), כדי לסמן שהספר נלקח לעיבוד. השתמש באותו `$JAR` מההתחברות (שלב א):

```bash
curl -s -X PUT "https://otzaria.org/api/admin/uploads/batch-update-book-status" \
  -b "$JAR" -H "Content-Type: application/json" \
  --data-raw '{"uploadIds":["<UPLOAD_ID>"],"bookStatus":"In_treatment"}'
```

- ה‑endpoint מקבל **מערך** `uploadIds`, כך שאפשר לסמן כמה ספרים בבקשה אחת (`["id1","id2"]`).
- אַמֵּת שהתשובה מציינת הצלחה. אם נכשל — דווח למשתמש, אך אפשר להמשיך בפייפליין (הסימון אינו חוסם עיבוד).
- **אל תסמן `added_to_library` בשלב הזה.** המעבר ל‑"נוסף לספרייה" קורה רק בסוף, אחרי אישור המשתמש וקומיט (ראה Stage 7).

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

## Stage 3.5 — Split & normalize (deterministic)

רוץ תמיד, גם כש‑OCR מדולג. הסקריפטים ב‑`../EditingDictaBooks/edit_dicta_cli.py` (יחסית לשורש הפרויקט — מאגר EditingDictaBooks הוא תיקייה אחות לפרויקט; תומכים `--json`, קוד יציאה 0/1/2). אם לא נמצא שם — שאל את המשתמש על המיקום.

1. **פצל לפי מסכת** — אם יש כמה מסכתות (כמה `<h2>` / קולופונים `תם ונשלם מסכת X` / `סליק מסכת X`), צור קובץ נפרד לכל מסכת עם `<h1>` משלו בתבנית `<שם הספר> על <מסכת>`. הצג את רשימת הקבצים המוצעת ואשר לפני יצירה.
2. **נקה `<h1>`** — הסר גרשיים (`"`/`”`/`’`).
3. **נקה טקסט** — `clean-text --file <f>` (נרמול גרשיים `''`→`"` ו‑`”`→`"`, רווחים כפולים, שורות ריקות).
4. **הסר `<big>`** מכותרות ומשורות דקורטיביות בודדות (לא קולופון סיום).
5. **נרמל כותרות `דף`** — `page-number --file <f> --style dot-colon` ו‑`replace-page-b` להמרת `עמוד ב`/גרש ל‑`.`/`:`.
6. **הדגש מילה ראשונה** — `emphasize-first --file <f>` (מוסיף `<b>` + פיסוק סוף). הרחבת הלמה המלאה ומיזוג `<b>` עוקבים (מוסכמה §6) הם שיקול‑דעת ב‑Stage 4.
7. **הפרד כותרות דבוקות לטקסט** — שורה שמתחילה `<h` ולא מסתיימת ב‑`>`: כותרת בשורה אחת, טקסט בשורה הבאה. אתר: `grep -nE '^<h[1-6]>' <f> | grep -vE '>[[:space:]]*$'`.

סיכום למשתמש: לכמה קבצים פוצל, כמה כותרות נורמלו, כמה מילים ראשונות הודגשו, כמה כותרות הופרדו.

## Stage 4 — Header proposal (LLM Pass A)

**זה אתה.** טען את [prompts/headers.md](prompts/headers.md), קרא את הקובץ הנכנס, והפק הצעות כותרות.

עקרונות מחייבים:
- אסור לערוך את הקובץ ישירות. הפק רק `headers.proposed.json` במבנה:
  ```json
  [{"line": 142, "current": "...", "proposed": "<h3>דף ב.</h3>", "level": 3, "confidence": "high|medium|low"}]
  ```
- אל תוסיף תוכן שלא קיים. אסור להמציא טקסט.
- כותרת לבד בשורה — בלי טקסט אחרי `</hN>` (מוסכמות §1).
- רמות יחסיות (מוסכמות §6): קבע קודם את עומק הכותרת בעץ, ואז גזור רמה:
  - שם הספר/המסכת → `<h1>` (קיים, אל תיגע)
  - חלק / "מסכת X על הרי"ף" / "הקדמה" → `<h2>`
  - פרק → `<h2>` או `<h3>` (לפי האם קיים חלק `<h2>` מעליו)
  - דף → רמה אחת מתחת לפרק (`<h3>` או `<h4>`)
  - סימן / סעיף → רמה אחת מתחת לדף
- אסור לדלג רמה (h2→h4). אם חסרה כותרת ביניים — הצע להוסיף אותה (למשל `<h3>פרק האשה</h3>`).
- בש"ס: צמד `דף ב.` ו‑`דף ב:` הם שתי כותרות נפרדות, לא אחת.

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

טען את [prompts/qa.md](prompts/qa.md). קרא את הקובץ במלואו (אחרי שלב 4).

**הרץ קודם את הגייט הדטרמיניסטי על כל קובץ פלט:**
```bash
python3 ../EditingDictaBooks/edit_dicta_cli.py validate-otzaria --file <path> --shas   # יחסי לשורש הפרויקט; --shas לש"ס (עמוד ב כפול)
```
פקודה זו מאחדת את כל אכיפת המוסכמות: תגים, כותרות, פיצול רב‑מסכתי, גרשיים ב‑`<h1>`, ו‑`<big>` בכותרת/דקורטיבי. קוד יציאה: **0 = עבר** (ירוק), **1 = הפרת מוסכמה קשה**. תקן כל בעיה "קשה" עד ש‑exit=0:
`multi_masechta`, `h1_gershayim`, `big_in_heading`, `decorative_big`, `opening/closing_without_opening`, `heading_errors`.
הממצאים תחת `advisory_daf_format` ו‑`advisory_heading_sequence` הם **advisory** — רועשים בספרי חידושים שחוזרים על דפים שלא לפי הסדר, אינם מכשילים. סקור אותם בעין; תקן רק מה שבאמת שגוי.

רק אחרי exit=0 — עבור לקטגוריות שיקול הדעת:

- α — קטעים גדולים ללא כותרת (>800 מילים בין כותרות צמודות).
- η — `דף ב`, `דף ג` כשורה רגילה (לא כותרת) — דגל לכל מופע.
- θ — שורות עם תווים מוזרים/רצפים לא הגיוניים — חשוד ל‑OCR (רק אם OCR זמין).

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

### סימון הסטטוס ל‑"נוסף לספרייה" (`added_to_library`) — רק בסוף

המעבר הסופי קורה **אך ורק** אחרי ש‑**שני** התנאים התקיימו:
1. המשתמש נתן **אישור סופי** לספר (סקר את ה‑`git diff` / הדו"ח ואישר), **וגם**
2. השינויים **נכנסו לקומיט** (commit).

רק אז עדכן את הסטטוס ב‑otzaria.org ל‑`added_to_library` ("הוכנס לאוצריא"), עם אותו endpoint משלב 0/ו (אם ה‑`$JAR` פג, התחבר מחדש לפי Stage 0/א):

```bash
curl -s -X PUT "https://otzaria.org/api/admin/uploads/batch-update-book-status" \
  -b "$JAR" -H "Content-Type: application/json" \
  --data-raw '{"uploadIds":["<UPLOAD_ID>"],"bookStatus":"added_to_library"}'
```

- **אל תקפוץ** מ‑`In_treatment` ל‑`added_to_library` לפני אישור וקומיט. אם המשתמש אישר אך עוד לא קומטת — אל תסמן.
- אַמֵּת הצלחה בתשובה ודווח למשתמש שהסטטוס עודכן ל‑"נוסף לספרייה".

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
