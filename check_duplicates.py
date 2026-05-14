#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
סקריפט לבדיקת כפילויות בשמות קבצים
עובר על כל הנתיבים מהקובץ update-library.yml ומזהה קבצים עם אותו שם
"""

import os
from collections import defaultdict
from pathlib import Path

# רשימת כל הנתיבים מהקובץ update-library.yml (שורות 6-33)
PATHS = [
    "Ben-YehudaToOtzaria/ספרים/אוצריא",
    "DictaToOtzaria/ערוך/ספרים/אוצריא",
    "DictaToOtzaria/לא ערוך/ספרים/אוצריא",
    "OnYourWayToOtzaria/ספרים/אוצריא",
    "OraytaToOtzaria/ספרים/אוצריא",
    "tashmaToOtzaria/ספרים/אוצריא",
    "extraBooks/SefariaToOtzria/sefaria_export/ספרים/אוצריא",
    "extraBooks/SefariaToOtzria/sefaria_api/ספרים/אוצריא",
    "MoreBooks/ספרים/אוצריא",
    "ToratEmetToOtzaria/ספרים/אוצריא",
    "wikiJewishBooksToOtzaria/ספרים/אוצריא",
    "wikisourceToOtzaria/ספרים/אוצריא",
    "pninimToOtzaria/ספרים/אוצריא",
    "Ben-YehudaToOtzaria/links",
    "DictaToOtzaria/links",
    "OnYourWayToOtzaria/links",
    "OraytaToOtzaria/links",
    "tashmaToOtzaria/links",
    "extraBooks/SefariaToOtzria/sefaria_export/links",
    "extraBooks/SefariaToOtzria/sefaria_api/links",
    "MoreBooks/links",
    "ToratEmetToOtzaria/links",
    "wikiJewishBooksToOtzaria/links",
    "wikisourceToOtzaria/links",
    "DictaToOtzaria/לא ערוך/links",
    "DictaToOtzaria/ערוך/links",
    "pninimToOtzaria/links",
]

def find_duplicates():
    """מוצא כפילויות בשמות קבצים"""
    # מילון: שם קובץ -> רשימת נתיבים מלאים
    files_dict = defaultdict(list)
    
    print("סורק קבצים...")
    
    for path in PATHS:
        if not os.path.exists(path):
            print(f"⚠️  התיקייה לא קיימת: {path}")
            continue
            
        # עובר על כל הקבצים בתיקייה (כולל תתי-תיקיות)
        for root, dirs, files in os.walk(path):
            for filename in files:
                full_path = os.path.join(root, filename)
                files_dict[filename].append(full_path)
    
    # מוצא כפילויות
    duplicates = {name: paths for name, paths in files_dict.items() if len(paths) > 1}
    
    if not duplicates:
        print("\n✅ לא נמצאו כפילויות!")
        return
    
    # מפריד כפילויות לשתי קבוצות
    dicta_lo_aruch_paths = [
        "DictaToOtzaria/לא ערוך/ספרים/אוצריא",
        "DictaToOtzaria/לא ערוך/links"
    ]
    
    general_duplicates = {}
    dicta_duplicates = {}
    
    for filename, paths in duplicates.items():
        # בדיקה אם יש נתיב שמכיל "לא ערוך"
        has_dicta_lo_aruch = any(
            any(dicta_path in path for dicta_path in dicta_lo_aruch_paths)
            for path in paths
        )
        
        if has_dicta_lo_aruch:
            dicta_duplicates[filename] = paths
        else:
            general_duplicates[filename] = paths
    
    # הדפסת כפילויות כלליות
    print(f"\n{'='*80}")
    print("חלק 1: כפילויות כלליות")
    print(f"{'='*80}")
    
    if general_duplicates:
        print(f"\n🔍 נמצאו {len(general_duplicates)} כפילויות כלליות:\n")
        for filename, paths in sorted(general_duplicates.items()):
            print(f"\n📄 {filename} ({len(paths)} פעמים):")
            for path in sorted(paths):
                print(f"   • {path}")
    else:
        print("\n✅ לא נמצאו כפילויות כלליות")
    
    # הדפסת כפילויות של דיקטה לא ערוך
    print(f"\n\n{'='*80}")
    print("חלק 2: כפילויות הכוללות 'DictaToOtzaria/לא ערוך'")
    print(f"{'='*80}")
    
    if dicta_duplicates:
        print(f"\n🔍 נמצאו {len(dicta_duplicates)} כפילויות עם 'לא ערוך':\n")
        for filename, paths in sorted(dicta_duplicates.items()):
            print(f"\n📄 {filename} ({len(paths)} פעמים):")
            for path in sorted(paths):
                print(f"   • {path}")
    else:
        print("\n✅ לא נמצאו כפילויות עם 'לא ערוך'")
    
    # סיכום
    print(f"\n{'='*80}")
    print(f"סה\"כ כפילויות כלליות: {len(general_duplicates)}")
    print(f"סה\"כ כפילויות עם 'לא ערוך': {len(dicta_duplicates)}")
    print(f"סה\"כ כולל: {len(duplicates)}")
    print(f"{'='*80}")

if __name__ == "__main__":
    find_duplicates()
