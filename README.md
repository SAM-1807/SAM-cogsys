An AI psychometric game engine written in C and Python.

Measures how a player thinks, not just whether they win. This repository
contains the pre-hackathon baseline for the BUILDUP UNIZIK hackathon
(Nov 2-7, 2026).

The project began as a terminal-based number guessing game. The original
terminal version and its full git history can be found here:
https://github.com/SAM-1807/my_number_guessing_game

## How it works

The C engine is a stateless shared library (libgame.so). Python owns
the game state, passes a guess into C, and reads back 10 telemetry
metrics.

- **range_max** and **trials_remaining** set the difficulty
- **current_min** and **current_max** track the valid search bounds
- **logical_entropy** flags a guess that falls outside the bounds
- **space_velocity** shows the percentage of the search space removed
- **distance_vector** shows the absolute difference from the secret

Difficulty levels are 1 (100 range, 7 trials), 2 (500 range, 9 trials),
           and 3 (1000 range, 10 trials). An invalid difficulty returns a struct
           with game_status set to -1.

## Building

           Requires `gcc`, `make`, and `python3`.

           make

           To clean up the build:

           make clean

## Running tests

           make test

## Project structure

           game.c          C engine: init_game, process_turn, telemetry
           game.h          Struct definition and function prototypes
           bridge.py       ctypes bridge mapping the C struct to Python
           test_engine.py  75 checks for bounds, wins, losses, and penalties
           Makefile        Build rules for libgame.so and tests

## Implementation notes

           - Standard C99, compiled with `-Wall -Wextra -Wpedantic -std=c99`
           - Stateless library design; all game state is passed in and out via
           the GameTelemetry struct
           - Python validates the game_status before processing turns
           - proximity_score is not part of the C struct. Python computes it
           from distance_vector and range_max using the formula
           100 - (distance / (range_max - 1)) * 100, clamped to 0-100, and
           sends it to Gemini instead of the raw distance so the score is
           comparable across difficulties
           - distance_vector is computed in 64-bit arithmetic and clamped to
           INT_MAX, so extreme guesses cannot trigger signed overflow
           - Tested on x86-64 with gcc and on ARM64 with clang
    - The Streamlit UI, Gemini AI integration, and deployment will be
built during the hackathon window (Nov 2-7)

## Author

    SAM
    EOF
