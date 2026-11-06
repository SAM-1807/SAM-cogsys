"""app.py - SAM_CogSys: game loop with a rules gate and full-page themes.

Run locally:   streamlit run app.py
Flow: rules screen (difficulty, name, Start Game) -> game -> end screen (Play Again).
The page look follows the Python theme (crimson, green, gold, victory, defeat), and
every theme also shows a text label, so colour is never the only signal.
Not in this version (planned): Naija persona, Pressure Mode timer.
Messages come from the local rule-based engine; Gemini is an optional sidebar switch.
"""
import ctypes
import html
import json
import math
import os
import subprocess
import time

import streamlit as st

st.set_page_config(page_title="SAM_CogSys", page_icon="🧠")

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "libgame.so")
SOURCE = os.path.join(HERE, "game.c")
SOUND_DIR = os.path.join(HERE, "sounds")
SOUND_FILES = {"music": "play.mp3", "victory": "victory.mp3", "defeat": "start.mp3"}



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
PRESSURE_LIMITS = {"Easy": 20, "Medium": 15, "Hard": 10}     # seconds per turn

# Session state used by this app. Two kinds, on purpose:
#   settings (plain keys, always present):  has_started, level, player_name, show_range
#   widget keys (only exist while their widget is on screen): level_choice,
#   name_choice, range_choice (rules screen), use_gemini (sidebar)
# Streamlit deletes a widget's state when the widget is not drawn, so the game
# page only ever reads the plain settings, which begin_game() copies from the widgets.
for _key, _default in (("has_started", False), ("level", "Easy"),
                       ("player_name", ""), ("show_range", False)):
    st.session_state.setdefault(_key, _default)



# ---------------------------------------------------------------- themes
# label and hint: the text that always accompanies a theme (colour is never the only signal)
# page: the full-page background for that theme. Banner colours live in the CSS below.
THEMES = {
        "neutral": {"label": "READY", "hint": "Make your first guess",
                    "page": "linear-gradient(160deg, #14181F, #0B0E13)"},
        "crimson": {"label": "⚠ WAHALA", "hint": "Outside your range",
                    "page": ("repeating-linear-gradient(45deg, rgba(255,60,60,0.05) 0 14px, "
                             "transparent 14px 28px), linear-gradient(160deg, #3B0A0A, #1F0505)")},
                    "green": {"label": "✔ SHARP GUY", "hint": "Inside your range",
                              "page": ("repeating-linear-gradient(0deg, rgba(57,217,138,0.18) 0 1px, "
                                       "transparent 1px 26px), repeating-linear-gradient(90deg, "
                                       "rgba(57,217,138,0.18) 0 1px, transparent 1px 26px), "
                                       "linear-gradient(160deg, #052B1C, #03140D)")},
                              "gold": {"label": "★ E DON NEAR", "hint": "Very close",
                                       "page": ("radial-gradient(circle at 50% 0%, rgba(255,215,0,0.18), transparent 55%), "
                                                "linear-gradient(160deg, #3A3000, #1D1800)")},
                                       "victory": {"label": "🏆 VICTORY", "hint": "You found the number",
                                                   "page": ("radial-gradient(circle at 50% 0%, rgba(255,215,0,0.25), transparent 60%), "
                                                            "linear-gradient(160deg, #052B1C, #3A3000)")},
                                                   "defeat": {"label": "■ DEFEAT", "hint": "Trials finished",
                                                              "page": "linear-gradient(160deg, #262626, #131313)"},
                                                   }

MAIN_AREAS = ['[data-testid="stMain"]', "section.main"]     # the page area, not the sidebar


def scoped(*inner):
    """CSS selectors for elements inside the main page area only."""
    return ",\n".join(f"{area} {selector}" for area in MAIN_AREAS for selector in inner)


