"""Unit tests for the Oregon Trail core game logic."""
from __future__ import annotations

import random

import pytest

from oregon_trail import Difficulty, Game, TradeOffer


@pytest.fixture()
def base_game() -> Game:
    game = Game("Tester", "banker", difficulty=Difficulty.NORMAL, rng=random.Random(0))
    game.event_chance = 0.0  # Deterministic tests
    return game


def test_game_initial_resources(base_game: Game) -> None:
    state = base_game.state
    assert state.food == 240
    assert state.ammo == 55
    assert state.money == 1700
    assert state.health == 100


def test_travel_consumes_food_and_moves_forward(base_game: Game) -> None:
    state = base_game.state
    starting_distance = state.distance
    starting_food = state.food
    base_game.perform_action("travel", pace="steady")
    assert base_game.state.distance > starting_distance
    assert base_game.state.food < starting_food


def test_hunt_requires_ammo_and_adds_food(base_game: Game) -> None:
    starting_food = base_game.state.food
    starting_ammo = base_game.state.ammo
    base_game.perform_action("hunt", ammo_spent=5)
    assert base_game.state.ammo == starting_ammo - 5
    assert base_game.state.food > starting_food


def test_rest_recovers_health(base_game: Game) -> None:
    base_game.state.health = 50
    base_game.perform_action("rest")
    assert base_game.state.health > 50


def test_trading_post_purchase(base_game: Game) -> None:
    base_game.state.trade_available = True
    base_game.current_trade_offers = [TradeOffer(item="food", quantity=20, price=40)]
    starting_money = base_game.state.money
    starting_food = base_game.state.food
    base_game.perform_action("trade", offer_index=0)
    assert base_game.state.money == starting_money - 40
    assert base_game.state.food > starting_food
