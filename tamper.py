import sqlite3

conn = sqlite3.connect("tamper_copy.db")  # the COPY only
row = conn.execute("SELECT id FROM discipline_log ORDER BY id LIMIT 1").fetchone()
conn.execute("UPDATE discipline_log SET detail = detail || ' (quietly edited later)' WHERE id=?",
             (row[0],))
conn.commit()
conn.close()
print(f"Changed entry {row[0]} in the COPY only.")