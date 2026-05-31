import json
import re
from dataclasses import dataclass
from pathlib import Path

from gematriapy import gematria
from pyluach import dates


@dataclass
class YearRange:
    start_year_greg: int | None
    end_year_greg: int | None
    start_year_hebrew: str | None
    end_year_hebrew: str | None
    year_desc: str | None


def get_year(year: str | None) -> tuple[int | None, str | None]:
    if not year or not year.strip():
        return None, None
    int_year = gematria.to_number(year) + 5000
    heb_date = dates.HebrewDate(int_year, 1, 1)
    heb_date_str = heb_date.hebrew_year(thousands=True)
    return heb_date.to_greg().to_pydate().year, heb_date_str


def get_date(year: str | None) -> YearRange | None:
    if not year or not year.strip():
        return None
    if '"' not in year:
        return None
    year_desc = None
    desc_match = re.search(r"\((.*?)\)", year)
    if desc_match:
        year_desc = desc_match.group(1).strip()
    year = re.sub(r"\(.*\)", "", year)
    year_split = year.split('-')
    end_year = None
    if len(year_split) == 2:
        end_year = year_split[1].strip()
    start_year = year_split[0].strip()
    start_year_date, start_year_hebrew = get_year(start_year)
    end_year_date, end_year_hebrew = get_year(end_year)
    return YearRange(
        start_year_greg=start_year_date,
        end_year_greg=end_year_date,
        start_year_hebrew=start_year_hebrew,
        end_year_hebrew=end_year_hebrew,
        year_desc=year_desc
    )


rambam_metadata_path = Path("metadata.json")
otzaria_metadata_path = Path("otzaria_metadata.json")
with rambam_metadata_path.open("r", encoding="utf-8") as f:
    metadata = json.load(f)
otzaria_metadata = []
for book in metadata.values():
    book_entry = {}
    book_entry["heAuthors"] = [book["AuthorName"]] if book["AuthorName"] else []
    book_entry["title"] = book["MefareshDesc"] if book["MefareshDesc"] else None
    book_entry["heShortDesc"] = book["MefareshTypeDesc"] if book["MefareshTypeDesc"] else None
    book_date = get_date(book["PrintYearDesc"])
    if book_date:
        book_entry["pubDateHeb"] = [
            book_date.start_year_hebrew,
        ]
        book_entry["pubDate"] = [
            book_date.start_year_greg,
        ]
        if book_date.end_year_greg:
            book_entry["pubDate"].append(book_date.end_year_greg)
        if book_date.end_year_hebrew:
            book_entry["pubDateHeb"].append(book_date.end_year_hebrew)
        if book_date.year_desc:
            book_entry["compDateStringHe"] = book_date.year_desc
    otzaria_metadata.append(book_entry)

with otzaria_metadata_path.open("w", encoding="utf-8") as f:
    json.dump(otzaria_metadata, f, ensure_ascii=False, indent=2)
