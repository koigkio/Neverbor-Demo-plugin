#!/usr/bin/env python3
"""neverbor — Stop hook: after a reply that saved tokens, tell the user how many (systemMessage).

Nothing is added to the model's context. Small savings stay silent to avoid noise.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state  # noqa: E402

MIN_TOKENS = 300

MESSAGES = {
    "en": "neverbor: ≈%s tokens saved in this reply, ≈%s this session",
    "ru": "neverbor: сэкономлено ≈%s токенов в этом ответе, ≈%s за сессию",
}


def fmt(n):
    return "{:,}".format(n).replace(",", " ")


def main():
    if not state.enabled():
        return
    data = state.read_hook_input()
    session_id = data.get("session_id") or ""
    if not session_id:
        return
    total = sum(state.saved_tokens(r) for r in state.read_ledger() if r.get("session") == session_id)
    session = state.load_session(session_id)
    fresh = total - session.get("reported", 0)
    if fresh < MIN_TOKENS:
        return
    session["reported"] = total
    state.save_session(session_id, session)
    lang = state.load_config()["lang"]
    state.write_hook_output({"systemMessage": MESSAGES.get(lang, MESSAGES["en"]) % (fmt(fresh), fmt(total))})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
