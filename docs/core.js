// Verification logic for the SolWorks Anchor public verifier.
// Talks to Monad testnet directly over JSON-RPC. No server, no wallet.

export const RPC_URL = "https://testnet-rpc.monad.xyz";
export const CHAIN_ID = 10143;
export const CONTRACT = "0xbbd400e757Dd6E6c6666A5036eA13e629Df7AE06";
export const EXPLORER = "https://testnet.monadexplorer.com";

const SEL_ANCHORED_AT = "0x9591a610";   // anchoredAt(bytes32)
const SEL_ANCHOR_COUNT = "0x34f96c8c";  // anchorCount()
const SEL_OWNER = "0x8da5cb5b";         // owner()
const TOPIC_ANCHORED =                  // Anchored(uint256,bytes32,uint256,uint256)
  "0x4be48ba87b7b62bb34ea6cd6df6629196f9008660355ad313b3fe961fa5fc6bd";

let rpcId = 0;
async function rpc(method, params) {
  const res = await fetch(RPC_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: ++rpcId, method, params }),
  });
  const body = await res.json();
  if (body.error) throw new Error(`${method}: ${body.error.message}`);
  return body.result;
}

const call = (data) => rpc("eth_call", [{ to: CONTRACT, data }, "latest"]);
const word = (hex, i) => BigInt("0x" + hex.replace(/^0x/, "").slice(i * 64, i * 64 + 64));

export function hexToBytes(hex) {
  const h = hex.replace(/^0x/, "");
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.substr(i * 2, 2), 16);
  return out;
}

export function bytesToHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(bytes) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

// Must match fingerprint.py: sha256(salt + "|" + compact JSON of the row).
export function canonical(values) {
  return JSON.stringify(values);
}

export async function leafHash(salt, values) {
  const text = salt + "|" + canonical(values);
  return bytesToHex(await sha256(new TextEncoder().encode(text)));
}

// Must match anchor.py: sha256 of the leaves' raw bytes, concatenated in order.
export async function rootOf(leaves) {
  const all = new Uint8Array(leaves.length * 32);
  leaves.forEach((leaf, i) => all.set(hexToBytes(leaf), i * 32));
  return "0x" + bytesToHex(await sha256(all));
}

export async function anchoredAt(root) {
  const data = SEL_ANCHORED_AT + root.replace(/^0x/, "").padStart(64, "0");
  return Number(word(await call(data), 0));
}

export async function contractInfo() {
  const [count, owner, chain] = await Promise.all([
    call(SEL_ANCHOR_COUNT),
    call(SEL_OWNER),
    rpc("eth_chainId", []),
  ]);
  return {
    anchorCount: Number(word(count, 0)),
    owner: "0x" + owner.slice(-40),
    chainId: Number(chain),
  };
}

// Check one published batch against the chain, trusting nothing in ledger.json
// except the transaction hash it points to.
export async function checkBatch(batch, owner) {
  const problems = [];
  const receipt = await rpc("eth_getTransactionReceipt", [batch.tx]);
  if (!receipt) return { ...batch, ok: false, problems: ["Transaction not found on Monad"] };

  if (receipt.status !== "0x1") problems.push("Transaction failed");
  if (receipt.to?.toLowerCase() !== CONTRACT.toLowerCase()) problems.push("Sent to a different contract");
  if (receipt.from?.toLowerCase() !== owner.toLowerCase()) problems.push("Not sent by the contract owner");

  const log = receipt.logs.find(
    (l) => l.address.toLowerCase() === CONTRACT.toLowerCase() && l.topics[0] === TOPIC_ANCHORED);
  if (!log) return { ...batch, ok: false, problems: [...problems, "No Anchored event in this transaction"] };

  const anchorId = Number(BigInt(log.topics[1]));
  const root = "0x" + log.topics[2].slice(-64);
  const entryCount = Number(word(log.data, 0));
  const timestamp = Number(word(log.data, 1));

  if (root.toLowerCase() !== batch.root.toLowerCase()) problems.push("Root onchain differs from the published root");
  if (entryCount !== batch.entries) problems.push("Entry count onchain differs from the published count");

  const storedAt = await anchoredAt(root);
  if (storedAt !== timestamp) problems.push("Contract storage disagrees with the event");

  return {
    ...batch, anchorId, root, entryCount, timestamp,
    block: Number(receipt.blockNumber), ok: problems.length === 0, problems,
  };
}

// Walk a single-entry proof through every step, reporting each one.
// `values` may be edited by the viewer; the proof's own values are the original.
export async function verifyProof(proof, values) {
  const steps = [];
  const leaf = await leafHash(proof.salt, values);
  const expected = proof.leaves[proof.position];
  steps.push({
    label: "Fingerprint the entry",
    detail: `sha256(salt | entry) = ${leaf}`,
    ok: leaf === expected,
    fail: `Does not match fingerprint #${proof.position + 1} in the batch (${expected.slice(0, 16)}…). The entry has been changed.`,
  });

  const root = await rootOf(proof.leaves);
  steps.push({
    label: "Rebuild the batch root",
    detail: `${proof.leaves.length} fingerprints → ${root}`,
    ok: root.toLowerCase() === proof.root.toLowerCase(),
    fail: "The batch fingerprints don't produce the root in this proof.",
  });

  const at = await anchoredAt(root);
  steps.push({
    label: "Ask Monad when that root was anchored",
    detail: at ? `anchoredAt(root) = ${at} (${new Date(at * 1000).toUTCString()})` : "anchoredAt(root) = 0",
    ok: at > 0,
    fail: "This root was never anchored on the contract.",
    timestamp: at,
  });

  return { ok: steps.every((s) => s.ok), steps, timestamp: at };
}
