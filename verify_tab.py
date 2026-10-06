"""Verify tab for the SolWorks dashboard.

Checks the private Discipline Log against roots anchored on Monad testnet.
Read-only against the real log; the tamper demo works on a throwaway copy.
"""
import streamlit as st
from verify import check, tamper_demo, CONTRACT, EXPLORER


def _n(k, word):
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def _short(h):
    return f"{h[:10]}…{h[-8:]}" if h else "—"


def _banner(ok, title, sub):
    color, bg = ("#2ecc71", "rgba(46,204,113,0.10)") if ok else ("#ff4d4f", "rgba(255,77,79,0.10)")
    st.markdown(f"""
<div style="border:1px solid {color};background:{bg};border-radius:10px;padding:22px 26px;margin:8px 0 18px;">
  <div style="color:{color};font-size:2rem;font-weight:700;letter-spacing:.04em;">{title}</div>
  <div style="opacity:.85;margin-top:4px;">{sub}</div>
</div>""", unsafe_allow_html=True)


def _show(result, tampered_id=None):
    n = sum(b["entries"] for b in result["batches"])
    if result["ok"]:
        _banner(True, "✓ VERIFIED",
                f"All {_n(n, 'anchored entry').replace('entrys', 'entries')} in {_n(len(result['batches']), 'batch').replace('batchs', 'batches')} match the Monad record.")
    else:
        edited = sorted({i for i, _ in result["problems"] if i is not None})
        what = f"Entry {', '.join(map(str, edited))} changed after it was anchored." if edited \
            else "A batch no longer matches its onchain root."
        _banner(False, "✗ TAMPERING DETECTED", what)

    if result["waiting"]:
        w = result["waiting"]
        st.caption("1 newer entry is not anchored yet. It will be in the next 9 PM run."
                   if w == 1 else
                   f"{w} newer entries are not anchored yet. They will be in the next 9 PM run.")

    for b in reversed(result["batches"]):
        icon = "🟢" if b["match"] else "🔴"
        when = b["onchain_at"].astimezone().strftime("%a %d %b %Y · %H:%M") if b["onchain_at"] else "no longer matches the onchain record"
        with st.expander(f"{icon}  Batch {b['batch_id']} · {b['entries']} {'entry' if b['entries'] == 1 else 'entries'} · {when}",
                         expanded=not b["match"]):
            c1, c2 = st.columns(2)
            c1.markdown("**Anchored root (onchain)**")
            c1.code(b["anchored_root"], language=None)
            c2.markdown("**Recomputed from your log now**")
            c2.code(b["recomputed_root"] or "cannot recompute (entry deleted)", language=None)
            for log_id, kind in b["bad_entries"]:
                st.error(f"Entry {log_id}: {kind}")
            if b["tx"]:
                st.markdown(f"[View transaction on Monad explorer ↗]({EXPLORER}/tx/{b['tx']})")


def render():
    st.markdown('<div class="sw-section" style="font-size:1.1rem;">Verify the Discipline Log</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<span class="sw-label">Every night at 9 PM, each new log entry is salted and hashed, and '
        'the batch root is written to Monad testnet. This recomputes those roots from the log as it '
        'is right now and asks the chain whether they match. The log itself never leaves this '
        f'machine. Contract: <a href="{EXPLORER}/address/{CONTRACT}" target="_blank">'
        f'{_short(CONTRACT)}</a></span>', unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2)
    if c1.button("Verify my log", type="primary", use_container_width=True):
        with st.spinner("Recomputing hashes and reading Monad…"):
            try:
                st.session_state["verify_result"] = ("real", None, check())
            except Exception as e:
                st.session_state["verify_result"] = ("error", None, str(e))
    if c2.button("Tamper demo (edits a throwaway copy)", use_container_width=True):
        with st.spinner("Editing one entry in a temp copy and verifying it…"):
            try:
                tid, res = tamper_demo()
                st.session_state["verify_result"] = ("tamper", tid, res)
            except Exception as e:
                st.session_state["verify_result"] = ("error", None, str(e))

    kind, tid, res = st.session_state.get("verify_result", (None, None, None))
    if kind is None:
        st.caption("Nothing checked yet this session.")
    elif kind == "error":
        st.warning(f"Could not complete the check: {res}")
    else:
        if kind == "tamper":
            st.info(f"Demo: entry {tid} was quietly edited in a temporary copy. "
                    "Your real log was not touched, and the copy has been deleted.")
        _show(res, tid)
        st.caption(f"Checked {res['checked_at'].astimezone():%a %d %b %Y · %H:%M:%S}")
