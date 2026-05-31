import json
import re
from pathlib import Path

rambam_json_file = Path("output.json")
with rambam_json_file.open("r", encoding="utf-8") as f:
    rambam_data = json.load(f)

rambam_dict = {}
for book in rambam_data:
    book_title = book.get("Desc").strip()
    book_data = {}
    for halachot in book.get("sub_levels", []):
        halachot_data = {}
        halachot_title = halachot.get("Desc").strip()
        for perek in halachot.get("sub_levels", []):
            perek_data = []
            perek_title = perek.get("Desc").strip()
            for ot in perek.get("sub_levels", []):
                if not ot["mefarshim"]:
                    continue
                ot_title = ot.get("Desc").strip()
                perek_data.append(ot_title)
            if perek_data:
                halachot_data[perek_title] = perek_data
        if halachot_data:
            book_data[halachot_title] = halachot_data
    if book_data:
        rambam_dict[book_title] = book_data

letter_re = re.compile(r"^\(([^)]*)\)")


def collect_letters(text: str) -> list[str]:
    letters: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = letter_re.match(line)
        if match:
            letter = match.group(1)
            if letter not in seen:
                seen.add(letter)
                letters.append(letter)
    return letters


otzaria_dict = {}
otzaria_rambam_path = Path('משנה תורה')
for folder in otzaria_rambam_path.iterdir():
    if not folder.is_dir():
        continue
    if folder.name == "הקדמה":
        continue
    book_name = folder.name.strip()
    otzaria_dict[book_name] = {}
    for file in folder.iterdir():
        if not file.is_file() or file.suffix.lower() != '.txt':
            continue
        halachot_name = file.stem.strip().replace("משנה תורה, ", "").strip()
        otzaria_dict[book_name][halachot_name] = {}
        with file.open("r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")
        header = None
        for index, line in enumerate(lines, start=1):
            line = line.strip()
            if line.startswith("<h2>") and line.endswith("</h2>"):
                header = line.replace("<h2>", "").replace("</h2>", "").strip()
                otzaria_dict[book_name][halachot_name][header] = {}
                continue
            if not header:
                continue
            if line.startswith("(") and ")" in line:
                ot = line.split(")")[0].strip("(")
                if not ot.strip():
                    continue
                otzaria_dict[book_name][halachot_name][header][ot] = index

with Path("rambam_hierarchy.json").open("w", encoding="utf-8") as f:
    json.dump(rambam_dict, f, ensure_ascii=False, indent=4)

with Path("otzaria_hierarchy.json").open("w", encoding="utf-8") as f:
    json.dump(otzaria_dict, f, ensure_ascii=False, indent=4)
