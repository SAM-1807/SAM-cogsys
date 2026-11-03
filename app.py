"""app.py - SAM_CogSys: functional game loop.

Run locally:   streamlit run app.py
Not in this version (planned): Naija persona, custom CSS themes, typewriter animation.
Messages come from the local rule-based engine; Gemini is an optional switch (off by default).
"""
import ctypes
import os
import subprocess

import streamlit as st

st.set_page_config(page_title="SAM_CogSys", page_icon="🧠")

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "libgame.so")
SOURCE = os.path.join(HERE, "game.c")

def build_library():
    """Try to compile libgame.so. Return an error text, or None on success."""
    try:
        build = subprocess.run(["gcc", "-shared", "-fPIC", "-o", LIB, SOURCE],
                               capture_output=True, text=True)
    except OSError as err:                    # gcc is not installed on this host
        return f"gcc not available: {err}"
    return None if build.returncode == 0 else build.stderr


# Rebuild when the library is missing or older than game.c. If the rebuild fails
# (no compiler, compile error) but a prebuilt libgame.so exists, keep using it.
lib_existed = os.path.exists(LIB)
if not lib_existed or os.path.getmtime(LIB) < os.path.getmtime(SOURCE):
    build_error = build_library()
    if build_error and not lib_existed:
        st.error("Could not compile libgame.so and no prebuilt copy exists.")
        st.code(build_error)
        st.stop()

# On a host, copy the Gemini key from the platform's secrets into the environment.
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ.setdefault("GEMINI_API_KEY", st.secrets["GEMINI_API_KEY"])
except Exception:      # no secrets configured (normal when running locally)
    pass

from bridge import GameTelemetry, lib, new_game  # noqa: E402  (after the build)
import cogsys_logic as cl  # noqa: E402

LEVELS = {"Easy": 1, "Medium": 2, "Hard": 3}


# ---------------------------------------------------------------- helpers
def snap(game):
    return {name: getattr(game, name) for name, _ in GameTelemetry._fields_}


def start_new_game():
    st.session_state.game = new_game(LEVELS[st.session_state.level])
    st.session_state.history = []
    st.session_state.rows = []
    st.session_state.reply = None


@st.cache_resource
def load_gemini():
    from gemini_client import make_call_model
    return make_call_model()


def gemini_off(system_prompt, payload_json):
    raise RuntimeError("Gemini is switched off")     # get_reply turns this into the fallback


def pick_call_model():
    if st.session_state.get("use_gemini"):
        try:
            return load_gemini()
        except Exception as err:                      # SDK or key missing
            st.sidebar.warning(f"Gemini unavailable ({type(err).__name__}). Using local messages.")
    return gemini_off


def result_text(guess, game, record):
    if not record["legal"]:
        return "Outside your range"
    if guess == game.secret_number:
        return "Correct"
    return "Too low" if guess < game.secret_number else "Too high"


def play(guess):
    game = st.session_state.game
    before = snap(game)
    lib.process_turn(guess, ctypes.byref(game))
    record = cl.make_turn_record(before, snap(game))
    st.session_state.history.append(record)
    st.session_state.rows.append({"#": len(st.session_state.history),
                                  "Guess": guess,
                                  "Result": result_text(guess, game, record)})
    name = (st.session_state.get("player_name") or "").strip() or None
    st.session_state.reply = cl.get_reply(st.session_state.history, game.range_max,
                                          game.secret_number, name, pick_call_model())


def show_reply(reply):
    """Plain Streamlit boxes for now; custom CSS themes replace this later."""
    box = {"crimson": st.error, "gold": st.warning, "green": st.success,
           "victory": st.success, "defeat": st.info}[reply["theme"]]
    box(reply["ai_message"])
    st.caption(f"theme: {reply['theme']} | source: {reply['source']}")
    if reply["game_summary"]:
        st.markdown(reply["game_summary"])


def optimal_path(level, secret):
    """Guesses a perfect midpoint search would make for this secret.

    Uses the real engine with a throwaway game, so the bot plays by the same rules.
    """
    bot = new_game(level)
    bot.secret_number = secret
    guesses = []
    while bot.game_status == 0 and len(guesses) < 50:
        guess = (bot.current_min + bot.current_max) // 2
        lib.process_turn(guess, ctypes.byref(bot))
        guesses.append(guess)
    return guesses if bot.game_status == 1 else None


