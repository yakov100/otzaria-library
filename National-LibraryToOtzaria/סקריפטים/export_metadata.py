import csv
import json

src = r'c:\Users\User\Desktop\kiwix_otzaria\rambam\metadata.json'
out = r'c:\Users\User\Desktop\kiwix_otzaria\rambam\books_rambam.csv'

with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

with open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['MefareshDesc', 'AuthorName'])
    for v in data.values():
        w.writerow([v.get('MefareshDesc', ''), v.get('AuthorName', '')])

print(f'wrote {len(data)} rows -> {out}')
