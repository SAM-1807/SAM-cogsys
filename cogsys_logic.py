"""cogsys_logic.py - pure-Python logic between the C engine, the UI and Gemini.

Nothing here imports ctypes or the Gemini SDK, so all of it can be tested
offline. Inputs are plain dicts: snapshots of the GameTelemetry struct taken
before and after each process_turn call.

Design (option B):
- Python ALWAYS decides the UI theme from engine data (never Gemini).
- Gemini only writes ai_message (each turn) and game_summary (game over).
- If Gemini fails or breaks a rule, a local rule-based reply is used.
"""
import json
import re

GOLD_THRESHOLD = 90         # proximity_score at or above this -> gold theme
EFFICIENT_VELOCITY = 40     # fallback wording only: "about half the range or more"
MAX_MESSAGE_CHARS = 160
MAX_SUMMARY_CHARS = 420
PHASES = {0: "playing", 1: "won", 2: "lost"}


class InvalidReply(ValueError):
    """The model's reply broke a rule, so the fallback must be used."""


# ------------------------------------------------------------------ numbers
def compute_proximity(distance, window_before):
    """0-100: how close a guess was, relative to the window the player knew.

    window_before is the count of numbers still possible BEFORE the guess.
    Rounded half-up (not Python's round(), which rounds halves to even).
    """
    span = max(window_before - 1, 1)
    score = 100 - (distance / span) * 100
    return max(0, min(100, int(score + 0.5)))


def choose_theme(game_status, logical_entropy, proximity_score):
    """Priority: game over > illegal guess > very close > default."""
    if game_status == 1:
        return "victory"
    if game_status == 2:
        return "defeat"
    if game_status != 0:
        raise ValueError(f"no theme for game_status {game_status}")
    if logical_entropy == 1:
        return "crimson"
    if proximity_score >= GOLD_THRESHOLD:
        return "gold"
    return "green"


def make_turn_record(before, after):
    """Build one history entry from struct snapshots taken around a turn."""
    window_before = before["current_max"] - before["current_min"] + 1
    proximity = compute_proximity(after["distance_vector"], window_before)
    return {
            "guess": after["last_guess"],
            "legal": after["logical_entropy"] == 0,
            "window_before": window_before,
            "velocity": after["space_velocity"],
            "proximity": proximity,
            "trials_remaining": after["trials_remaining"],
            "game_status": after["game_status"],
            "theme": choose_theme(after["game_status"], after["logical_entropy"], proximity),
            }


# ------------------------------------------------------------------ Gemini
SYSTEM_PROMPT = """\
        You are the analysis voice of SAM_CogSys, a number-guessing game that shows
players how efficiently they search. You describe search STRATEGY only. You do
not assess intelligence, personality or mental health.

You receive one JSON object describing the game so far. Every number in it was
computed by the game engine and is exact. Never recompute or contradict them.

Fields:
- range_max: the game picks a secret number from 1 to range_max.
- phase: "playing", "won" or "lost".
- theme_chosen_by_engine: the screen theme the engine already picked
  (crimson = illegal guess, gold = very close, green = normal, victory, defeat).
  Match your tone to it. Do not argue with it.
- history: one entry per guess, oldest first:
  - guess: the number the player guessed.
  - legal: false means the guess was outside the range the player had already
    narrowed down. It cost one trial and taught nothing.
  - window_before: how many numbers were still possible before this guess.
  - velocity: percent of window_before that this guess removed. About 50 means
    the player split the range in half (ideal). 0 appears only on illegal
    guesses. 100 appears only on the winning guess.
  - proximity: 0 to 100, how close the guess was to the secret compared with
    window_before. 100 is exact. 90 or more is very close.
  - trials_remaining: trials left after this guess.
- secret_number and player_name appear only when the game is over.

Output rules:
1. Reply with one JSON object and nothing else: no markdown, no code fences.
2. Keys, exactly: "ai_message" and "game_summary".
3. ai_message: 1 or 2 short sentences, at most 160 characters, about the LAST
   guess. While phase is "playing": clinical and neutral, no name, no
   exclamation marks. You may give a strategy hint such as "try the middle of
   your remaining range".
4. game_summary: null while phase is "playing". When phase is "won" or "lost":
   2 to 3 sentences, at most 420 characters, describing the WHOLE sequence: how
   consistently the player halved the range, how many guesses were illegal, and
   one concrete tip. You may state the secret number then.
5. Address the player as "you". Use player_name at most once, but only when phase is "won" or "lost". If player_name is null, do not use a name at all.
6. While playing, never state or hint at the secret number, and never use the
   name "SAM".
7. Describe only what the data shows. Do not guess why the player played that way.
"""