def build_css(theme):
    text = scoped('[data-testid="stMarkdownContainer"] *', '[data-testid="stHeading"] *',
                  '[data-testid="stWidgetLabel"] *', '[data-testid="stMetricLabel"] *',
                  '[data-testid="stMetricValue"] *', '[data-testid="stExpander"] summary *')
    restore = scoped('button [data-testid="stMarkdownContainer"] *',
                     '[data-testid^="stAlert"] [data-testid="stMarkdownContainer"] *')
    muted = scoped('[data-testid="stCaptionContainer"] *')
    banner = scoped('[data-testid="stMarkdownContainer"] .cog-banner',
                    '[data-testid="stMarkdownContainer"] .cog-banner *')
    footer = scoped('[data-testid="stMarkdownContainer"] .cog-footer')
    css = """<style>
.stApp {
  background: #0B0E13;
  isolation: isolate;
}
.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background: __PAGE__;
}
[data-testid="stAppViewContainer"] {
  background: transparent !important;
}
[data-testid="stHeader"], [data-testid="stMain"], section.main {
  background: transparent !important;
}
__TEXT__ { color: #F5F5F5 !important; }
__RESTORE__ { color: inherit !important; }
__MUTED__ { color: #BDBDBD !important; }
.cog-banner {
  border-radius: 14px; padding: 1rem 1.25rem; margin: 0.25rem 0 1rem 0;
  border: 3px solid var(--border); background: var(--bg);
  box-shadow: 0 0 22px var(--glow);
}
.cog-label { font-weight: 800; letter-spacing: 0.08em; font-size: 1.05rem; }
.cog-hint { font-weight: 600; font-size: 0.9rem; letter-spacing: 0; }
.cog-text { font-size: 1.15rem; margin-top: 0.35rem; }
.cog-neutral { --bg: #1F2937; --fg: #F5F5F5; --border: #4B5563; --glow: rgba(0,0,0,0); }
.cog-crimson { --bg: #B22222; --fg: #FFFFFF; --border: #FF8A8A; --glow: rgba(255,70,70,0.55);
  animation: cog-shake 0.45s ease-in-out 1, cog-pulse 1.8s ease-in-out infinite; }
.cog-green { --bg: #008751; --fg: #FFFFFF; --border: #39D98A; --glow: rgba(57,217,138,0.45); }
.cog-gold { --bg: #FFD700; --fg: #1A1A1A; --border: #FFF3A0; --glow: rgba(255,215,0,0.6);
  animation: cog-glow 2s ease-in-out infinite; }
.cog-victory { --bg: #008751; --fg: #FFFFFF; --border: #FFD700; --glow: rgba(255,215,0,0.65);
  border-width: 4px; }
.cog-defeat { --bg: #333333; --fg: #F2F2F2; --border: #8A8A8A; --glow: rgba(0,0,0,0); }
__BANNER__ { color: var(--fg) !important; }
__FOOTER__ { color: #BDBDBD !important; text-align: center; font-size: 0.8rem;
  padding-top: 2rem; }
@keyframes cog-shake { 0%, 100% { transform: translateX(0); } 20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); } 60% { transform: translateX(-5px); }
  80% { transform: translateX(5px); } }
@keyframes cog-pulse { 0%, 100% { box-shadow: 0 0 12px rgba(255,70,70,0.35); }
  50% { box-shadow: 0 0 30px 6px rgba(255,70,70,0.75); } }
@keyframes cog-glow { 0%, 100% { box-shadow: 0 0 14px rgba(255,215,0,0.35); }
  50% { box-shadow: 0 0 34px 8px rgba(255,215,0,0.75); } }
@media (prefers-reduced-motion: reduce) { .cog-banner { animation: none !important; } }
[data-testid="stForm"] button {
  background: #4B5563 !important; color: #FFFFFF !important; border: 1px solid #6B7280 !important;
}
[data-testid="stForm"]:has(input:not(:placeholder-shown):valid) button {
  background: #1E6FE8 !important; border-color: #6FA8FF !important;
}
</style>"""
    for marker, value in (("__PAGE__", THEMES[theme]["page"]), ("__TEXT__", text),
                          ("__RESTORE__", restore), ("__MUTED__", muted),
                          ("__BANNER__", banner), ("__FOOTER__", footer)):
        css = css.replace(marker, value)
    return css


def current_theme():
    """Theme for the whole page: neutral on the rules screen and before the first guess."""
    if not st.session_state.has_started:
        return "neutral"
    reply = st.session_state.get("reply")
    return reply["theme"] if reply else "neutral"


