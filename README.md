# SolWorks Anchor

**Tamper-evident provenance for a private trading-discipline log, anchored on Monad.**

Built for the Monad Metropolis hackathon, Trust, Identity & AI Infrastructure track.

## The problem

A trading journal is only useful if it's honest. But a journal kept on your own computer can be quietly rewritten after the fact: a bad call deleted, a "rule followed" added a week later, a date nudged. No one can tell, including you.

Publishing the journal fixes that, but it gives away your positions, amounts and reasoning.

## What SolWorks Anchor does

SolWorks is my personal crypto discipline framework. Every decision goes into its **Discipline Log**: rules followed, rules broken, alerts acted on or dismissed, notes.

SolWorks Anchor makes that log **tamper-evident without making it public**:

1. **Fingerprint.** Each log entry is hashed with its own random salt (SHA-256). The salt means nobody can guess an entry's content from its hash.
2. **Anchor.** Every night at 9 PM, the new fingerprints are combined into one 32-byte root and written to a minimal contract on Monad testnet. The chain records the root and the block time.
3. **Verify.** At any later point, the log is re-hashed as it is *right now*, and each root is checked against the chain. If a single character of any anchored entry changed, or an entry was deleted, its batch no longer matches.

**Only hashes go onchain.** No amounts, holdings, symbols or text.

**What this proves:** the log hasn't been edited, deleted from or backdated since each entry was anchored.
**What it doesn't prove:** that the decisions were good.

## See it work

The SolWorks dashboard has a **Verify** tab with two buttons:

- **Verify my log**: recomputes every anchored batch from the live log and checks it against Monad. Currently: 60 entries across 6 nightly batches, all ✓ VERIFIED.
- **Tamper demo**: copies the log to a throwaway temp file, quietly edits one old entry in the copy, and verifies the copy. The edited entry's batch turns red, **✗ TAMPERING DETECTED**, while the others stay green. The real log is never written to, and the copy is deleted afterwards.

Each batch shows the root stored onchain next to the root recomputed now, with a link to its transaction.

## Contract

| | |
|---|---|
| Network | Monad Testnet (chain ID 10143) |
| Address | `0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06` |
| Source | [`contracts/SolWorksAnchor.sol`](contracts/SolWorksAnchor.sol), verified via Sourcify |

The contract is deliberately small: only the owner can anchor, a root can be anchored once, and `anchoredAt(root)` returns the timestamp it landed onchain (0 if never). Each anchor emits an `Anchored` event.

## How it's built

| File | Job |
|---|---|
| `fingerprint.py` | Reads the SolWorks log **read-only** and stores a salt and hash for each new entry in a local `anchor.db` |
| `anchor.py` | Combines unanchored hashes into one root and sends it to the contract. Refuses to run on the wrong chain or with the wrong wallet |
| `verify.py` | Recomputes every batch root and checks it onchain. Usable from the command line or the dashboard |
| `verify_tab.py` | The Verify tab in the SolWorks Streamlit dashboard |
| `tamper.py` | Command-line version of the tamper demo (edits a copy only) |

Nightly anchoring runs from Windows Task Scheduler (fingerprint, then anchor).

Salts and hashes stay in `anchor.db` on my machine and are not committed. Anchoring uses a throwaway testnet wallet whose key lives in a local `.env`.

## Run it

Requires Python 3.13 and `pip install web3 python-dotenv`.

```
python fingerprint.py      # hash new log entries
python anchor.py           # anchor them on Monad testnet
python verify.py           # check the whole log against the chain
python verify.py copy.db   # check a different copy of the log
```

`fingerprint.py` expects the path to a SolWorks database (`SOLWORKS_DB` at the top of the file). `anchor.py` expects `PRIVATE_KEY` in `.env`.

## Limits, honestly

- **Tamper-evident, not tamper-proof.** Nothing stops an edit. It just can't go unnoticed.
- **Batch-level, not entry-level.** A root covers a whole night's entries, so a mismatch identifies the batch, and the local hashes identify the entry. Proving a single entry to an outsider currently means sharing that batch's hashes (still not its contents).
- **Anything not yet anchored is unprotected.** An entry is covered from the next 9 PM run onward.
- **Testnet.** Monad testnet, with a throwaway wallet.

## Next

- **Per-entry Merkle proofs**, so one entry can be proven onchain without revealing anything else in its batch.
- **Public verifier page**, so someone I share an entry with can check it themselves.
- **Mainnet**, once the design settles.

---

Built by William "Billy" Henry, [Autodidact Innovations](https://github.com/autodidactinnovations-dev).
