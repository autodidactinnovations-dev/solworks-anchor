"""Export a proof for ONE log entry, so someone else can verify it on the
public verifier page.

    python export_proof.py 1                  # writes docs/proofs/entry-1.json
    python export_proof.py 1 path\\to\\anchor.db

The proof reveals that entry's full text and its salt. Every other entry in
the batch appears only as a salted hash, which reveals nothing about it.
Only share entries you are happy for the recipient to read.
"""
import sys, json, sqlite3
from pathlib import Path
from fingerprint import leaf_hash, canonical, SOLWORKS_DB

HERE = Path(__file__).parent
CONTRACT = "0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06"
CHAIN_ID = 10143


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python export_proof.py <log_id> [anchor.db]")
    log_id = int(sys.argv[1])
    anchor_db = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "anchor.db"

    db = sqlite3.connect(f"file:{anchor_db}?mode=ro", uri=True)  # read-only
    hit = db.execute("SELECT salt, batch_id FROM proofs WHERE log_id=?", (log_id,)).fetchone()
    if not hit or hit[1] is None:
        raise SystemExit(f"Entry {log_id} has not been anchored yet.")
    salt, batch_id = hit
    leaves = db.execute(
        "SELECT log_id, leaf FROM proofs WHERE batch_id=? ORDER BY log_id", (batch_id,)).fetchall()
    root, tx = db.execute(
        "SELECT root, tx_hash FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
    db.close()

    src = sqlite3.connect(f"file:{SOLWORKS_DB}?mode=ro", uri=True)  # read-only
    row = src.execute(
        "SELECT id, ts, symbol, event_type, detail FROM discipline_log WHERE id=?",
        (log_id,)).fetchone()
    src.close()
    if row is None:
        raise SystemExit(f"Entry {log_id} is missing from the log.")

    position = [lid for lid, _ in leaves].index(log_id)
    if leaf_hash(salt, row) != leaves[position][1]:
        raise SystemExit(f"Entry {log_id} no longer matches its fingerprint. Not exporting.")

    proof = {
        "version": 1,
        "chainId": CHAIN_ID,
        "contract": CONTRACT,
        "batch": batch_id,
        "tx": tx,
        "root": root,
        "entry": {"fields": ["id", "ts", "symbol", "event_type", "detail"],
                  "values": list(row), "canonical": canonical(row)},
        "salt": salt,
        "position": position,
        "leaves": [leaf for _, leaf in leaves],
    }
    out = HERE / "docs" / "proofs" / f"entry-{log_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Batch {batch_id}: entry {position + 1} of {len(leaves)}")


if __name__ == "__main__":
    main()