def build_payload(history, range_max, secret_number=None, player_name=None):
    """The JSON object sent to Gemini. The secret appears only after game over."""
    last = history[-1]
    payload = {
            "range_max": range_max,
            "phase": PHASES[last["game_status"]],
            "theme_chosen_by_engine": last["theme"],
            "history": [
                {key: rec[key] for key in
                 ("guess", "legal", "window_before", "velocity", "proximity",
                  "trials_remaining")}
                 for rec in history
                 ],
            }
    if last["game_status"] != 0:
        payload["secret_number"] = secret_number
        payload["player_name"] = player_name
    return payload


def _strip_fences(text):
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return (match.group(1) if match else text).strip()


def validate_reply(raw, secret_number, phase):
    """Return {"ai_message", "game_summary"} or raise InvalidReply."""
    if not isinstance(raw, str):
        raise InvalidReply("reply is not text")
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as err:
        raise InvalidReply(f"not valid JSON: {err}") from err
    if not isinstance(data, dict) or set(data) != {"ai_message", "game_summary"}:
        raise InvalidReply("wrong keys")

    message, summary = data["ai_message"], data["game_summary"]
    if (not isinstance(message, str) or not message.strip()
        or len(message) > MAX_MESSAGE_CHARS):
        raise InvalidReply("ai_message missing or too long")

    if phase == "playing":
        if summary is not None:
            raise InvalidReply("game_summary must be null while playing")
        if re.search(rf"(?<!\d){secret_number}(?!\d)", message):
            raise InvalidReply("message reveals the secret number")
        if re.search(r"\bsam\b", message, re.IGNORECASE):
            raise InvalidReply("name used while playing")
    elif (not isinstance(summary, str) or not summary.strip()
          or len(summary) > MAX_SUMMARY_CHARS):
        raise InvalidReply("game_summary missing or too long")

    return {"ai_message": message.strip(),
            "game_summary": summary.strip() if summary else None}


# ------------------------------------------------------------------ fallback
def fallback_reply(history, secret_number=None, player_name=None):
    """Local rule-based reply, used when Gemini fails or breaks a rule."""
    last = history[-1]
    theme = last["theme"]

    if theme == "crimson":
        message = "That guess was outside your remaining range and cost a trial."
    elif theme == "gold":
        message = "Very close to the target. Keep your next guess inside your range."
    elif theme == "green":
        if last["velocity"] >= EFFICIENT_VELOCITY:
            message = ("Efficient guess: it removed about half of your "
                       "remaining range or more.")
        else:
            message = "That guess removed little of your range. Try the middle next."
    else:
        return _fallback_game_over(history, theme, secret_number, player_name)
    return {"ai_message": message, "game_summary": None}


def _fallback_game_over(history, theme, secret_number, player_name):
    name = f", {player_name}" if player_name else ""
    if theme == "victory":
        message = f"Solved in {len(history)} guesses{name}."
    else:
        message = f"Out of trials{name}."

    illegal = sum(1 for rec in history if not rec["legal"])
    scored = [rec["velocity"] for rec in history
              if rec["legal"] and rec["game_status"] == 0]
    summary = f"{len(history)} guesses, {illegal} illegal."
    if scored:
        average = sum(scored) // len(scored)
        tip = ("Aim for the middle of your remaining range."
               if average < EFFICIENT_VELOCITY
               else "Your search stayed close to ideal halving.")
        summary += f" Your other legal guesses removed {average}% of the range on average. {tip}"
    if secret_number is not None:
        summary += f" The number was {secret_number}."
    return {"ai_message": message, "game_summary": summary}


def get_reply(history, range_max, secret_number, player_name, call_model):
    """Ask Gemini through call_model(system_prompt, payload_json) -> str.

    Any failure (exception, timeout, bad JSON, rule broken) falls back to the
    local reply. The result always has: ai_message, game_summary, theme, source.
    call_model owns the SDK call and its timeout, so tests can fake it.
    """
    last = history[-1]
    phase = PHASES[last["game_status"]]
    payload = build_payload(history, range_max, secret_number, player_name)
    try:
        raw = call_model(SYSTEM_PROMPT, json.dumps(payload))
        reply = validate_reply(raw, secret_number, phase)
        reply["source"] = "gemini"
    except Exception:  # deliberate: the demo must never crash on an API problem
        reply = fallback_reply(history, secret_number, player_name)
        reply["source"] = "fallback"
    reply["theme"] = last["theme"]
    return reply
