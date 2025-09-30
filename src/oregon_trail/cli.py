"""Command line interface for the Oregon Trail game."""
from __future__ import annotations

import argparse
import random
from typing import List

from .game import Difficulty, Game


def prompt_choice(prompt: str, options: List[str]) -> str:
    """Prompt the user to pick an option from a list."""

    while True:
        print(prompt)
        for idx, option in enumerate(options, start=1):
            print(f"  {idx}. {option.capitalize()}")
        selection = input(
            "Select an option by number (or press Enter to choose the first): "
        ).strip()
        if not selection:
            return options[0]
        if selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(options):
                return options[index]
        print("Invalid choice. Please try again.\n")


def prompt_pace() -> str:
    return prompt_choice("Choose your travel pace:", list(Game.pace_options()))


def prompt_action(actions: List[str]) -> str:
    return prompt_choice("What will you do today?", actions)


def configure_game_from_args() -> Game:
    parser = argparse.ArgumentParser(description="Play the classic Oregon Trail.")
    parser.add_argument("--name", help="Name of the party leader.")
    parser.add_argument(
        "--profession",
        help="Chosen profession (banker, carpenter, farmer, doctor).",
    )
    parser.add_argument(
        "--difficulty",
        choices=[level.value for level in Difficulty],
        help="Difficulty setting.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible games.",
    )
    args = parser.parse_args()

    name = args.name or input("What is your name, traveler? ").strip() or "Pioneer"
    professions = list(Game.available_professions())
    profession = args.profession
    if not profession:
        profession = prompt_choice(
            "Choose your profession:", [p.capitalize() for p in professions]
        ).lower()
    else:
        profession = profession.lower().strip()
    if profession not in professions:
        raise SystemExit(
            f"Unsupported profession '{profession}'. Choose from: {', '.join(professions)}."
        )

    if args.difficulty:
        difficulty = Difficulty.from_choice(args.difficulty)
    else:
        difficulty = Difficulty.from_choice(
            prompt_choice(
                "Choose your difficulty:",
                [level.value for level in Difficulty],
            )
        )

    rng = random.Random(args.seed) if args.seed is not None else None
    return Game(name, profession, difficulty=difficulty, rng=rng)


def print_day_header(game: Game) -> None:
    state = game.state
    print("\n" + "=" * 60)
    print(f"Day {state.day} on the trail")
    print("=" * 60)
    print(f"Weather: {state.weather} | Terrain: {state.terrain}")
    print(f"Distance: {state.distance}/{Game.TARGET_MILES} miles")
    print(
        f"Health: {state.health} | Food: {state.food} lbs | Ammo: {state.ammo} | Money: ${state.money}"
    )
    print(f"Status: {state.status}")


def handle_trade(game: Game) -> dict:
    offers = game.get_trade_offers()
    if not offers:
        print("No traders are available today.")
        return game.perform_action("trade", offer_index=None)
    print("Trading Post Offers:")
    for idx, offer in enumerate(offers, start=1):
        print(f"  {idx}. {offer.describe()}")
    print("  0. Leave without trading")
    choice = input("Choose an offer (0 to skip): ").strip() or "0"
    if not choice.isdigit():
        print("Invalid input, skipping trade.")
        return game.perform_action("trade", offer_index=None)
    index = int(choice)
    if index == 0:
        return game.perform_action("trade", offer_index=None)
    return game.perform_action("trade", offer_index=index - 1)


def main() -> None:
    game = configure_game_from_args()
    print("\nWelcome to the Oregon Trail! Prepare for the long journey ahead.")

    while not game.is_over:
        print_day_header(game)
        actions = list(game.available_actions())
        if not actions:
            raise SystemExit("No available actions. The game cannot continue.")
        action = prompt_action(actions)
        if action == "travel":
            pace = prompt_pace()
            result = game.perform_action(action, pace=pace)
        elif action == "trade":
            result = handle_trade(game)
        else:
            result = game.perform_action(action)

        for message in result.get("messages", []):
            print(f"- {message}")

    print("\n" + "=" * 60)
    print(game.state.status)
    if game.state.won:
        print(
            f"You arrive in Oregon with {game.state.food} lbs of food, {game.state.ammo} ammo, and ${game.state.money}."
        )
    else:
        print("Your journey ends here. Perhaps try a different strategy next time.")


if __name__ == "__main__":
    main()
