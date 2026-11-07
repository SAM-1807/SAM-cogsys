# SAM_CogSys

**The problem:** Most assessments only measure whether you got the right answer, not *how* you got there. Two candidates can score the same while one guesses randomly and the other uses systematic logic. SAM_CogSys is a web-based game that makes the search process visible.

## 🏆 Hackathon Submission: BUILDUP UNIZIK 2026

This project was built for the BUILDUP UNIZIK hackathon (Nov 2–7, 2026). It is a number-guessing game that uses a high-performance C engine to calculate search telemetry, and the Gemini API to generate real-time feedback on the player's search strategy.

**Live Demo:** [https://sam-cogsys.streamlit.app/](https://sam-cogsys.streamlit.app/)

### 💡 Who Is This For?

- **Primary:** Computer Science students learning algorithmic thinking (like binary search).
- **Secondary:** Educators and technical recruiters who want to assess problem-solving *process*, not just final answers.

### 🛠️ How It Works: The 4-Layer Architecture

1. **The Core (C Engine):** A stateless shared library (`libgame.so`) that handles the math. It computes a 10-field telemetry struct (search velocity, distance, logical entropy, bounds).
                            2. **The Bridge (Python):** Uses `ctypes` to map the C struct to Python.
                                                        3. **The Logic (Python):** Calculates window-relative proximity, decides the UI theme deterministically, validates the AI's JSON, and runs a local fallback engine if the API fails.
                                                                                   4. **The Voice (Gemini API):** Gemini receives the telemetry and writes live commentary and end-game search-strategy summaries in a witty Nigerian persona ("Naija Persona").

### ⚙️ Technical Definitions

                                                                                                                  - **`logical_entropy`:** A flag that triggers when a player guesses outside the current valid bounds (ignoring information they already learned).
                                                                                                                  - **`space_velocity`:** The percentage of the search space eliminated by a single guess.
                                                                                                                  - **Timeouts (Pressure Mode):** If the timer runs out, the game auto-submits a guess of `0` (costing a trial). The system explicitly reports this to the AI as a "time-out," not an "illegal guess."

### 🔌 Google Product Integration (Gemini)

                                                                                                                                                  - **The Model:** We use `gemini-3.5-flash-lite`.
                                                                                                                                                  - **The Split:** Python calculates the exact math and picks the UI theme. Gemini is only allowed to generate the text (`ai_message`) and the end-game summary (`game_summary`).
                                                                                                                                                  - **Security:** The API key is stored in a `.env` file locally and in Streamlit Cloud "Secrets" in production. It is never committed to the repo.
                                                                                                                                                  - **No Key? No Problem:** The game works without a Gemini API key. If the key is missing or the API times out (3-second limit), the Python layer instantly falls back to a local rule-based engine so the game never crashes.

                                                                                                                                                  ---

## 📅 Pre-Hackathon vs. Hackathon Work

                                                                                                                                                  To comply with the hackathon rules, this section distinguishes what was built before the event from what was built during it. The Git tag `hackathon-start` marks the exact boundary.

### Pre-Hackathon: The Baseline

                                                                                                                                                  - The original terminal-based number-guessing game (C).
                                                                                                                                                  - The refactored C engine (`game.c` / `game.h`) and the `ctypes` Python bridge (`bridge.py`).
                                                                                                                                                  - The initial logic layer (`cogsys_logic.py`) and 50 offline tests.
                                                                                                                                                  - The initial Gemini prompt and JSON validator.

### Built During the Hackathon (November 2–7, 2026)

                                                                                                                                                  - The entire Streamlit UI (`app.py`), including dark-mode CSS, dynamic themes, and a mobile-responsive grid (tested on ARM64/mobile).
                                                                                                                                                  - The Rules Gate, footer, and game flow.
                                                                                                                                                  - The **Ghost Bot** optimal-path simulator.
                                                                                                                                                  - The **Naija Persona** prompt tuning and local fallback voice.
                                                                                                                                                  - The **Pressure Mode** timer and timeout-penalty logic.
                                                                                                                                                  - Audio integration (victory, defeat, and background music).
                                                                                                                                                  - **Deployment Engineering:** Streamlit Cloud doesn't reliably ship `gcc`. We solved this by pre-compiling `libgame.so` locally and committing the binary. *(Note: If `game.c` is ever changed, the `.so` must be rebuilt and recommitted).*

                                                                                                                                                  ---

## 🚀 Running Locally

### Requirements

                                                                                                                                                  - `gcc`
                                                                                                                                                  - `python3`

### Setup and Execution

                                                                                                                                                  1. **Build the C library:**

                                                                                                                                                  ```bash
                                                                                                                                                  gcc -shared -fPIC -Wall -Wextra -Wpedantic -std=c99 -o libgame.so game.c
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

                                                                                                                                                  **Audio Credits:** "Champions" by Walen and "Summer Time" by Nebulite (Free To Use Music).