def plural(count, word="turn"):
    return f"{count} {word}" + ("" if count == 1 else "s")


def show_ghost_bot(game, history, level):
    """Compare the player's path with a perfect midpoint search for the same secret."""
    optimal = optimal_path(level, game.secret_number)
    if optimal is None:
        return
    mine = len(history)
    wasted = sum(1 for record in history if not record["legal"])

    st.subheader("Optimal path vs your path")
    left, right = st.columns(2)
    left.metric("Optimal Path", plural(len(optimal)))
    right.metric("Your Path", plural(mine))
    st.caption("Optimal = a perfect halving search that does not know the number in advance.")

    if game.game_status == 1:
        gap = mine - len(optimal)
        if gap < 0:
            st.success("You found it faster than a perfect search would. Excellent.")
        elif gap == 0:
            st.success("You matched the optimal path.")
        else:
            st.info(f"You were {plural(gap)} over the optimal path.")
    else:
        numbers_left = game.current_max - game.current_min + 1
        message = (f"You ran out of trials after {plural(mine)}. A perfect search finds "
                   f"this number in {plural(len(optimal))}. When your trials ended, "
                   f"{numbers_left} numbers were still possible.")
        if mine > len(optimal):
            message += f" That is {plural(mine - len(optimal))} more than the optimal path."
        st.info(message)

    st.caption(f"Efficient turns (inside your range): {mine - wasted} | "
               f"Wasted turns (outside your range): {wasted}")

    with st.expander("See the optimal path"):
        rows = []
        for index in range(max(len(optimal), mine)):
            bot_guess = str(optimal[index]) if index < len(optimal) else "-"
            if index < mine:
                record = history[index]
                yours = str(record["guess"]) + ("" if record["legal"] else " (wasted)")
            else:
                yours = "-"
            rows.append({"Turn": index + 1, "Optimal bot": bot_guess, "You": yours})
        st.dataframe(rows, hide_index=True)


# ---------------------------------------------------------------- state
if "level" not in st.session_state:
    st.session_state.level = "Easy"
if "game" not in st.session_state:
    start_new_game()

with st.sidebar:
    st.header("Game")
    st.selectbox("Difficulty", list(LEVELS), key="level", on_change=start_new_game)
    st.text_input("Your name (optional)", key="player_name")
    st.checkbox("Show possible range", key="show_range")
    st.checkbox("Use Gemini for messages", key="use_gemini")
    st.button("New game", on_click=start_new_game)

game = st.session_state.game
history = st.session_state.history

# ---------------------------------------------------------------- page
st.title("SAM_CogSys")
st.caption("Guess the number. The engine measures how you search.")

if game.game_status == -1:                  # cannot happen from the selector; kept as a guard
    st.error("The engine reported an invalid difficulty.")
    st.stop()

if game.game_status == 0:
    with st.form("guess_form", clear_on_submit=True):
        guess = st.number_input(f"Your guess (1 to {game.range_max})", min_value=1,
                                max_value=game.range_max, value=None, step=1,
                                placeholder="Type a number")
        submitted = st.form_submit_button("Guess")
    if submitted:
        if guess is None:
            st.warning("Type a number first.")
        else:
            play(int(guess))
            st.rerun()                      # redraw so a finished game hides the form

if st.session_state.reply:
    show_reply(st.session_state.reply)

if game.game_status in (1, 2):
    st.write(f"The number was **{game.secret_number}**.")
    show_ghost_bot(game, history, LEVELS[st.session_state.level])
    st.write("Press **New game** in the sidebar to play again.")

left, middle, right = st.columns(3)
left.metric("Trials left", game.trials_remaining)
middle.metric("Guesses made", len(history))
if st.session_state.get("show_range") and game.game_status == 0:
    right.metric("Possible range", f"{game.current_min} to {game.current_max}")

if st.session_state.rows:
    st.subheader("Your guesses")
    st.dataframe(st.session_state.rows, hide_index=True)

with st.expander("Engine telemetry"):
    data = snap(game)
    if game.game_status == 0:
        data.pop("secret_number")           # never show the secret while playing
    st.json({"engine_struct": data, "last_turn": history[-1] if history else None})
