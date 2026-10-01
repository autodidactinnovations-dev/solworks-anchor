import sqlite3, json, hashlib, secrets
from datetime import datetime, timezone
from pathlib import Path

SOLWORKS_DB = r"C:\Users\billy\Downloads\solworks-phase3\solworks\data\solworks.db"
ANCHOR_DB = Path(__file__).with_name("anchor.db")

def canonical(row):
    return json.dumps(list(row), ensure_ascii=False, separators=(",", ":"))

def leaf_hash(salt, row):
    return hashlib.sha256((salt + "|" + canonical(row)).encode("utf-8")).hexdigest()

def open_anchor():
    db = sqlite3.connect(ANCHOR_DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS proofs(
      log_id INTEGER PRIMARY KEY, salt TEXT NOT NULL, leaf TEXT NOT NULL,
      hashed_at TEXT NOT NULL, batch_id INTEGER);
    CREATE TABLE IF NOT EXISTS batches(
      batch_id INTEGER PRIMARY KEY AUTOINCREMENT, root TEXT NOT NULL,
      entry_count INTEGER NOT NULL, created_at TEXT NOT NULL,
      tx_hash TEXT, anchored_at TEXT);
    """)
    return db

def read_log():
    src = sqlite3.connect(f"file:{SOLWORKS_DB}?mode=ro", uri=True)  # read-only
    rows = src.execute(
        "SELECT id, ts, symbol, event_type, detail FROM discipline_log ORDER BY id"
    ).fetchall()
    src.close()
    return rows

def main():
    rows = read_log()
    db = open_anchor()
    done = {r[0] for r in db.execute("SELECT log_id FROM proofs")}
    now = datetime.now(timezone.utc).isoformat()
    new = 0
    for row in rows:
        if row[0] in done:
            continue
        salt = secrets.token_hex(16)
        db.execute("INSERT INTO proofs(log_id, salt, leaf, hashed_at) VALUES (?,?,?,?)",
                   (row[0], salt, leaf_hash(salt, row), now))
        new += 1
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM proofs").fetchone()[0]
    print(f"Fingerprinted {new} new entries. Total fingerprinted: {total}")
    for log_id, leaf in db.execute("SELECT log_id, leaf FROM proofs ORDER BY log_id DESC LIMIT 3"):
        print(f"  entry {log_id}: {leaf[:16]}...")
    db.close()

if __name__ == "__main__":
    main()