def show_banner(theme, message, hint=None):
    """The themed message box. Its label is text, so colour is never the only signal."""
    spec = THEMES[theme]
    st.markdown(
            f"<div class='cog-banner cog-{theme}' role='status' aria-live='polite'>"
            f"<div class='cog-label'>{spec['label']} <span class='cog-hint'>· {html.escape(hint or spec['hint'])}</span></div>"
            f"<div class='cog-text'>{html.escape(message)}</div></div>",
            unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def snap(game):
    return {name: getattr(game, name) for name, _ in GameTelemetry._fields_}


def start_new_game():
    st.session_state.game = new_game(LEVELS[st.session_state.level])
    st.session_state.history = []
    st.session_state.rows = []
    st.session_state.reply = None
    st.session_state.deadline = None

def begin_game():
    """Start Game button: copy the rules-screen choices, build a game, open the game page."""
    state = st.session_state
    state.level = state.get("level_choice", state.level)
    state.player_name = (state.get("name_choice", state.player_name) or "").strip()
    state.show_range = bool(state.get("range_choice", state.show_range))
    start_new_game()
    state.has_started = True


def back_to_rules():
    """New game / Play Again: return to the rules screen (the previous choices are kept)."""
    st.session_state.has_started = False


@st.cache_data
def level_info():
    """Range and trials per level, read from the engine so the rules never drift from it."""
    info = {}
    for name, level in LEVELS.items():
        probe = new_game(level)
        info[name] = (probe.range_max, probe.trials_remaining)
    return info


def show_footer():
    st.markdown("<div class='cog-footer'>Developed by SAM</div>", unsafe_allow_html=True)


def show_rules():
    st.title("SAM_CogSys")
    st.caption("Guess the number. The engine measures how efficiently you search.")
    with st.container(border=True):
        st.subheader("How to play")
        st.markdown(
                "1. The game picks a secret number. Find it before your trials run out.\n"
                "2. Every guess costs one trial. After each guess you see \"Too low\" "
                "or \"Too high\".\n"
                "3. **Penalty:** a guess outside the range you have already narrowed "
                "down is wasted. It costs a trial and teaches you nothing.\n"
                "4. After each guess, a message reacts to how well you searched.\n"
                "5. At the end, your path is compared with a perfect halving search "
                "for the same number.")
        st.markdown("\n".join(
            f"- **{name}:** numbers 1 to {top}, {trials} trials"
            for name, (top, trials) in level_info().items()))
        st.selectbox("Difficulty", list(LEVELS),
                     index=list(LEVELS).index(st.session_state.level), key="level_choice")
        st.text_input("Your name (optional)", value=st.session_state.player_name,
                      key="name_choice")
        st.checkbox("Show my possible range (easier)", value=st.session_state.show_range,
                    key="range_choice")
        st.button("Start Game", type="primary", on_click=begin_game)


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


def play(guess, timed_out=False):
    game = st.session_state.game
    before = snap(game)
    lib.process_turn(guess, ctypes.byref(game))
    record = cl.make_turn_record(before, snap(game), timed_out=timed_out)
    st.session_state.history.append(record)
    st.session_state.rows.append({"#": len(st.session_state.history),
                                  "Guess": guess,
                                  "Result": ("Time ran out" if timed_out
                                             else result_text(guess, game, record))})
    name = (st.session_state.get("player_name") or "").strip() or None
    st.session_state.reply = cl.get_reply(st.session_state.history, game.range_max,
                                          game.secret_number, name, pick_call_model())
    st.session_state.deadline = None        # next turn starts a fresh clock
    if game.game_status == 1:
        st.session_state.pending_sound = "victory"
    elif game.game_status == 2:
        st.session_state.pending_sound = "defeat"


def time_is_up():
    deadline = st.session_state.get("deadline")
    return deadline is not None and time.time() >= deadline


@st.fragment(run_every=0.5)
def show_timer(limit):
    """Countdown. Redraws itself twice a second and triggers a full rerun at 0."""
    deadline = st.session_state.get("deadline")
    if deadline is None:                    # stale tick after a turn ended
        return
    left = deadline - time.time()
    if left <= 0:
        st.progress(0.0, text="⏱ Time's up")
        st.rerun()                          # full rerun: the main script queues the penalty
    st.progress(max(0.0, min(1.0, left / limit)),
                text=f"⏱ {math.ceil(left)}s left")


def show_reply(reply):
    last = st.session_state.history[-1] if st.session_state.history else None
    timed_out = bool(last and last.get("timed_out") and reply["theme"] == "crimson")
    show_banner(reply["theme"], reply["ai_message"], "Time ran out" if timed_out else None)
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
                yours = ("timed out (wasted)" if record.get("timed_out")
                         else str(record["guess"]) + ("" if record["legal"] else " (wasted)"))
            else:
                yours = "-"
            rows.append({"Turn": index + 1, "Optimal bot": bot_guess, "You": yours})
        st.dataframe(rows, hide_index=True)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Options")
    st.checkbox("Use Gemini for messages", key="use_gemini")
    st.checkbox("Enable Pressure Mode", key="pressure_mode",
                help="Time limit per guess: Easy 20s, Medium 15s, Hard 10s.")
    if st.session_state.has_started:
        st.caption(f"Difficulty: {st.session_state.level}")
        st.button("New game", on_click=back_to_rules)

# ---------------------------------------------------------------- page theme
st.markdown(build_css(current_theme()), unsafe_allow_html=True)

# ---------------------------------------------------------------- rules gate
if not st.session_state.has_started:
    show_rules()
    show_footer()
    st.stop()

if "game" not in st.session_state:          # safety net: started, but no game object yet
    start_new_game()
game = st.session_state.game
history = st.session_state.history

# ---------------------------------------------------------------- game page
st.title("SAM_CogSys")
st.caption("Guess the number. The engine measures how you search.")

if game.game_status == -1:                  # cannot happen from the selector; kept as a guard
    st.error("The engine reported an invalid difficulty.")
    show_footer()
    st.stop()

if game.game_status == 0 and st.session_state.get("pressure_mode"):
    limit = PRESSURE_LIMITS[st.session_state.level]


@st.cache_data
def load_sound(name):
    """Bytes of a local .mp3, or None if the file is missing (the game stays silent)."""
    try:
        with open(os.path.join(SOUND_DIR, SOUND_FILES[name]), "rb") as handle:
            return handle.read()
    except OSError:
        return None




def play_pending_sound(playing):
    """One audio slot: a queued sound (victory/defeat) wins, else music while playing."""
    name = st.session_state.pop("pending_sound", None)
    if name is None and playing:
        name = "music"
    data = load_sound(name) if name else None
    if data:
        st.audio(data, format="audio/mpeg", autoplay=True, loop=(name == "music"))


# --- GAME PAGE START ---
play_pending_sound(game.game_status == 0)

pending = st.session_state.pop("pending_guess", None)
if pending is not None and game.game_status == 0:
    st.session_state.deadline = None
    with st.spinner("Checking your guess..."):
        play(pending["guess"], timed_out=pending["timed_out"])
    st.rerun()                              # redraw so a finished game hides the form

timer_slot = st.container()                 # the timer is drawn here, after the form code
limit = None
if game.game_status == 0 and st.session_state.get("pressure_mode"):
    limit = PRESSURE_LIMITS[st.session_state.level]
    if st.session_state.get("deadline") is None:
        st.session_state.deadline = time.time() + limit
else:
    st.session_state.deadline = None


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
            st.session_state.deadline = None
            st.session_state.pending_guess = {"guess": int(guess), "timed_out": False}
            st.rerun()                      # the next run plays it, with no timer on screen
    elif time_is_up():
        st.session_state.deadline = None
        st.session_state.pending_guess = {"guess": 0, "timed_out": True}   # engine treats 0 as illegal
        st.rerun()


if limit is not None:
    with timer_slot:
        show_timer(limit)

if st.session_state.reply:
    show_reply(st.session_state.reply)
elif game.game_status == 0:

    show_banner("neutral", "Type a number and press Guess.")

if game.game_status in (1, 2):
    st.write(f"The number was **{game.secret_number}**.")
    show_ghost_bot(game, history, LEVELS[st.session_state.level])
    st.button("Play Again", type="primary", on_click=back_to_rules)

left, middle, right = st.columns(3)
left.metric("Trials left", game.trials_remaining)
middle.metric("Guesses made", len(history))
if st.session_state.show_range and game.game_status == 0:
    right.metric("Possible range", f"{game.current_min} to {game.current_max}")

if st.session_state.rows:
    st.subheader("Your guesses")
    st.dataframe(st.session_state.rows, hide_index=True)

with st.expander("Engine telemetry"):
    reply = st.session_state.reply or {}
    if reply:
        st.caption(f"theme: {reply['theme']} | source: {reply['source']}")
    data = snap(game)
    if game.game_status == 0:
        data.pop("secret_number")           # never show the secret while playing
    st.code(json.dumps({"engine_struct": data, "last_turn": history[-1] if history else None},
                       indent=2), language="json")

show_footer()
