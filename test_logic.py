"""test_logic.py - tests for cogsys_logic.py (no Gemini calls, no network).

Run from the project folder, after building libgame.so:
    python3 test_logic.py

Predict which checks might fail before you run it.
"""
import ctypes
import json
import sys

import cogsys_logic as cl
from bridge import GameTelemetry, lib, new_game

results = []


def check(name, cond, info=""):
    results.append(bool(cond))
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else "   -> " + str(info)))


def snap(t):
    return {f: getattr(t, f) for f, _ in GameTelemetry._fields_}


def midpoint(t):
    return (t.current_min + t.current_max) // 2


def play_game(difficulty, secret, strategy, max_turns=30):
    """Play with the real C engine. Returns (struct, history of turn records)."""
    t = new_game(difficulty)
    t.secret_number = secret
    history = []
    for _ in range(max_turns):
        if t.game_status != 0:
            break
        before = snap(t)
        lib.process_turn(strategy(t), ctypes.byref(t))
        history.append(cl.make_turn_record(before, snap(t)))
    return t, history


def rec(theme, velocity=50, legal=True, status=0):
    """A hand-made history entry for fallback and payload tests."""
    return {"guess": 10, "legal": legal, "window_before": 50, "velocity": velocity,
            "proximity": 95 if theme == "gold" else 40, "trials_remaining": 3,
            "game_status": status, "theme": theme}


# ------------------------------------------------------------ A: proximity
check("A proximity exact guess is 100", cl.compute_proximity(0, 100) == 100)
check("A proximity distance 10 in window 100 rounds to 90", cl.compute_proximity(10, 100) == 90)
check("A proximity distance 11 in window 100 is 89", cl.compute_proximity(11, 100) == 89)
check("A proximity is clamped at 0", cl.compute_proximity(10 ** 6, 100) == 0)
check("A proximity window of 1 does not divide by zero", cl.compute_proximity(0, 1) == 100)
check("A same distance, smaller window means lower proximity (window-relative)",
      cl.compute_proximity(5, 100) == 95 and cl.compute_proximity(5, 10) == 44,
      (cl.compute_proximity(5, 100), cl.compute_proximity(5, 10)))

# ------------------------------------------------------------ B: theme priority
cases = [
        (0, 0, 95, "gold"), (0, 0, 90, "gold"), (0, 0, 89, "green"),
        (0, 1, 99, "crimson"), (0, 1, 0, "crimson"),
        (1, 0, 100, "victory"), (2, 1, 10, "defeat"), (1, 1, 0, "victory"),
        ]
for status, entropy, prox, expected in cases:
    got = cl.choose_theme(status, entropy, prox)
    check(f"B theme(status={status}, entropy={entropy}, prox={prox}) == {expected}",
          got == expected, got)
try:
    cl.choose_theme(-1, 0, 0)
    check("B error state has no theme (raises)", False, "no exception")
except ValueError:
    check("B error state has no theme (raises)", True)

# ------------------------------------------------------------ C: records from the real engine
t, hist = play_game(1, 50, lambda t: 50)
check("C first-guess win: one record, victory, velocity 100",
      len(hist) == 1 and hist[0]["theme"] == "victory" and hist[0]["velocity"] == 100, hist)

t, hist = play_game(1, 50, lambda t: 100, max_turns=2)      # legal, then illegal repeat
check("C legal wrong guess then illegal repeat: green/gold then crimson",
      hist[0]["legal"] and not hist[1]["legal"] and hist[1]["theme"] == "crimson", hist)
check("C illegal guess keeps window_before from before the turn",
      hist[1]["window_before"] == 99, hist[1])

# ------------------------------------------------------------ D: Gold no longer saturates
share_late = []
for secret in range(1, 101):
    t, hist = play_game(1, secret, midpoint)
    for turn_no, record in enumerate(hist, start=1):
        if record["game_status"] == 0 and turn_no >= 4:
            share_late.append(record["theme"] == "gold")
gold_share = sum(share_late) / max(len(share_late), 1)
print(f"      (info) perfect binary search, Easy, turn 4+: gold on {gold_share:.0%} of turns")
check("D gold is NOT on every late turn of perfect play (was 100% with full-range proximity)",
      share_late and gold_share < 0.6, gold_share)

# ------------------------------------------------------------ E: payload
history = [rec("green"), rec("gold")]
payload = cl.build_payload(history, 100, secret_number=42, player_name="SAM")
check("E payload while playing has no secret and no name",
      "secret_number" not in payload and "player_name" not in payload
      and "42" not in json.dumps(payload) and "SAM" not in json.dumps(payload), payload)
check("E payload phase and engine theme are included",
      payload["phase"] == "playing" and payload["theme_chosen_by_engine"] == "gold", payload)
payload = cl.build_payload([rec("green"), rec("victory", 100, True, 1)], 100, 42, "SAM")
check("E payload after game over includes secret and name",
      payload["secret_number"] == 42 and payload["player_name"] == "SAM", payload)
