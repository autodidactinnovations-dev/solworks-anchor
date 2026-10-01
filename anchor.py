import os, hashlib, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
ANCHOR_DB = HERE / "anchor.db"
RPC_URL = "https://testnet-rpc.monad.xyz"
CHAIN_ID = 10143
CONTRACT = "0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06"
EXPECTED_WALLET = "0xc951fDA229397f782d7828B55104b1eA9830F0EB"
ABI = [
    {"inputs": [{"name": "root", "type": "bytes32"}, {"name": "entryCount", "type": "uint256"}],
     "name": "anchor", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "", "type": "bytes32"}], "name": "anchoredAt",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]

def main():
    db = sqlite3.connect(ANCHOR_DB)
    pending = db.execute(
        "SELECT log_id, leaf FROM proofs WHERE batch_id IS NULL ORDER BY log_id").fetchall()
    if not pending:
        print("Nothing new to anchor.")
        return

    root = hashlib.sha256(b"".join(bytes.fromhex(leaf) for _, leaf in pending)).digest()

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if w3.eth.chain_id != CHAIN_ID:
        raise SystemExit("STOP: not connected to Monad testnet.")
    acct = w3.eth.account.from_key(os.environ["PRIVATE_KEY"])
    if acct.address.lower() != EXPECTED_WALLET.lower():
        raise SystemExit("STOP: this key is not the throwaway wallet.")

    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=ABI)
    tx = contract.functions.anchor(root, len(pending)).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": CHAIN_ID,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("Sent. Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise SystemExit(f"Transaction failed: {Web3.to_hex(tx_hash)}")

    now = datetime.now(timezone.utc).isoformat()
    cur = db.execute(
        "INSERT INTO batches(root, entry_count, created_at, tx_hash, anchored_at) VALUES (?,?,?,?,?)",
        ("0x" + root.hex(), len(pending), now, Web3.to_hex(tx_hash), now))
    ids = [p[0] for p in pending]
    db.execute(f"UPDATE proofs SET batch_id=? WHERE log_id IN ({','.join('?' * len(ids))})",
               (cur.lastrowid, *ids))
    db.commit()
    print(f"Anchored {len(pending)} entries.")
    print(f"Root: 0x{root.hex()}")
    print(f"Tx:   {Web3.to_hex(tx_hash)}")

if __name__ == "__main__":
    main()