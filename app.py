"""app.py - SAM_CogSys: elite dark-mode card architecture with dynamic theme backgrounds."""
import ctypes
import os
import subprocess

import streamlit as st

st.set_page_config(page_title="SAM_CogSys", page_icon="🧠", layout="centered")

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "libgame.so")
SOURCE = os.path.join(HERE, "game.c")


def build_library():
    """Try to compile libgame.so. Return an error text, or None on success."""
    try:
        build = subprocess.run(["gcc", "-shared", "-fPIC", "-o", LIB, SOURCE],
                               capture_output=True, text=True)
    except OSError as err:
        return f"gcc not available: {err}"
    return None if build.returncode == 0 else build.stderr


# Rebuild when the library is missing or older than game.c.
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
except Exception:
    pass

from bridge import GameTelemetry, lib, new_game
import cogsys_logic as cl

LEVELS = {"Easy": 1, "Medium": 2, "Hard": 3}

# Session state used by this app.
for _key, _default in (("has_started", False), ("level", "Easy"),
                       ("player_name", ""), ("show_range", False), ("theme", None)):
    st.session_state.setdefault(_key, _default)

# ---------------------------------------------------------------- ELITE DARK-MODE & DYNAMIC THEME CSS
def apply_theme_css(theme):
    """Injects sleek dark-mode card styling while allowing dynamic page backgrounds on events."""

    # Determine background color based on active theme
    bg_color = "#0b0b0b"
    sidebar_bg = "#141414"
    border_color = "#262626"
    card_bg = "#141414"
    extra_css = ""

    if theme == "crimson":
        bg_color = "#B22222"
        sidebar_bg = "#8B0000"
        border_color = "#ff6b6b"
        card_bg = "#801f1f"
    elif theme == "green":
        bg_color = "#008751"
        sidebar_bg = "#004D2C"
        border_color = "#2ecc71"
        card_bg = "#00663d"
    elif theme == "gold":
        bg_color = "#FFD700"
        sidebar_bg = "#DAA520"
        border_color = "#fff275"
        card_bg = "#cca300"
    elif theme == "victory":
        bg_color = "#008751"
        sidebar_bg = "#004D2C"
        border_color = "#FFD700"
        card_bg = "#00663d"
        extra_css = ".stApp { border: 8px solid #FFD700; box-sizing: border-box; }"
    elif theme == "defeat":
        bg_color = "#333333"
        sidebar_bg = "#1a1a1a"
        border_color = "#555555"
        card_bg = "#222222"

    text_color = "black" if theme == "gold" else "white" if theme else "#f0f0f0"
    sidebar_text = "black" if theme == "gold" else "white" if theme else "#e0e0e0"

    css = f"""
    <style>
    /* Global App Background & Dynamic Theme */
    .stApp {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    {extra_css}

    /* Sidebar Styling */
    [data-testid='stSidebar'] {{
        background-color: {sidebar_bg} !important;
        border-right: 1px solid {border_color};
    }}
    [data-testid='stSidebar'] p, [data-testid='stSidebar'] span, [data-testid='stSidebar'] label, [data-testid='stSidebar'] h2 {{
        color: {sidebar_text} !important;
    }}

    /* Card Containers */
    div.stMarkdownContainer, div[data-testid="stVerticalBlock"] > div[style*="border"] {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 16px;
        padding: 1.2rem;
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        margin-bottom: 1rem;
    }}

    /* Metric Cards */
    div[data-testid="stMetric"] {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }}
    div[data-testid="stMetric"] label {{
        color: {'#333333' if theme == 'gold' else '#aaaaaa'} !important;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {text_color} !important;
    }}

    /* Buttons */
    .stButton > button {{
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid {border_color};
        background-color: {'#fff' if theme == 'gold' else '#1f1f1f'};
        color: {'#000' if theme == 'gold' else '#ffffff'};
        transition: all 0.2s ease;
    }}
    .stButton > button:hover {{
        border-color: #555;
        background-color: {'#e6dfa1' if theme == 'gold' else '#2a2a2a'};
    }}
    .stButton > button[kind="primary"] {{
        background: {'linear-gradient(135deg, #FFD700, #cca300)' if theme == 'victory' else 'linear-gradient(135deg, #2563eb, #1d4ed8)'};
        border: none;
        color: {'black' if theme == 'victory' else 'white'};
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def snap(game):
    return {name: getattr(game, name) for name, _ in GameTelemetry._fields_}


def start_new_game():
    st.session_state.game = new_game(LEVELS[st.session_state.level])
    st.session_state.history = []
    st.session_state.rows = []
    st.session_state.reply = None
    st.session_state.theme = None


def begin_game():
    state = st.session_state
    state.level = state.get("level_choice", state.level)
    state.player_name = (state.get("name_choice", state.player_name) or "").strip()
    state.show_range = bool(state.get("range_choice", state.show_range))
    start_new_game()
    state.has_started = True


def back_to_rules():
    st.session_state.has_started = False
    st.session_state.theme = None


@st.cache_data
def level_info():
    info = {}
    for name, level in LEVELS.items():
        probe = new_game(level)
        info[name] = (probe.range_max, probe.trials_remaining)
    return info


def show_footer():
    st.markdown(
            "<div style='text-align: center; color: inherit; font-size: 1.1rem; font-weight: 700; "
            "padding-top: 3rem; letter-spacing: 1px; text-shadow: 0px 1px 2px rgba(0,0,0,0.3);'>Developed by SAM</div>",
            unsafe_allow_html=True)


def show_rules():
    st.title("SAM_CogSys")
    st.caption("High-performance psychometric telemetry engine.")
    with st.container():
        st.subheader("How to play")
        st.markdown(
                "1. The game picks a secret number. Find it before your trials run out.\n"
                "2. Every guess costs one trial. After each guess you see \"Too low\" "
                "or \"Too high\".\n"
                "3. **Penalty:** a guess outside the range you have already narrowed "
                "down is wasted. It costs a trial and teaches you nothing.\n"
                "4. After each guess, an AI mentor reacts to how well you searched.\n"
                "5. At the end, your path is compared with a perfect optimal search.")
        st.markdown("\n".join(
            f"- **{name}:** numbers 1 to {top}, {trials} trials"
            for name, (top, trials) in level_info().items()))
        st.selectbox("Difficulty", list(LEVELS),
                     index=list(LEVELS).index(st.session_state.level), key="level_choice")
        st.text_input("Your name (optional)", value=st.session_state.player_name,
                      key="name_choice")
        st.checkbox("Show my possible range (easier)", value=st.session_state.show_range,
                    key="range_choice")
        st.button("Start Game", type="primary", on_click=begin_game, use_container_width=True)


@st.cache_resource
def load_gemini():
    from gemini_client import make_call_model
    return make_call_model()


def gemini_off(system_prompt, payload_json):
    raise RuntimeError("Gemini is switched off")


def pick_call_model():
    if st.session_state.get("use_gemini"):
        try:
            return load_gemini()
        except Exception:
            st.sidebar.warning("Gemini unavailable. Using local messages.")
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
    if st.session_state.reply:
        st.session_state.theme = st.session_state.reply.get("theme")


def show_reply(reply):
    """Displays the AI message inside a polished feedback card."""
    labels = {
            "crimson": "⚠️ WAHALA (Logical Error)",
            "gold": "🔥 E DON NEAR (Very Close)",
            "green": "✅ SHARP (Efficient)",
            "victory": "🏆 VICTORY",
            "defeat": "💀 DEFEAT"
            }
    with st.container():
        st.subheader(labels.get(reply["theme"], ""))
        st.write(f"**{reply['ai_message']}**")
        st.caption(f"theme: {reply['theme']} | source: {reply['source']}")
        if reply["game_summary"]:
            st.write(reply["game_summary"])


def optimal_path(level, secret):
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
    optimal = optimal_path(level, game.secret_number)
    if optimal is None:
        return
    mine = len(history)
    wasted = sum(1 for record in history if not record["legal"])

    with st.container():
        st.subheader("Optimal path vs your path")
        left, right = st.columns(2)
        left.metric("Optimal Path", plural(len(optimal)))
        right.metric("Your Path", plural(mine))
        st.caption("Optimal = a perfect halving search algorithm.")

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

        st.caption(f"Efficient turns: {mine - wasted} | Wasted turns: {wasted}")

        with st.expander("See the optimal path breakdown"):
            rows = []
            for index in range(max(len(optimal), mine)):
                bot_guess = str(optimal[index]) if index < len(optimal) else "-"
                if index < mine:
                    record = history[index]
                    yours = str(record["guess"]) + ("" if record["legal"] else " (wasted)")
                else:
                    yours = "-"
                rows.append({"Turn": index + 1, "Optimal bot": bot_guess, "You": yours})
            st.dataframe(rows, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------- APPLY THEME
apply_theme_css(st.session_state.get("theme"))

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Session Options")
    st.checkbox("Use Gemini for messages", key="use_gemini")
    if st.session_state.has_started:
        st.caption(f"Difficulty: {st.session_state.level}")
        st.button("New game", on_click=back_to_rules, use_container_width=True)

# ---------------------------------------------------------------- rules gate
if not st.session_state.has_started:
    show_rules()
    show_footer()
    st.stop()

if "game" not in st.session_state:
    start_new_game()
game = st.session_state.game
history = st.session_state.history

# ---------------------------------------------------------------- game page
st.title("SAM_CogSys")
st.caption("Guess the number. Analyzing search telemetry in real-time.")

if game.game_status == -1:
    st.error("The engine reported an invalid difficulty.")
    show_footer()
    st.stop()

if game.game_status == 0:
    with st.container():
        with st.form("guess_form", clear_on_submit=True):
            guess = st.number_input(f"Your guess (1 to {game.range_max})", min_value=1,
                                    max_value=game.range_max, value=None, step=1,
                                    placeholder="Type a number")
            submitted = st.form_submit_button("Submit Guess", use_container_width=True)
        if submitted:
            if guess is None:
                st.warning("Type a number first.")
            else:
                play(int(guess))
                st.rerun()

if st.session_state.get("reply"):
    show_reply(st.session_state.reply)

if game.game_status in (1, 2):
    st.markdown(f"### The number was **{game.secret_number}**.")
    show_ghost_bot(game, history, LEVELS[st.session_state.level])
    st.button("Play Again", type="primary", on_click=start_new_game, use_container_width=True)

col1, col2, col3 = st.columns(3)
col1.metric("Trials left", game.trials_remaining)
col2.metric("Guesses made", len(history))
if st.session_state.show_range and game.game_status == 0:
    col3.metric("Possible range", f"{game.current_min} to {game.current_max}")

if st.session_state.rows:
    with st.container():
        st.subheader("Your guesses")
        st.dataframe(st.session_state.rows, hide_index=True, use_container_width=True)

with st.expander("Engine telemetry stream"):
    data = snap(game)
    if game.game_status == 0:
        data.pop("secret_number")
    st.json({"engine_struct": data, "last_turn": history[-1] if history else None})

show_footer()
