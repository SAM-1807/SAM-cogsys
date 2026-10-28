#include "game.h"
#include <stdlib.h>
#include <string.h>
#include <time.h>

/**
 * set_level - Sets range and trials for a difficulty level
 * @metrics: Pointer to the GameTelemetry struct
 * @difficulty: 1 for Easy, 2 for Medium, 3 for Hard
 *
 * Return: 1 if the difficulty is valid, 0 otherwise
 */
static int set_level(GameTelemetry *metrics, int difficulty)
{
	if (difficulty == 1)
	{
		metrics->range_max = 100;
		metrics->trials_remaining = 7;
	}
	else if (difficulty == 2)
	{
		metrics->range_max = 500;
		metrics->trials_remaining = 9;
	}
	else if (difficulty == 3)
	{
		metrics->range_max = 1000;
		metrics->trials_remaining = 10;
	}
	else
	{
		return (0);
	}

	return (1);
}

/**
 * init_game - Initializes the game telemetry structure
 * @metrics: Pointer to the GameTelemetry struct
 * @difficulty: 1 for Easy, 2 for Medium, 3 for Hard
 *
 * Return: Nothing. An invalid difficulty leaves every field at 0 except
 * game_status, which is set to -1 (error state).
 */
void init_game(GameTelemetry *metrics, int difficulty)
{
	static int seeded;

	if (metrics == NULL)
		return;

	memset(metrics, 0, sizeof(*metrics));

	if (!set_level(metrics, difficulty))
	{
		metrics->game_status = -1;
		return;
	}

	if (!seeded)
	{
		srand((unsigned int)time(NULL));
		seeded = 1;
	}

	metrics->current_min = 1;
	metrics->current_max = metrics->range_max;
	metrics->secret_number = (rand() % metrics->range_max) + 1;
}

/**
 * narrow_window - Tightens the bounds after an in-bounds guess
 * @guess: The player's guess, already known to be inside the bounds
 * @metrics: Pointer to the GameTelemetry struct
 *
 * Return: Nothing. space_velocity becomes the percentage of the old window
 * removed by this guess, or 100 if the guess wins.
 */
static void narrow_window(int guess, GameTelemetry *metrics)
{
	int old_window;
	int new_window;

	old_window = metrics->current_max - metrics->current_min + 1;

	if (guess == metrics->secret_number)
	{
		metrics->current_min = guess;
		metrics->current_max = guess;
		metrics->space_velocity = 100;
		return;
	}

	if (guess > metrics->secret_number)
		metrics->current_max = guess - 1;
	else
		metrics->current_min = guess + 1;

	new_window = metrics->current_max - metrics->current_min + 1;
	metrics->space_velocity =
		((old_window - new_window) * 100) / old_window;
}

/**
 * process_turn - Processes a single guess and updates telemetry
 * @guess: The player's guessed number
 * @metrics: Pointer to the GameTelemetry struct
 *
 * Return: Nothing. Every guess costs one trial, including out-of-bounds
 * guesses. Calls made after the game has ended are ignored.
 */
void process_turn(int guess, GameTelemetry *metrics)
{
	if (metrics == NULL || metrics->game_status != 0)
		return;

	metrics->last_guess = guess;
	metrics->logical_entropy = 0;
	metrics->space_velocity = 0;
	metrics->distance_vector = abs(guess - metrics->secret_number);
	metrics->trials_remaining--;

	if (guess < metrics->current_min || guess > metrics->current_max)
		metrics->logical_entropy = 1;
	else
		narrow_window(guess, metrics);

	if (guess == metrics->secret_number)
		metrics->game_status = 1;
	else if (metrics->trials_remaining <= 0)
		metrics->game_status = 2;
}
