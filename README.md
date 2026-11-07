# SAM_CogSys

An AI-powered behavioral diagnostic game engine that measures *how* a player thinks, not just whether they win.

## 🏆 Hackathon Submission: BUILDUP UNIZIK 2026

This project was built for the BUILDUP UNIZIK hackathon (November 2–7, 2026). It is a web-based behavioral diagnostic tool disguised as a number-guessing game. It combines a high-performance C engine for calculating search telemetry with the Gemini API for generating real-time feedback based on the player's cognitive strategy.

**Live Demo:** [https://sam-cogsys.streamlit.app/](https://sam-cogsys.streamlit.app/)

### 💡 Why This Matters

Most assessments focus on whether someone gets the right answer, not how they arrived at it. SAM_CogSys explores a different approach: using gameplay to observe decision-making patterns, search strategies, and responses under pressure. The goal is to make the thinking process measurable, not just the final outcome.

## 🛠️ How It Works: The 4-Layer Architecture

1. **The Core (C Engine):** A stateless shared library (`libgame.so`) that handles the calculations. It computes 10 behavioral telemetry metrics, including search velocity, distance, and logical entropy, in microseconds.
2. **The Bridge (Python):** Uses `ctypes` to map the C struct to Python.
3. **The Logic (Python):** The brain of the app. It calculates window-relative proximity, determines the UI theme deterministically, validates the AI's JSON, and runs a local fallback engine if the API fails.
4. **The Voice (Gemini API):** Gemini receives the telemetry and generates live commentary and end-game cognitive strategy profiles in a witty Nigerian persona (the "Naija Persona").

### Understanding Logical Entropy

The `logical_entropy` metric tracks whether a player's guess falls outside the currently valid search boundaries. It provides an indication of how well the player maintains logical consistency during the search.

This is an operational behavioral metric, not a claim of calculating Shannon entropy or measuring a validated psychological construct.

## ✨ Key Features

- **Cognitive Strategy Telemetry:** Observes whether a player searches systematically or resorts to random guessing. It uses behavioral indicators such as search velocity, guess distance, and logical consistency.
- **Ghost Bot Comparison:** At the end of the game, the app simulates an optimal binary search for the specific secret number and compares the player's path to the mathematical ideal.
- **Dynamic UI Themes:** The entire screen changes color based on the theme: crimson for errors, Matrix green for efficiency, and gold for proximity.
- **Pressure Mode:** A toggleable ticking clock with time limits of 20 seconds (Easy), 15 seconds (Medium), and 10 seconds (Hard). It introduces time pressure and penalizes slow decision-making.
- **Fault-Tolerant AI:** If the Gemini API times out (after a 3-second limit) or returns invalid output, the Python layer immediately falls back to a local rule-based engine so the game does not crash.

---

## 📅 Pre-Hackathon vs. Hackathon Work

To comply with the hackathon rules, this section clearly distinguishes what was built before the event from what was built during it. The Git tag `hackathon-start` marks the exact boundary.

### Pre-Hackathon: The Baseline

- The original terminal-based number-guessing game (C).
- The refactored C engine (`game.c` / `game.h`) and the `ctypes` Python bridge (`bridge.py`).
- The initial logic layer (`cogsys_logic.py`) and 50 offline tests.
- The initial Gemini prompt and JSON validator.

### Built During the Hackathon (November 2–7, 2026)

- The entire Streamlit UI (`app.py`), including dark-mode CSS, dynamic themes, and a mobile-responsive grid.
- The Rules Gate, footer, and game flow.
- The **Ghost Bot** optimal-path simulator.
- The **Naija Persona** prompt tuning and local fallback voice.
- The **Pressure Mode** timer and timeout-penalty logic.
- Audio integration (victory, defeat, and background music).
- Cloud deployment and pre-compilation of `libgame.so` for Streamlit Community Cloud.

### ☁️ Deployment Engineering: The Precompiled C Engine

One of the deployment challenges was ensuring that the C engine would work reliably on Streamlit Community Cloud.

Rather than depending on the cloud environment to have GCC available and compile the shared library at runtime, the project includes a precompiled `libgame.so` binary.

This allows the Python application to load the C engine directly through `ctypes`, avoiding a runtime compilation dependency and making deployment more reliable.

---

## 🚀 Running Locally

### Requirements

- `gcc`
- `make`
- `python3`

### Setup and Execution

1. **Build the C library:**

   ```bash
   make
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**

   ```bash
   streamlit run app.py
   ```

---

## 🧪 Testing

The project has extensive test coverage:

- **C Engine:** `python3 test_engine.py` — 75 checks passing.
- **Python Logic:** `python3 test_logic.py` — 50 checks passing.

---

## 👨🏾💻 Author

**Agbai Samuel Chibuike (SAM)**  
200-Level Computer Science Student, Nnamdi Azikiwe University.

Developed for the **BUILDUP UNIZIK Hackathon 2026**.
