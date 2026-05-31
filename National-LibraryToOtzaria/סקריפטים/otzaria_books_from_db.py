import csv
import sqlite3

db = r'C:\ProgramData\otzaria\books\seforim.db'
out = r'c:\Users\User\Desktop\kiwix_otzaria\rambam\books_otzaria.csv'

c = sqlite3.connect(db)
q = """
SELECT b.id, b.title,
       COALESCE(GROUP_CONCAT(a.name, '; '), '') AS authors
FROM book b
LEFT JOIN book_author ba ON ba.bookId = b.id
LEFT JOIN author a ON a.id = ba.authorId
GROUP BY b.id, b.title
ORDER BY b.title
"""
rows = list(c.execute(q))
with open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['id', 'title', 'authors'])
    w.writerows(rows)
print(f'wrote {len(rows)} rows -> {out}')
