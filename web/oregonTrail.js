(function (global) {
  'use strict';

  const Difficulty = Object.freeze({
    EASY: 'easy',
    NORMAL: 'normal',
    HARD: 'hard',
  });

  const PACE_SPEEDS = Object.freeze({
    slow: 12,
    steady: 18,
    grueling: 24,
  });

  const PACE_FOOD_MULTIPLIER = Object.freeze({
    slow: 0.8,
    steady: 1.0,
    grueling: 1.35,
  });

  const BASE_FOOD_PER_DAY = 5;
  const TARGET_MILES = 2000;

  const DIFFICULTY_SETTINGS = Object.freeze({
    [Difficulty.EASY]: {
      food: 300,
      ammo: 70,
      money: 1400,
      eventChance: 0.18,
      restHealth: 15,
      starvationPenalty: 8,
      maxDays: 60,
    },
    [Difficulty.NORMAL]: {
      food: 240,
      ammo: 55,
      money: 1100,
      eventChance: 0.27,
      restHealth: 12,
      starvationPenalty: 10,
      maxDays: 55,
    },
    [Difficulty.HARD]: {
      food: 200,
      ammo: 45,
      money: 900,
      eventChance: 0.35,
      restHealth: 9,
      starvationPenalty: 12,
      maxDays: 50,
    },
  });

  const PROFESSION_BONUSES = Object.freeze({
    banker: Object.freeze({ money: 600 }),
    carpenter: Object.freeze({ ammo: 10, health: 5 }),
    farmer: Object.freeze({ food: 50, health: 5 }),
    doctor: Object.freeze({ health: 10 }),
  });

  const WEATHER_OPTIONS = Object.freeze([
    ['Mild', 1.0],
    ['Warm', 1.05],
    ['Hot', 0.9],
    ['Cold', 0.85],
    ['Freezing', 0.7],
    ['Stormy', 0.6],
  ]);

  const TERRAIN_OPTIONS = Object.freeze([
    ['Plains', 1.0],
    ['Hills', 0.85],
    ['Mountains', 0.7],
    ['Desert', 0.75],
    ['Forest', 0.9],
  ]);

  const TRADE_ITEMS = new Set(['food', 'ammo']);

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function randomInt(rng, min, max) {
    const low = Math.ceil(min);
    const high = Math.floor(max);
    return Math.floor(rng() * (high - low + 1)) + low;
  }

  function weightedChoice(rng, options, weights) {
    const total = weights.reduce((acc, weight) => acc + weight, 0);
    let roll = rng() * total;
    for (let index = 0; index < options.length; index += 1) {
      if (roll < weights[index]) {
        return options[index];
      }
      roll -= weights[index];
    }
    return options[options.length - 1];
  }

  class TradeOffer {
    constructor(item, quantity, price) {
      this.item = item;
      this.quantity = quantity;
      this.price = price;
    }

    describe() {
      const direction = this.price > 0 ? 'buy' : 'sell';
      const cost = Math.abs(this.price);
      if (direction === 'buy') {
        return `Buy ${this.quantity} ${this.item} for $${cost}`;
      }
      return `Sell ${this.quantity} ${this.item} for $${cost}`;
    }
  }

  class GameState {
    constructor({
      playerName,
      profession,
      difficulty,
      food,
      ammo,
      money,
      health,
    }) {
      this.playerName = playerName;
      this.profession = profession;
      this.difficulty = difficulty;
      this.day = 1;
      this.distance = 0;
      this.food = food;
      this.ammo = ammo;
      this.money = money;
      this.health = health;
      this.pace = 'steady';
      this.weather = 'Mild';
      this.terrain = 'Plains';
      this.alive = true;
      this.won = false;
      this.status = 'On the trail';
      this.eventLog = [];
      this.tradeAvailable = false;
    }

    snapshot() {
      return {
        playerName: this.playerName,
        profession: this.profession,
        difficulty: this.difficulty,
        day: this.day,
        distance: this.distance,
        food: this.food,
        ammo: this.ammo,
        money: this.money,
        health: this.health,
        pace: this.pace,
        weather: this.weather,
        terrain: this.terrain,
        alive: this.alive,
        won: this.won,
        status: this.status,
        eventLog: this.eventLog.slice(),
        tradeAvailable: this.tradeAvailable,
      };
    }
  }

  class Game {
    static TARGET_MILES = TARGET_MILES;

    constructor(playerName, profession, difficulty = Difficulty.NORMAL, options = {}) {
      const professionKey = String(profession || '').toLowerCase().trim();
      if (!Object.prototype.hasOwnProperty.call(PROFESSION_BONUSES, professionKey)) {
        const available = Object.keys(PROFESSION_BONUSES).join(', ');
        throw new Error(`Unknown profession '${profession}'. Choose from ${available}`);
      }

      this.random = typeof options.random === 'function' ? options.random : Math.random;

      this.difficulty = difficulty;
      this.settings = DIFFICULTY_SETTINGS[difficulty];
      if (!this.settings) {
        throw new Error(`Unknown difficulty '${difficulty}'.`);
      }

      const baseFood = this.settings.food;
      const baseAmmo = this.settings.ammo;
      const baseMoney = this.settings.money;
      let health = 100;

      const bonuses = PROFESSION_BONUSES[professionKey];
      const food = baseFood + (bonuses.food || 0);
      const ammo = baseAmmo + (bonuses.ammo || 0);
      const money = baseMoney + (bonuses.money || 0);
      health += bonuses.health || 0;

      this.state = new GameState({
        playerName: (playerName || '').trim() || 'Pioneer',
        profession: professionKey,
        difficulty,
        food,
        ammo,
        money,
        health,
      });

      this.eventChance = this.settings.eventChance;
      this.maxDays = this.settings.maxDays;
      this.isOver = false;
      this.currentTradeOffers = [];

      this._updateWeatherAndTerrain();
      this._maybePrepareTradePost({ initial: true });
    }

    static availableProfessions() {
      return Object.keys(PROFESSION_BONUSES);
    }

    static paceOptions() {
      return Object.keys(PACE_SPEEDS);
    }

    availableActions() {
      const actions = ['travel', 'hunt', 'rest'];
      if (this.state.tradeAvailable) {
        actions.push('trade');
      }
      return actions;
    }

    getTradeOffers() {
      return this.currentTradeOffers.slice();
    }

    performAction(action, params = {}) {
      if (this.isOver) {
        throw new Error('The game has ended. Start a new game to continue playing.');
      }

      const actionKey = String(action || '').toLowerCase().trim();
      if (!['travel', 'hunt', 'rest', 'trade'].includes(actionKey)) {
        throw new Error(`Unknown action '${action}'.`);
      }

      const messages = [];
      this.state.eventLog.length = 0;

      this._updateWeatherAndTerrain();

      let foodConsumed = BASE_FOOD_PER_DAY;
      if (actionKey === 'travel') {
        const pace = params.pace || this.state.pace;
        const [message, extraFood] = this._travel(pace);
        messages.push(message);
        foodConsumed += extraFood;
      } else if (actionKey === 'hunt') {
        messages.push(this._hunt(params.ammoSpent));
      } else if (actionKey === 'rest') {
        messages.push(this._rest());
      } else if (actionKey === 'trade') {
        messages.push(this._trade(params.offerIndex));
        foodConsumed = Math.max(1, BASE_FOOD_PER_DAY - 2);
      }

      this._consumeFood(foodConsumed);
      messages.push(...this._applyRandomEvent());
      this._endOfDay();
      messages.push(...this.state.eventLog);

      const snapshot = this.state.snapshot();
      snapshot.messages = messages;
      snapshot.tradeOffers = this.currentTradeOffers.map((offer) => offer.describe());

      if (!this.isOver) {
        this.state.day += 1;
        this._maybePrepareTradePost({ initial: false });
      }

      return snapshot;
    }

    _travel(pace) {
      const paceKey = String(pace || '').toLowerCase().trim();
      if (!Object.prototype.hasOwnProperty.call(PACE_SPEEDS, paceKey)) {
        const available = Object.keys(PACE_SPEEDS).join(', ');
        throw new Error(`Invalid pace '${pace}'. Choose from ${available}.`);
      }

      const milesFloat =
        PACE_SPEEDS[paceKey] * this._weatherModifier() * this._terrainModifier();
      const miles = Math.max(5, Math.round(milesFloat));
      this.state.distance += miles;
      this.state.pace = paceKey;
      const message = `You travel ${miles} miles at a ${paceKey} pace through ${this.state.weather.toLowerCase()} weather and ${this.state.terrain.toLowerCase()} terrain.`;
      const extraFood = Math.ceil(
        BASE_FOOD_PER_DAY * Math.max(0, (PACE_FOOD_MULTIPLIER[paceKey] || 1) - 1)
      );
      return [message, extraFood];
    }

    _hunt(ammoOverride) {
      const ammoCost = ammoOverride != null ? ammoOverride : 5;
      if (ammoCost <= 0) {
        throw new Error('Ammo spent must be positive when hunting.');
      }
      if (this.state.ammo < ammoCost) {
        throw new Error('Not enough ammunition to hunt.');
      }
      this.state.ammo -= ammoCost;
      const foodGained = randomInt(this.random, 25, 55) + ammoCost * 2;
      this.state.food += foodGained;
      return `You spend ${ammoCost} ammo hunting and bring back ${foodGained} lbs of food.`;
    }

    _rest() {
      const healthGain = this.settings.restHealth;
      const previousHealth = this.state.health;
      this.state.health = clamp(this.state.health + healthGain, 0, 100);
      const gained = this.state.health - previousHealth;
      if (gained <= 0) {
        return 'You rest for the day but feel no better.';
      }
      return `You rest for the day and recover ${gained} health.`;
    }

    _trade(offerIndex) {
      if (!this.state.tradeAvailable || this.currentTradeOffers.length === 0) {
        return 'There is no trading post available today.';
      }
      if (offerIndex == null) {
        this.state.tradeAvailable = false;
        this.currentTradeOffers = [];
        return 'You browse the trading post but decide not to trade.';
      }
      if (
        typeof offerIndex !== 'number' ||
        offerIndex < 0 ||
        offerIndex >= this.currentTradeOffers.length
      ) {
        throw new Error('Invalid trade offer selection.');
      }
      const offer = this.currentTradeOffers[offerIndex];
      if (!TRADE_ITEMS.has(offer.item)) {
        throw new Error('Unsupported trade item.');
      }
      let message;
      if (offer.price > 0) {
        if (this.state.money < offer.price) {
          throw new Error('Not enough money for that trade.');
        }
        this.state.money -= offer.price;
        this._addResource(offer.item, offer.quantity);
        message = `You buy ${offer.quantity} ${offer.item} for $${offer.price}.`;
      } else {
        if (this._getResource(offer.item) < offer.quantity) {
          throw new Error('You do not have enough goods for that trade.');
        }
        this._addResource(offer.item, -offer.quantity);
        this.state.money += Math.abs(offer.price);
        message = `You sell ${offer.quantity} ${offer.item} for $${Math.abs(offer.price)}.`;
      }
      this.state.tradeAvailable = false;
      this.currentTradeOffers.splice(offerIndex, 1);
      return message;
    }

    _consumeFood(amount) {
      this.state.food = Math.max(0, this.state.food - Math.max(0, amount));
    }

    _applyRandomEvent() {
      const messages = [];
      if (this.random() > this.eventChance) {
        return messages;
      }
      const eventRoll = this.random();
      if (eventRoll < 0.2) {
        const loss = randomInt(this.random, 10, 30);
        this.state.food = Math.max(0, this.state.food - loss);
        messages.push(`Spoiled supplies force you to discard ${loss} lbs of food.`);
      } else if (eventRoll < 0.4) {
        const injury = randomInt(this.random, 8, 15);
        this.state.health = Math.max(0, this.state.health - injury);
        messages.push(`A wagon accident injures you for ${injury} health.`);
      } else if (eventRoll < 0.6) {
        const disease = randomInt(this.random, 12, 20);
        this.state.health = Math.max(0, this.state.health - disease);
        messages.push(`You fall ill and lose ${disease} health fighting the sickness.`);
      } else if (eventRoll < 0.75) {
        const ammoLoss = Math.min(this.state.ammo, randomInt(this.random, 4, 10));
        this.state.ammo -= ammoLoss;
        messages.push(`Bandits raid your camp and steal ${ammoLoss} ammo.`);
      } else if (eventRoll < 0.9) {
        const foundFood = randomInt(this.random, 20, 45);
        this.state.food += foundFood;
        messages.push(`You find wild game and add ${foundFood} lbs of food to your stores.`);
      } else {
        this.state.distance = Math.max(0, this.state.distance - 10);
        messages.push('You lose the trail and backtrack 10 miles.');
      }
      return messages;
    }

    _endOfDay() {
      if (this.state.food <= 0) {
        const penalty = this.settings.starvationPenalty;
        this.state.health = Math.max(0, this.state.health - penalty);
        this.state.eventLog.push('Without food your health deteriorates quickly.');
      }
      if (this.state.health <= 0) {
        this.state.alive = false;
        this.state.status = 'You have perished on the trail.';
        this.isOver = true;
        return;
      }
      if (this.state.distance >= TARGET_MILES) {
        this.state.won = true;
        this.state.status = 'Congratulations! You have reached Oregon City.';
        this.isOver = true;
        return;
      }
      if (this.state.day >= this.maxDays) {
        this.state.alive = false;
        this.state.status = 'Time has run out before you reached Oregon.';
        this.isOver = true;
        return;
      }
      this.state.status = 'On the trail';
    }

    _updateWeatherAndTerrain() {
      this.state.weather = weightedChoice(
        this.random,
        WEATHER_OPTIONS.map((entry) => entry[0]),
        [5, 4, 3, 3, 2, 2]
      );
      this.state.terrain = weightedChoice(
        this.random,
        TERRAIN_OPTIONS.map((entry) => entry[0]),
        [5, 3, 2, 2, 3]
      );
    }

    _weatherModifier() {
      const match = WEATHER_OPTIONS.find((entry) => entry[0] === this.state.weather);
      return match ? match[1] : 1.0;
    }

    _terrainModifier() {
      const match = TERRAIN_OPTIONS.find((entry) => entry[0] === this.state.terrain);
      return match ? match[1] : 1.0;
    }

    _maybePrepareTradePost({ initial }) {
      const probability = initial ? 0.3 : 0.25;
      if (this.random() > probability) {
        this.state.tradeAvailable = false;
        this.currentTradeOffers = [];
        return;
      }

      const offers = [];
      const numOffers = randomInt(this.random, 1, 3);
      for (let index = 0; index < numOffers; index += 1) {
        let item;
        let quantity;
        let price;
        if (this.random() < 0.5) {
          item = 'food';
          quantity = randomInt(this.random, 25, 60);
          price = Math.max(10, Math.round(quantity * (0.4 + this.random() * 0.3)));
        } else {
          item = 'ammo';
          quantity = randomInt(this.random, 6, 15);
          price = Math.max(8, Math.round(quantity * (1.5 + this.random() * 0.5)));
        }
        if (this.random() < 0.25) {
          price *= -1;
        }
        offers.push(new TradeOffer(item, quantity, price));
      }
      this.state.tradeAvailable = true;
      this.currentTradeOffers = offers;
    }

    _addResource(item, amount) {
      if (item === 'food') {
        this.state.food = Math.max(0, this.state.food + amount);
      } else if (item === 'ammo') {
        this.state.ammo = Math.max(0, this.state.ammo + amount);
      } else {
        throw new Error('Unknown resource type.');
      }
    }

    _getResource(item) {
      if (item === 'food') {
        return this.state.food;
      }
      if (item === 'ammo') {
        return this.state.ammo;
      }
      throw new Error('Unknown resource type.');
    }
  }

  global.OregonTrail = {
    Difficulty,
    Game,
    TradeOffer,
  };
})(typeof window !== 'undefined' ? window : globalThis);
