import json
import os
import shutil
from pathlib import Path

BASE_PATH = Path("אוצריא")
LOCAL_PATH = Path(r"C:\אוצריא")
LOCAL_PATH_SOURCE = Path(r"C:\אוצריא")
DEL_LIST_FILE_NAME = "del_list.txt"
MANIFEST_FILE_NAME = "files_manifest.json"
DICTA_MANIFEST_FILE_NAME = "files_manifest_dicta.json"


def copy_manifest(is_dicta: bool = False) -> None:
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    manifest_file_name = MANIFEST_FILE_NAME if not is_dicta else DICTA_MANIFEST_FILE_NAME
    shutil.copy(LOCAL_PATH / manifest_file_name, BASE_PATH / manifest_file_name)


def copy_files() -> None:
    shutil.copytree(BASE_PATH, LOCAL_PATH, dirs_exist_ok=True, ignore=lambda _, files: [DEL_LIST_FILE_NAME] if DEL_LIST_FILE_NAME in files else [])


def remove_files() -> None:
    del_list_file_path = BASE_PATH / DEL_LIST_FILE_NAME
    with del_list_file_path.open("r", encoding="utf-8") as f:
        content = f.readlines()
    for file_path in content:
        file_path = file_path.strip()
        if not file_path:
            continue
        full_path = LOCAL_PATH / file_path
        if full_path.exists():
            full_path.unlink()
    del_list_file_path.unlink()


def remove_empty_dirs() -> None:
    for root, dirs, _ in LOCAL_PATH.walk(top_down=False):
        for dir_name in dirs:
            dir_path = root / dir_name
            if not any(dir_path.iterdir()):
                dir_path.rmdir()


def copy_new(is_dicta: bool = False) -> None:
    manifest_file_name = MANIFEST_FILE_NAME if not is_dicta else DICTA_MANIFEST_FILE_NAME
    new_manifest_path = LOCAL_PATH_SOURCE / manifest_file_name
    old_manifest_file_path = BASE_PATH / manifest_file_name

    with new_manifest_path.open("r", encoding="utf-8") as f:
        new_manifest_content = json.load(f)
    with old_manifest_file_path.open("r", encoding="utf-8") as f:
        old_manifest_content = json.load(f)

    if new_manifest_content == old_manifest_content:
        return

    for book_name, value in new_manifest_content.items():
        if value["hash"] == old_manifest_content.get(book_name, {}).get("hash"):
            continue
        target_folder_components = book_name.split("/")
        file_type = "אוצריא" if "אוצריא" in target_folder_components else "links"
        target_path = BASE_PATH.joinpath(*target_folder_components[target_folder_components.index(file_type):])
        source_path = LOCAL_PATH_SOURCE.joinpath(*target_folder_components[target_folder_components.index(file_type):])
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, target_path)

    del_list = []
    for book_name in old_manifest_content:
        if book_name in new_manifest_content:
            continue
        target_folder_components = book_name.split("/")
        file_type = "אוצריא" if "אוצריא" in target_folder_components else "links"
        del_list.append(os.sep.join(*target_folder_components[target_folder_components.index(file_type):]))

    with old_manifest_file_path.open("w", encoding="utf-8") as f:
        json.dump(new_manifest_content, f, indent=2, ensure_ascii=False)

    with (BASE_PATH / DEL_LIST_FILE_NAME).open("a", encoding="utf-8") as f:
        f.write("\n".join(del_list) + "\n")


if __name__ == "__main__":
    copy_new()
    copy_new(is_dicta=True)
