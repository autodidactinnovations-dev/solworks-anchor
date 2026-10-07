"""Write docs/ledger.json for the public verifier page.

Contains only what is already public onchain: batch number, transaction hash,
root and entry count. No salts, no leaf hashes, no log contents.
"""
import sys, json, sqlite3
from pathlib import Path

HERE = Path(__file__).parent
ANCHOR_DB = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "anchor.db"
OUT = HERE / "docs" / "ledger.json"


def main():
    db = sqlite3.connect(f"file:{ANCHOR_DB}?mode=ro", uri=True)  # read-only
    batches = [
        {"batch": batch_id, "tx": tx, "root": root, "entries": count}
        for batch_id, tx, root, count in db.execute(
            "SELECT batch_id, tx_hash, root, entry_count FROM batches "
            "WHERE tx_hash IS NOT NULL ORDER BY batch_id")
    ]
    db.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"batches": batches}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(batches)} batches to {OUT}")


if __name__ == "__main__":
    main()
