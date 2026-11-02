# PS 2 Ex 3

# Setup

## Environment

This project uses [Pixi](https://pixi.sh) for the environment. Install Pixi if you
do not have it yet, then from the repository root run:

```bash
pixi install
```

Activate the environment by running:

```bash
pixi shell
```

You can also run commands without activating the shell, for example
`pixi run python nba/data_loader.py ...`.

## Pre-commit

This repository uses pre-commit to run some checks before each commit. To install pre-commit, run:

```bash
pixi run pre-commit install
```

To run the checks manually, run:

```bash
pixi run pre-commit run --all-files
```

# Getting the data

1. create a Kaggle account: https://www.kaggle.com/
2. get API keys and user name
   - Go to your account, and click on your profile in the top right
   - Then click on "Settings"
   - Scroll down to the API section and click on "Create New Token"
   - Get your username and API key from there

We have written a data loader function for you in the "nba/data_loader.py".This allows you to
download the data with by running the script from the terminal. Run the following command in the
terminal being at the root of the repository.

```bash
pixi run python nba/data_loader.py -u "your_user_name" -k "your_api_key" -d "wyattowalsh/basketball"
```

Replace "your_user_name" and "your_api_key" with your username and API key. This creates a json
file at "~/.kaggle/kaggle.json" with your username and API key, which is used to authenticate your
account and download the data.

## Reproduce the analysis and attendance cleaning

After installing the environment and downloading the dataset, open
`analysis.ipynb` using the project's Pixi Python kernel and choose **Run All**.
The streak chart has an NBA-season dropdown and a team game-number axis.

`nba/wrangling.py:get_attendance` automatically excludes these two known
erroneous attendance observations before calculating annual extremes:

| Game ID | Game (1995) | Excluded attendance | Comparison value |
| --- | --- | ---: | ---: |
| 0029400853 | Jazz at Nets, 17 March | 200,049 | 20,049 |
| 0029401063 | Jazz at Timberwolves, 18 April | 144,442 | 14,442 |

The comparison figures are from Basketball Reference's
[March schedule](https://www.basketball-reference.com/leagues/NBA_1995_games-march.html)
and [April schedule](https://www.basketball-reference.com/leagues/NBA_1995_games-april.html).
The implausible extra-digit entries distort the annual maximum. We exclude
these observations rather than guess replacements. Exclusions match BOTH
the game ID and bad value: a corrected future source value is retained.
Other valid large attendances and recorded zeros are not removed.

The raw Kaggle database is kept unchanged for auditability. Cleaning is part
of the analysis pipeline, so a fresh fork/download followed by **Run All**
applies the same exclusions, without manual database edits. These games
remain available for streaks, scoring, and other non-attendance analyses.
