"""Core game logic for the Oregon Trail recreation."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import math
import random
from typing import Dict, Iterable, List, Optional


class Difficulty(Enum):
    """Supported difficulty levels for the game."""

    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"

    @classmethod
    def from_choice(cls, value: str) -> "Difficulty":
        value = value.lower().strip()
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown difficulty '{value}'.")


PACE_SPEEDS: Dict[str, int] = {
    "slow": 12,
    "steady": 18,
    "grueling": 24,
}

PACE_FOOD_MULTIPLIER: Dict[str, float] = {
    "slow": 0.8,
    "steady": 1.0,
    "grueling": 1.35,
}

BASE_FOOD_PER_DAY = 5
TARGET_MILES = 2000

DIFFICULTY_SETTINGS: Dict[Difficulty, Dict[str, float]] = {
    Difficulty.EASY: {
        "food": 300,
        "ammo": 70,
        "money": 1400,
        "event_chance": 0.18,
        "rest_health": 15,
        "starvation_penalty": 8,
        "max_days": 60,
    },
    Difficulty.NORMAL: {
        "food": 240,
        "ammo": 55,
        "money": 1100,
        "event_chance": 0.27,
        "rest_health": 12,
        "starvation_penalty": 10,
        "max_days": 55,
    },
    Difficulty.HARD: {
        "food": 200,
        "ammo": 45,
        "money": 900,
        "event_chance": 0.35,
        "rest_health": 9,
        "starvation_penalty": 12,
        "max_days": 50,
    },
}

PROFESSION_BONUSES: Dict[str, Dict[str, int]] = {
    "banker": {"money": 600},
    "carpenter": {"ammo": 10, "health": 5},
    "farmer": {"food": 50, "health": 5},
    "doctor": {"health": 10},
}

WEATHER_OPTIONS: List[tuple[str, float]] = [
    ("Mild", 1.0),
    ("Warm", 1.05),
    ("Hot", 0.9),
    ("Cold", 0.85),
    ("Freezing", 0.7),
    ("Stormy", 0.6),
]

TERRAIN_OPTIONS: List[tuple[str, float]] = [
    ("Plains", 1.0),
    ("Hills", 0.85),
    ("Mountains", 0.7),
    ("Desert", 0.75),
    ("Forest", 0.9),
]

TRADE_ITEMS = {"food", "ammo"}


@dataclass
class TradeOffer:
    """Represents an offer at a trading post."""

    item: str
    quantity: int
    price: int  # Positive means you pay money, negative means you earn money

    def describe(self) -> str:
        direction = "buy" if self.price > 0 else "sell"
        cost = abs(self.price)
        if direction == "buy":
            return f"Buy {self.quantity} {self.item} for ${cost}"
        return f"Sell {self.quantity} {self.item} for ${cost}"


@dataclass
class GameState:
    """Mutable representation of the current game state."""

    player_name: str
    profession: str
    difficulty: Difficulty
    day: int = 1
    distance: int = 0
    food: int = 0
    ammo: int = 0
    money: int = 0
    health: int = 100
    pace: str = "steady"
    weather: str = "Mild"
    terrain: str = "Plains"
    alive: bool = True
    won: bool = False
    status: str = "On the trail"
    event_log: List[str] = field(default_factory=list)
    trade_available: bool = False

    def snapshot(self) -> Dict[str, object]:
        """Return a serialisable snapshot of the state for UI layers."""

        data = asdict(self)
        data["difficulty"] = self.difficulty.value
        data["event_log"] = list(self.event_log)
        return data


class Game:
    """High-level game controller."""

    TARGET_MILES = TARGET_MILES

    def __init__(
        self,
        player_name: str,
        profession: str,
        difficulty: Difficulty = Difficulty.NORMAL,
        *,
        rng: Optional[random.Random] = None,
    ) -> None:
        profession_key = profession.lower().strip()
        if profession_key not in PROFESSION_BONUSES:
            raise ValueError(
                f"Unknown profession '{profession}'. Choose from {', '.join(PROFESSION_BONUSES)}"
            )

        self.rng = rng or random.Random()
        self.difficulty = difficulty
        self.settings = DIFFICULTY_SETTINGS[difficulty]
        base_food = int(self.settings["food"])
        base_ammo = int(self.settings["ammo"])
        base_money = int(self.settings["money"])
        health = 100

        bonuses = PROFESSION_BONUSES[profession_key]
        food = base_food + bonuses.get("food", 0)
        ammo = base_ammo + bonuses.get("ammo", 0)
        money = base_money + bonuses.get("money", 0)
        health += bonuses.get("health", 0)

        self.state = GameState(
            player_name=player_name.strip() or "Pioneer",
            profession=profession_key,
            difficulty=difficulty,
            food=food,
            ammo=ammo,
            money=money,
            health=health,
        )

        self.event_chance = float(self.settings["event_chance"])
        self.max_days = int(self.settings["max_days"])
        self.is_over = False
        self.current_trade_offers: List[TradeOffer] = []
        # Determine starting conditions
        self._update_weather_and_terrain()
        self._maybe_prepare_trade_post(initial=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def available_professions() -> Iterable[str]:
        return PROFESSION_BONUSES.keys()

    @staticmethod
    def pace_options() -> Iterable[str]:
        return PACE_SPEEDS.keys()

    def available_actions(self) -> List[str]:
        actions = ["travel", "hunt", "rest"]
        if self.state.trade_available:
            actions.append("trade")
        return actions

    def get_trade_offers(self) -> List[TradeOffer]:
        return list(self.current_trade_offers)

    def perform_action(self, action: str, **kwargs) -> Dict[str, object]:
        if self.is_over:
            raise RuntimeError("The game has ended. Start a new game to continue playing.")

        action_key = action.lower().strip()
        if action_key not in {"travel", "hunt", "rest", "trade"}:
            raise ValueError(f"Unknown action '{action}'.")

        messages: List[str] = []
        self.state.event_log.clear()

        # Update environment for the new day
        self._update_weather_and_terrain()

        # Execute the selected action
        food_consumed = BASE_FOOD_PER_DAY
        if action_key == "travel":
            pace = kwargs.get("pace", self.state.pace)
            message, extra_food = self._travel(pace)
            messages.append(message)
            food_consumed += extra_food
        elif action_key == "hunt":
            message = self._hunt(kwargs.get("ammo_spent"))
            messages.append(message)
        elif action_key == "rest":
            message = self._rest()
            messages.append(message)
        elif action_key == "trade":
            message = self._trade(kwargs.get("offer_index"))
            messages.append(message)
            # Trading posts consume less food because you are stationary
            food_consumed = max(1, BASE_FOOD_PER_DAY - 2)

        self._consume_food(food_consumed)
        messages.extend(self._apply_random_event())
        self._end_of_day()
        messages.extend(self.state.event_log)
        snapshot = self.state.snapshot()
        snapshot["messages"] = messages
        snapshot["trade_offers"] = [offer.describe() for offer in self.current_trade_offers]

        if not self.is_over:
            self.state.day += 1
            self._maybe_prepare_trade_post()

        return snapshot

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def _travel(self, pace: str) -> tuple[str, int]:
        pace_key = pace.lower().strip()
        if pace_key not in PACE_SPEEDS:
            raise ValueError(f"Invalid pace '{pace}'. Choose from {', '.join(PACE_SPEEDS)}.")
        weather_mod = self._weather_modifier()
        terrain_mod = self._terrain_modifier()
        miles_float = PACE_SPEEDS[pace_key] * weather_mod * terrain_mod
        miles = max(5, int(round(miles_float)))
        self.state.distance += miles
        self.state.pace = pace_key
        message = (
            f"You travel {miles} miles at a {pace_key} pace through {self.state.weather.lower()} weather "
            f"and {self.state.terrain.lower()} terrain."
        )
        extra_food = int(math.ceil(BASE_FOOD_PER_DAY * max(0.0, PACE_FOOD_MULTIPLIER[pace_key] - 1.0)))
        return message, extra_food

    def _hunt(self, ammo_override: Optional[int]) -> str:
        ammo_cost = ammo_override if ammo_override is not None else 5
        if ammo_cost <= 0:
            raise ValueError("Ammo spent must be positive when hunting.")
        if self.state.ammo < ammo_cost:
            raise ValueError("Not enough ammunition to hunt.")
        self.state.ammo -= ammo_cost
        food_gained = self.rng.randint(25, 55) + ammo_cost * 2
        self.state.food += food_gained
        return (
            f"You spend {ammo_cost} ammo hunting and bring back {food_gained} lbs of food."
        )

    def _rest(self) -> str:
        health_gain = int(self.settings["rest_health"])
        previous_health = self.state.health
        self.state.health = min(100, self.state.health + health_gain)
        gained = self.state.health - previous_health
        if gained <= 0:
            return "You rest for the day but feel no better."
        return f"You rest for the day and recover {gained} health."

    def _trade(self, offer_index: Optional[int]) -> str:
        if not self.state.trade_available or not self.current_trade_offers:
            return "There is no trading post available today."
        if offer_index is None:
            self.state.trade_available = False
            self.current_trade_offers.clear()
            return "You browse the trading post but decide not to trade."
        if not isinstance(offer_index, int) or offer_index < 0 or offer_index >= len(self.current_trade_offers):
            raise ValueError("Invalid trade offer selection.")
        offer = self.current_trade_offers[offer_index]
        if offer.item not in TRADE_ITEMS:
            raise ValueError("Unsupported trade item.")
        if offer.price > 0:
            if self.state.money < offer.price:
                raise ValueError("Not enough money for that trade.")
            self.state.money -= offer.price
            self._add_resource(offer.item, offer.quantity)
            message = f"You buy {offer.quantity} {offer.item} for ${offer.price}."
        else:
            if self._get_resource(offer.item) < offer.quantity:
                raise ValueError("You do not have enough goods for that trade.")
            self._add_resource(offer.item, -offer.quantity)
            self.state.money += abs(offer.price)
            message = f"You sell {offer.quantity} {offer.item} for ${abs(offer.price)}."
        self.state.trade_available = False
        self.current_trade_offers.pop(offer_index)
        return message

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _consume_food(self, amount: int) -> None:
        self.state.food = max(0, self.state.food - max(0, amount))

    def _apply_random_event(self) -> List[str]:
        messages: List[str] = []
        if self.rng.random() > self.event_chance:
            return messages
        event_roll = self.rng.random()
        if event_roll < 0.2:
            loss = self.rng.randint(10, 30)
            self.state.food = max(0, self.state.food - loss)
            messages.append(f"Spoiled supplies force you to discard {loss} lbs of food.")
        elif event_roll < 0.4:
            injury = self.rng.randint(8, 15)
            self.state.health = max(0, self.state.health - injury)
            messages.append(f"A wagon accident injures you for {injury} health.")
        elif event_roll < 0.6:
            disease = self.rng.randint(12, 20)
            self.state.health = max(0, self.state.health - disease)
            messages.append(f"You fall ill and lose {disease} health fighting the sickness.")
        elif event_roll < 0.75:
            ammo_loss = min(self.state.ammo, self.rng.randint(4, 10))
            self.state.ammo -= ammo_loss
            messages.append(f"Bandits raid your camp and steal {ammo_loss} ammo.")
        elif event_roll < 0.9:
            found_food = self.rng.randint(20, 45)
            self.state.food += found_food
            messages.append(f"You find wild game and add {found_food} lbs of food to your stores.")
        else:
            self.state.distance = max(0, self.state.distance - 10)
            messages.append("You lose the trail and backtrack 10 miles.")
        return messages

    def _end_of_day(self) -> None:
        if self.state.food <= 0:
            penalty = int(self.settings["starvation_penalty"])
            self.state.health = max(0, self.state.health - penalty)
            self.state.event_log.append(
                "Without food your health deteriorates quickly."
            )
        if self.state.health <= 0:
            self.state.alive = False
            self.state.status = "You have perished on the trail."
            self.is_over = True
            return
        if self.state.distance >= TARGET_MILES:
            self.state.won = True
            self.state.status = "Congratulations! You have reached Oregon City."
            self.is_over = True
            return
        if self.state.day >= self.max_days:
            self.state.alive = False
            self.state.status = "Time has run out before you reached Oregon."
            self.is_over = True
            return
        self.state.status = "On the trail"

    def _update_weather_and_terrain(self) -> None:
        self.state.weather = self.rng.choices(
            [w for w, _ in WEATHER_OPTIONS],
            weights=[5, 4, 3, 3, 2, 2],
            k=1,
        )[0]
        self.state.terrain = self.rng.choices(
            [t for t, _ in TERRAIN_OPTIONS],
            weights=[5, 3, 2, 2, 3],
            k=1,
        )[0]

    def _weather_modifier(self) -> float:
        for weather, modifier in WEATHER_OPTIONS:
            if weather == self.state.weather:
                return modifier
        return 1.0

    def _terrain_modifier(self) -> float:
        for terrain, modifier in TERRAIN_OPTIONS:
            if terrain == self.state.terrain:
                return modifier
        return 1.0

    def _maybe_prepare_trade_post(self, *, initial: bool = False) -> None:
        probability = 0.25 if not initial else 0.3
        if self.rng.random() > probability:
            self.state.trade_available = False
            self.current_trade_offers.clear()
            return
        offers: List[TradeOffer] = []
        num_offers = self.rng.randint(1, 3)
        for _ in range(num_offers):
            if self.rng.random() < 0.5:
                item = "food"
                quantity = self.rng.randint(25, 60)
                price = max(10, int(quantity * self.rng.uniform(0.4, 0.7)))
            else:
                item = "ammo"
                quantity = self.rng.randint(6, 15)
                price = max(8, int(quantity * self.rng.uniform(1.5, 2.0)))
            if self.rng.random() < 0.25:
                price *= -1  # Trader wants to buy from you
            offers.append(TradeOffer(item=item, quantity=quantity, price=price))
        self.state.trade_available = True
        self.current_trade_offers = offers

    def _add_resource(self, item: str, amount: int) -> None:
        if item == "food":
            self.state.food = max(0, self.state.food + amount)
        elif item == "ammo":
            self.state.ammo = max(0, self.state.ammo + amount)
        else:
            raise ValueError("Unknown resource type.")

    def _get_resource(self, item: str) -> int:
        if item == "food":
            return self.state.food
        if item == "ammo":
            return self.state.ammo
        raise ValueError("Unknown resource type.")

