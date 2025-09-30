# Oregon Trail

A modern, text-based recreation of the classic Oregon Trail journey. Create a leader, pick a profession, and guide your party to Oregon City while balancing supplies, weather, and unexpected hardships.

## Features

- [x] Character creation with multiple professions that alter starting supplies.
- [x] Resource management for food, ammunition, health, and money.
- [x] Daily decision making with travel, hunting, rest, and trading options.
- [x] Random events including disease, injuries, bandits, and supply windfalls.
- [x] Dynamic weather and terrain modifiers that impact progress.
- [x] Trading posts with procedurally generated offers for buying and selling goods.
- [x] Three difficulty levels that tune resources, risk, and time limits.

## Getting Started

### Prerequisites

- Python 3.11+
- (Optional) [`pipx`](https://pipx.pypa.io/) or a virtual environment for isolation.

### Installation

```bash
pip install -e .
```

This installs the package in editable mode and exposes the `oregon-trail` console script.

### Usage

```bash
oregon-trail [--name NAME] [--profession banker|carpenter|farmer|doctor] \
             [--difficulty easy|normal|hard] [--seed SEED]
```

If arguments are omitted the CLI will interactively prompt you for the missing information. Each in-game day you can choose to travel, hunt, rest, or visit a trading post when available. Reach 2,000 miles before the time limit runs out to win.

### Running Tests

Install the development dependency and execute the tests with:

```bash
pip install pytest
pytest
```

## Project Structure

- `src/oregon_trail/game.py` – core simulation state machine and random events.
- `src/oregon_trail/cli.py` – command line interface harnessing the game engine.
- `tests/` – unit tests validating the primary game mechanics.

## License

TBD – License will be determined as the project evolves.

## Acknowledgments

- Inspired by the original Oregon Trail game by Don Rawitsch, Bill Heinemann, and Paul Dillenberger.
- Originally developed by MECC (Minnesota Educational Computing Consortium).
