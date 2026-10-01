import sys, sqlite3, hashlib
from datetime import datetime, timezone
from pathlib import Path
from web3 import Web3
from fingerprint import leaf_hash, SOLWORKS_DB

HERE = Path(__file__).parent
RPC_URL = "https://testnet-rpc.monad.xyz"
CONTRACT = "0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06"
ABI = [{"inputs": [{"name": "", "type": "bytes32"}], "name": "anchoredAt",
        "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]

def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else SOLWORKS_DB
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)  # read-only
    live = {r[0]: r for r in src.execute(
        "SELECT id, ts, symbol, event_type, detail FROM discipline_log")}
    src.close()

    db = sqlite3.connect(HERE / "anchor.db")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=ABI)
    problems = 0

    batches = db.execute(
        "SELECT batch_id, entry_count, tx_hash FROM batches ORDER BY batch_id").fetchall()
    for batch_id, count, tx in batches:
        proofs = db.execute(
            "SELECT log_id, salt, leaf FROM proofs WHERE batch_id=? ORDER BY log_id",
            (batch_id,)).fetchall()
        fresh, broken = [], False
        for log_id, salt, saved_leaf in proofs:
            row = live.get(log_id)
            if row is None:
                print(f"  DELETED  entry {log_id}")
                problems += 1
                broken = True
                continue
            h = leaf_hash(salt, row)
            if h != saved_leaf:
                print(f"  EDITED   entry {log_id}")
                problems += 1
            fresh.append(h)

        ts = 0
        if not broken:
            root = hashlib.sha256(b"".join(bytes.fromhex(h) for h in fresh)).digest()
            ts = contract.functions.anchoredAt(root).call()
        if ts:
            when = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"Batch {batch_id}: {count} entries MATCH the onchain record from {when}")
        else:
            print(f"Batch {batch_id}: does NOT match the onchain record (tx {tx})")
            problems += 1

    anchored = {r[0] for r in db.execute("SELECT log_id FROM proofs WHERE batch_id IS NOT NULL")}
    waiting = len(set(live) - anchored)
    if waiting:
        print(f"{waiting} newer entries not anchored yet (normal until the next daily run).")
    print("\nRESULT: VERIFIED - log untouched" if problems == 0
          else f"\nRESULT: TAMPERING DETECTED ({problems} problem(s))")

if __name__ == "__main__":
    main()