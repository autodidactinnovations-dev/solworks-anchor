import sys, sqlite3, hashlib, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
from web3 import Web3
from fingerprint import leaf_hash, SOLWORKS_DB

HERE = Path(__file__).parent
RPC_URL = "https://testnet-rpc.monad.xyz"
CONTRACT = "0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06"
EXPLORER = "https://testnet.monadexplorer.com"
ABI = [{"inputs": [{"name": "", "type": "bytes32"}], "name": "anchoredAt",
        "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]


def check(src_path=SOLWORKS_DB) -> dict:
    """Recompute every anchored batch from the log at src_path and ask the
    contract whether that exact root was anchored. Opens the log read-only."""
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)  # read-only
    live = {r[0]: r for r in src.execute(
        "SELECT id, ts, symbol, event_type, detail FROM discipline_log")}
    src.close()

    db = sqlite3.connect(HERE / "anchor.db")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=ABI)

    batches, problems = [], []
    for batch_id, count, saved_root, tx in db.execute(
            "SELECT batch_id, entry_count, root, tx_hash FROM batches ORDER BY batch_id").fetchall():
        proofs = db.execute(
            "SELECT log_id, salt, leaf FROM proofs WHERE batch_id=? ORDER BY log_id",
            (batch_id,)).fetchall()
        fresh, broken, bad = [], False, []
        for log_id, salt, saved_leaf in proofs:
            row = live.get(log_id)
            if row is None:
                bad.append((log_id, "DELETED"))
                broken = True
                continue
            h = leaf_hash(salt, row)
            if h != saved_leaf:
                bad.append((log_id, "EDITED"))
            fresh.append(h)
        problems += bad

        ts, root_hex = 0, None
        if not broken:
            root = hashlib.sha256(b"".join(bytes.fromhex(h) for h in fresh)).digest()
            root_hex = "0x" + root.hex()
            ts = contract.functions.anchoredAt(root).call()
        if not ts:
            problems.append((None, f"Batch {batch_id} root not found onchain"))
        batches.append({
            "batch_id": batch_id, "entries": count, "tx": tx,
            "anchored_root": saved_root, "recomputed_root": root_hex,
            "onchain_at": datetime.fromtimestamp(ts, timezone.utc) if ts else None,
            "match": bool(ts), "bad_entries": bad,
        })

    anchored = {r[0] for r in db.execute("SELECT log_id FROM proofs WHERE batch_id IS NOT NULL")}
    db.close()
    return {"ok": not problems, "batches": batches, "problems": problems,
            "waiting": len(set(live) - anchored), "checked_at": datetime.now(timezone.utc)}


def tamper_demo() -> tuple[int, dict]:
    """Copy the live log to a throwaway temp file, quietly edit one entry in
    the COPY, and verify the copy. The real log is never written to, and the
    copy is deleted afterwards."""
    tmpdir = Path(tempfile.mkdtemp(prefix="solworks_tamper_"))
    try:
        copy = tmpdir / "tamper_copy.db"
        src = sqlite3.connect(f"file:{SOLWORKS_DB}?mode=ro", uri=True)
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        row = dst.execute("SELECT id FROM discipline_log ORDER BY id LIMIT 1").fetchone()
        dst.execute("UPDATE discipline_log SET detail = detail || ' (quietly edited later)' "
                    "WHERE id=?", (row[0],))
        dst.commit()
        dst.close()
        return row[0], check(copy)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else SOLWORKS_DB
    r = check(src_path)
    for b in r["batches"]:
        for log_id, kind in b["bad_entries"]:
            print(f"  {kind:<8} entry {log_id}")
        if b["match"]:
            when = b["onchain_at"].strftime("%Y-%m-%d %H:%M UTC")
            print(f"Batch {b['batch_id']}: {b['entries']} entries MATCH the onchain record from {when}")
        else:
            print(f"Batch {b['batch_id']}: does NOT match the onchain record (tx {b['tx']})")
    if r["waiting"]:
        print(f"{r['waiting']} newer entries not anchored yet (normal until the next daily run).")
    print("\nRESULT: VERIFIED - log untouched" if r["ok"]
          else f"\nRESULT: TAMPERING DETECTED ({len(r['problems'])} problem(s))")


if __name__ == "__main__":
    main()