check("E history entries expose exactly the documented fields",
      set(payload["history"][0]) == {"guess", "legal", "window_before", "velocity",
                                     "proximity", "trials_remaining"}, payload["history"][0])

# ------------------------------------------------------------ F: validator
GOOD = json.dumps({"ai_message": "Try the middle of your remaining range.", "game_summary": None})
END = json.dumps({"ai_message": "Solved.", "game_summary": "You halved the range well."})


def rejects(raw, secret, phase):
    try:
        cl.validate_reply(raw, secret, phase)
        return False
    except cl.InvalidReply:
        return True


check("F valid playing reply accepted",
      cl.validate_reply(GOOD, 42, "playing")["game_summary"] is None)
check("F reply wrapped in code fences accepted",
      cl.validate_reply("```json\n" + GOOD + "\n```", 42, "playing")["ai_message"].startswith("Try"))
check("F valid game-over reply accepted", cl.validate_reply(END, 42, "won")["game_summary"] is not None)
check("F invalid JSON rejected", rejects("not json at all", 42, "playing"))
check("F non-text reply rejected", rejects(None, 42, "playing"))
check("F extra key rejected", rejects(json.dumps({"ai_message": "x", "game_summary": None, "theme": "red"}), 42, "playing"))
check("F missing key rejected", rejects(json.dumps({"ai_message": "x"}), 42, "playing"))
check("F summary while playing rejected", rejects(json.dumps({"ai_message": "x", "game_summary": "y"}), 42, "playing"))
check("F missing summary at game over rejected", rejects(json.dumps({"ai_message": "x", "game_summary": None}), 42, "lost"))
check("F too-long message rejected", rejects(json.dumps({"ai_message": "x" * 161, "game_summary": None}), 42, "playing"))
check("F leaking the secret rejected", rejects(json.dumps({"ai_message": "Try 42 next.", "game_summary": None}), 42, "playing"))
check("F a different number containing the same digits is allowed",
      not rejects(json.dumps({"ai_message": "Your window has 142 numbers left.", "game_summary": None}), 42, "playing"))
check("F name used while playing rejected", rejects(json.dumps({"ai_message": "Nice try, Sam.", "game_summary": None}), 42, "playing"))
check("F name allowed at game over",
      not rejects(json.dumps({"ai_message": "Well played, SAM.", "game_summary": "Good halving."}), 42, "won"))

# ------------------------------------------------------------ G: get_reply and fallback
def good_model(system, payload_json):
    return GOOD


def timeout_model(system, payload_json):
    raise TimeoutError("simulated")


def api_down_model(system, payload_json):
    raise RuntimeError("503 Service Unavailable")


def garbage_model(system, payload_json):
    return "<html>oops</html>"


def leaking_model(system, payload_json):
    return json.dumps({"ai_message": "The number is 42.", "game_summary": None})


hist = [rec("green")]
r = cl.get_reply(hist, 100, 42, "SAM", good_model)
check("G good reply: source gemini, theme from the engine",
      r["source"] == "gemini" and r["theme"] == "green", r)
for name, model in (("timeout", timeout_model), ("503", api_down_model),
                    ("garbage", garbage_model), ("secret leak", leaking_model)):
    r = cl.get_reply(hist, 100, 42, "SAM", model)
    check(f"G {name}: falls back, theme still from the engine",
          r["source"] == "fallback" and r["theme"] == "green" and r["ai_message"], r)

# every fallback reply must satisfy the same rules we demand of Gemini
for theme, velocity in (("crimson", 0), ("gold", 50), ("green", 60), ("green", 10)):
    h = [rec(theme, velocity, legal=(theme != "crimson"))]
    reply = cl.fallback_reply(h, secret_number=42, player_name="SAM")
    ok = True
    try:
        cl.validate_reply(json.dumps(reply), 42, "playing")
    except cl.InvalidReply as err:
        ok = str(err)
    check(f"G fallback ({theme}, velocity {velocity}) passes the validator", ok is True, ok)

t, win_hist = play_game(1, 50, midpoint)
reply = cl.fallback_reply(win_hist, 50, "SAM")
check("G fallback win: ai_message and summary present, secret and name included",
      reply["game_summary"] and "50" in reply["game_summary"] and "SAM" in reply["ai_message"], reply)
try:
    cl.validate_reply(json.dumps(reply), 50, "won")
    check("G fallback win passes the validator", True)
except cl.InvalidReply as err:
    check("G fallback win passes the validator", False, err)

t, lose_hist = play_game(1, 50, lambda t: 1)
reply = cl.fallback_reply(lose_hist, 50, "SAM")
check("G fallback loss: counts illegal guesses and reveals the number",
      lose_hist[-1]["theme"] == "defeat" and "illegal" in reply["game_summary"]
      and "50" in reply["game_summary"], (lose_hist[-1]["theme"], reply))
r = cl.get_reply(win_hist, 100, 50, "SAM", api_down_model)
check("G game over with API down still returns a summary", r["game_summary"] and r["theme"] == "victory", r)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
