# Card-Sharp

A blackjack basic-strategy trainer for macOS. Play simulated hands against the built-in dealer, and after every hand see exactly where your play deviated from perfect basic strategy — with the correct move for each decision, given the current rule set. Card-Sharp is offline practice software; it does not connect to a live dealer, casino, or gambling service.

## A real, finite shoe — not random cards

Card-Sharp builds a complete 52-card deck for every deck in the selected shoe (for example, **312 physical cards in a 6-deck game**), shuffles it, and removes each card as it is dealt. A card cannot appear again until the cut card is reached and the shoe is reshuffled before the following hand. No infinite random-card generator, no duplicate aces, no funny business.

Ships with editable presets for **Foxwoods**, **Mohegan Sun**, **Bally Twin River**, and nine additional Northeast casino/table profiles (best-estimate rules — verify at the table and tweak in the Rules dialog).

## Features

- **Real shoe simulation** — 6- or 8-deck shoe with cut-card penetration, matching each casino's format.
- **All standard actions** — Hit / Stand / Double / Split / Surrender, with buttons enabled only when the current rule set + hand allow the move.
- **Post-hand review** — every decision you made this hand vs. the basic-strategy recommendation, right/wrong flagged.
- **Session accuracy tracker** — running % of correct decisions this session.
- **Editable rules** — S17/H17, DAS, surrender (none/late/early), BJ payout (3:2 / 6:5), double restrictions, resplit/hit split aces, penetration. Save your own custom presets.
- **Persistent history** — SQLite log of every session, hand, and decision at `~/Library/Application Support/Card-Sharp/card_sharp.sqlite`.

## Casino presets (editable)

| Preset | Decks | Soft 17 | DAS | Surrender | BJ |
|--------|-------|---------|-----|-----------|----|
| Foxwoods — 6D Main Pit | 6 | S17 | Yes | None | 3:2 |
| Foxwoods — 8D Low Limit | 8 | H17 | Yes | None | 3:2 |
| Mohegan Sun — 6D | 6 | S17 | Yes | None | 3:2 |
| Mohegan Sun — 8D | 8 | H17 | Yes | None | 3:2 |
| Bally Twin River — 6D | 6 | H17 | Yes | Late | 3:2 |
| Bally Twin River — 8D | 8 | H17 | Yes | Late | 3:2 |
| Ocean Casino Resort — 6D S17 | 6 | S17 | Yes | Late | 3:2 |
| Ocean Casino Resort — 8D H17 | 8 | H17 | Yes | Late | 3:2 |
| Borgata — 8D Atlantic City | 8 | S17 | Yes | Late | 3:2 |
| Harrah's Atlantic City — 8D | 8 | S17 | Yes | Late | 3:2 |
| Caesars Atlantic City — 8D | 8 | S17 | Yes | Late | 3:2 |
| Tropicana Atlantic City — 8D H17 | 8 | H17 | Yes | Late | 3:2 |
| Hard Rock Atlantic City — 8D H17 | 8 | H17 | Yes | Late | 3:2 |
| Golden Nugget Atlantic City — 6D S17 | 6 | S17 | Yes | None | 3:2 |
| MGM Springfield — 6D S17 | 6 | S17 | Yes | Late | 3:2 |

> These are **best-estimate** rules that vary by pit, table minimum, and time. The Atlantic City profiles start from the common 8D/S17/DAS/late-surrender rule package, while Ocean publishes both 6D/8D and S17/H17 tables. The Rules dialog lets you correct any field and save it as a custom preset.

## Requirements

- macOS 10.15+
- Homebrew Python 3.11+ (`brew install python`). **Not** miniconda — py2app doesn't work with it.

## Run from source (development)

```bash
/usr/local/opt/python@3.14/bin/python3.14 -m venv venv
source venv/bin/activate
pip install pillow          # only for icon generation
python -m card_sharp.main
```

## Build .app

```bash
./build.sh
open dist/Card-Sharp.app
```

`build.sh` will:
1. Create a fresh venv with the correct Homebrew Python
2. Install `py2app` and `pillow`
3. Regenerate the icon
4. Run self-tests
5. Build the `.app` in `dist/`
6. Run `otool -L` on the binary so you can spot Homebrew-only dylibs

## Self-test

```bash
python -m card_sharp.self_test
```

Covers hand totals, shoe reshuffle at the cut card, one full round, blackjack payout, and correct basic-strategy answers for both S17/DAS and H17/late-surrender rule sets.

## Data locations

- Prefs: `~/Library/Application Support/Card-Sharp/prefs.json`
- Database: `~/Library/Application Support/Card-Sharp/card_sharp.sqlite`

## Version

0.6.0 — visual table refresh, Auto Deal, expanded casino presets, and portable app zip.
