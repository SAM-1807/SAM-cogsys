"""try_gemini.py - send six realistic game states to the REAL model.

Run (needs GEMINI_API_KEY and network):
    python3 try_gemini.py

For each scenario it prints: which source answered ("gemini" or "fallback"),
how long it took, the theme, and the text. Read the messages as a player would.
What to look for:
  - Does "fallback" appear? If so, run again with DEBUG=1 to see why.
  - Is latency under about 3 seconds? (A slow reply makes the demo feel broken.)
  - Does the tone match the theme, and does a mid-game message avoid the secret?
"""
import os
import time

import cogsys_logic as cl
from gemini_client import make_call_model


def rec(guess, legal, window, velocity, proximity, trials, status, theme):
    return {"guess": guess, "legal": legal, "window_before": window,
            "velocity": velocity, "proximity": proximity,
            "trials_remaining": trials, "game_status": status, "theme": theme}


SCENARIOS = {
        "1 illegal guess": [
            rec(50, True, 100, 50, 49, 6, 0, "green"),
            rec(70, False, 49, 0, 0, 5, 0, "crimson"),
            ],
        "2 very close (gold)": [
            rec(50, True, 100, 50, 49, 6, 0, "green"),
            rec(26, True, 49, 49, 78, 5, 0, "green"),
            rec(37, True, 24, 50, 92, 4, 0, "gold"),
            ],
        "3 slow progress (green, low velocity)": [
            rec(99, True, 100, 1, 2, 6, 0, "green"),
            ],
        "4 efficient progress (green, ~50)": [
            rec(50, True, 100, 50, 49, 6, 0, "green"),
            rec(25, True, 49, 51, 80, 5, 0, "green"),
            ],
        "5 win": [
            rec(50, True, 100, 50, 49, 6, 0, "green"),
            rec(25, True, 49, 51, 80, 5, 0, "green"),
            rec(37, True, 24, 50, 92, 4, 0, "gold"),
            rec(31, True, 12, 50, 90, 3, 0, "gold"),
            rec(34, True, 6, 100, 100, 2, 1, "victory"),
            ],
        "6 loss with illegal guesses": [
            rec(50, True, 100, 50, 49, 6, 0, "green"),
            rec(60, False, 49, 0, 0, 5, 0, "crimson"),
            rec(60, False, 49, 0, 0, 4, 0, "crimson"),
            rec(10, True, 49, 20, 60, 3, 0, "green"),
            rec(11, True, 39, 2, 60, 2, 0, "green"),
            rec(12, True, 38, 2, 60, 0, 2, "defeat"),
            ],
        }
SECRET = 34


def main():
    call_model = make_call_model()
    for name, history in SCENARIOS.items():
        start = time.time()
        reply = cl.get_reply(history, 100, SECRET, "SAM", call_model)
        elapsed = time.time() - start
        print(f"== {name}: source={reply['source']} theme={reply['theme']} "
              f"time={elapsed:.1f}s")
        print("   message:", reply["ai_message"])
        if reply["game_summary"]:
            print("   summary:", reply["game_summary"])
        if reply["source"] == "fallback" and os.environ.get("DEBUG"):
            try:   # show the real reason the reply was rejected
                payload = cl.build_payload(history, 100, SECRET, "SAM")
                import json
                raw = call_model(cl.SYSTEM_PROMPT, json.dumps(payload))
                print("   RAW:", raw)
                cl.validate_reply(raw, SECRET, cl.PHASES[history[-1]["game_status"]])
            except Exception as err:   # noqa: BLE001 - diagnostic only
                print("   REASON:", type(err).__name__, err)


if __name__ == "__main__":
    main()
