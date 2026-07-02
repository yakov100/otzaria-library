#!/usr/bin/env python3
"""ממיר את משנה ברורה_links.json לפורמט הקישורים שגנרטור SeforimLibrary קורא.

קלט:  רשומות עם mb_char_index — אופסט תו גולמי בתוך שורת המשנה ברורה
      (line_index_1, אינדוקס 1-based) שבה מעוגנת הערת שער הציון.
פלט:  אותן רשומות עם:
        "Conection Type": "commentary"  (שער הציון — נושא כלים על המשנה ברורה)
        "start": <mb_char_index>        (שדה העוגן הגנרי שהגנרטור קורא)
      השדה mb_char_index מוסר.

הרצה:  python3 convert_mb_links_to_generator.py [נתיב לקובץ]
"""
import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "links" / "משנה ברורה_links.json"


def convert(path: Path) -> None:
    entries = json.loads(path.read_text(encoding="utf-8"))
    converted = 0
    for entry in entries:
        if "mb_char_index" in entry:
            entry["start"] = entry.pop("mb_char_index")
            converted += 1
        entry["Conection Type"] = "commentary"
    path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{path.name}: {len(entries)} רשומות, {converted} עוגנים הומרו ל-start")


if __name__ == "__main__":
    convert(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH)
