import json
import shutil
from pathlib import Path

dicta_base_path = Path(r"C:\Users\User\Downloads\DictaToOtzaria\DictaToOtzaria\ערוך\ספרים")
dicta_target_path = Path("dicta_target")
dicta_links_path = Path("dicta_links")
dicta_links_target_path = Path("dicta_links_target")
dicta_books_json_path = Path("dicta_books.json")


target_rambam_books = Path("test") / "rambam"
target_rambam_books.mkdir(parents=True, exist_ok=True)
target_dicta_books = Path("test") / "dicta"
target_dicta_books.mkdir(parents=True, exist_ok=True)

dicta_books_json = json.loads(dicta_books_json_path.read_text(encoding="utf-8"))
dicta_books = []
for rambam_book, dicta_books_list in dicta_books_json.items():
    target_rambam_book = target_rambam_books / f"{rambam_book}.txt"
    source_rambam_book = Path("mefarshim") / f"{rambam_book}.txt"
    if source_rambam_book.exists():
        shutil.copy(source_rambam_book, target_rambam_book)
    else:
        print(f"Warning: Rambam book '{rambam_book}' not found at '{source_rambam_book}'")
    dicta_books.extend(dicta_books_list)

found_books = set()

for root, _, files in dicta_base_path.walk():
    for file in files:
        file_path = root / file
        if file_path.suffix.lower() != ".txt":
            continue
        book_name = file_path.stem
        if book_name not in dicta_books:
            continue
        target_file_path = target_dicta_books / file_path.relative_to(dicta_base_path)
        target_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_path, target_file_path)
        found_books.add(book_name)

missing_books = set(dicta_books) - found_books
if missing_books:
    print("Warning: The following books were listed in dicta_books.json but not found in the source directory:")
    for book in missing_books:
        print(f" - {book}")

# for root, _, files in dicta_links_path.walk():
#     for file in files:
#         file_path = root / file
#         if file_path.suffix.lower() != ".json":
#             continue
#         book_name = file_path.stem.replace("_links", "")
#         if book_name not in dicta_books:
#             continue
#         target_file_path = dicta_links_target_path / file_path.relative_to(dicta_links_path)
#         target_file_path.parent.mkdir(parents=True, exist_ok=True)
#         shutil.move(file_path, target_file_path)
