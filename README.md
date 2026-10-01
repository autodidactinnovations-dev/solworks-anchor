# SolWorks Anchor

Tamper-proof provenance for personal trading discipline.

SolWorks is my personal crypto discipline framework. SolWorks Anchor adds an onchain provenance layer: every decision in the SolWorks log is fingerprinted (salted SHA-256), and fingerprints are anchored to a minimal contract on Monad testnet. Anyone can verify a log entry was never edited or backdated.

Only hashes go onchain. No amounts, holdings, or personal data.

**What this proves:** the log is untampered. **What it doesn't prove:** that the decisions were good.

## Contract
- Network: Monad Testnet (chain ID 10143)
- Address: `0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06`
- Source verified via Sourcify

Built for the Monad Metropolis hackathon (Trust, Identity & AI Infrastructure track) by William "Billy" Henry, Autodidact Innovations.
