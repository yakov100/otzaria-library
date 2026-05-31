import json
from pathlib import Path

otzaria_path = Path("otzaria_hierarchy.json")
rambam_path = Path("rambam_hierarchy.json")

with otzaria_path.open("r", encoding="utf-8") as f:
    otzaria_data = json.load(f)

with rambam_path.open("r", encoding="utf-8") as f:
    rambam_data = json.load(f)

otzaria_books = set()
rambam_books = set()

otzaria_halachot = set()
rambam_halachot = set()

otzaria_prakim = set()
rambam_prakim = set()

otzaria_ot = set()
rambam_ot = set()

for book_name, book_data in otzaria_data.items():
    otzaria_books.add(book_name)
    for halachot_name, halachot_data in book_data.items():
        otzaria_halachot.add(halachot_name)
        for perek_name, perek_data in halachot_data.items():
            otzaria_prakim.add(perek_name)
            otzaria_ot.update(perek_data.keys())


for book_name, book_data in rambam_data.items():
    rambam_books.add(book_name)
    for halachot_name, halachot_data in book_data.items():
        rambam_halachot.add(halachot_name)
        for perek_name, perek_data in halachot_data.items():
            rambam_prakim.add(perek_name)
            rambam_ot.update(perek_data)


with Path("otzaria_books.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(otzaria_books)))

with Path("rambam_books.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(rambam_books)))

with Path("otzaria_halachot.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(otzaria_halachot)))

with Path("rambam_halachot.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(rambam_halachot)))

with Path("otzaria_prakim.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(otzaria_prakim)))

with Path("rambam_prakim.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(rambam_prakim)))

with Path("otzaria_ot.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(otzaria_ot)))

with Path("rambam_ot.txt").open("w", encoding="utf-8") as f:
    f.write("\n".join(sorted(rambam_ot)))


with Path("rambam_books.json").open("w", encoding="utf-8") as f:
    data = dict.fromkeys(sorted(rambam_books))
    json.dump(data, f, indent=2, ensure_ascii=False)

with Path("rambam_halachot.json").open("w", encoding="utf-8") as f:
    data = dict.fromkeys(sorted(rambam_halachot))
    json.dump(data, f, indent=2, ensure_ascii=False)

with Path("rambam_prakim.json").open("w", encoding="utf-8") as f:
    data = dict.fromkeys(sorted(rambam_prakim))
    json.dump(data, f, indent=2, ensure_ascii=False)

with Path("rambam_ot.json").open("w", encoding="utf-8") as f:
    data = dict.fromkeys(sorted(rambam_ot))
    json.dump(data, f, indent=2, ensure_ascii=False)
