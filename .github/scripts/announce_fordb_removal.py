#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""מפרסם בפורום אוצריא הודעה על שורות ForDB שהוסרו אוטומטית ע"י ה-CI.

קורא את fordb_removed.json (שכותב validate_fordb_book_names.py --fix) ושולח הודעה
לנושא הייעודי בפורום. שימוש חוזר ב-OtzariaForumClient מ-send_update/.
סביבה: FORUM_TOPIC_ID, USER_NAME, PASSWORD (חובה); FORDB_COMMIT_SHA (אופציונלי, לקישור).
כשל בפרסום אינו פטאלי - ההסרה עצמה כבר בוצעה ונדחפה.
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "send_update"))
from otzaria_forum import OtzariaForumClient  # noqa: E402

TZ = ZoneInfo("Asia/Jerusalem")
REPORT = os.path.join(REPO_ROOT, "fordb_removed.json")


def heb_date():
    try:
        from pyluach import dates
        return dates.HebrewDate.from_pydate(datetime.now(tz=TZ).date()).hebrew_date_string()
    except Exception:
        return datetime.now(tz=TZ).strftime("%Y-%m-%d")


def build_content(removed):
    by_file = {}
    for r in removed:
        by_file.setdefault(r["file"], []).append(r["name"])
    parts = [
        "# הסרה אוטומטית של שורות ForDB\n",
        f"**{heb_date()}**\n",
        "\nה-CI הסיר אוטומטית את השורות הבאות מקבצי ForDB, כי הספרים אינם קיימים ב-DB "
        "(לא נארזו לספרייה — למשל ספר שהוזז לתיקייה לא-נארזת). אם ספר אמור היה להיכלל, "
        "יש לארוז אותו לנתיב תקין ולהחזיר את השורה:\n",
    ]
    for f in sorted(by_file):
        parts.append(f"\n## {f}:\n" + "\n".join(f"* {n}" for n in sorted(by_file[f])) + "\n")
    repo, sha = os.getenv("GITHUB_REPOSITORY"), os.getenv("FORDB_COMMIT_SHA")
    if repo and sha:
        parts.append(f"\n[הקומיט](https://github.com/{repo}/commit/{sha})\n")
    return "".join(parts)


def main():
    if not os.path.isfile(REPORT) or os.path.getsize(REPORT) == 0:
        print("אין fordb_removed.json — אין מה לפרסם.")
        return 0
    with open(REPORT, encoding="utf-8") as fh:
        removed = json.load(fh)
    if not removed:
        print("דוח ההסרה ריק — אין מה לפרסם.")
        return 0

    topic = os.getenv("FORUM_TOPIC_ID")
    username = os.getenv("USER_NAME")
    password = os.getenv("PASSWORD")
    content = build_content(removed)
    print("----- forum post -----")
    print(content)
    print("----------------------")
    if not (topic and username and password):
        print("⏭️  חסר FORUM_TOPIC_ID / USER_NAME / PASSWORD — לא נשלח.")
        return 0

    client = OtzariaForumClient(username.strip().replace(" ", "+"), password.strip())
    try:
        client.login()
        client.send_post(content, int(topic))
        print(f"✅ פורסם בפורום (topic {topic}).")
    except Exception as e:  # פרסום נכשל אינו פטאלי
        print(f"⚠️  פרסום בפורום נכשל (לא פטאלי): {e}")
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
