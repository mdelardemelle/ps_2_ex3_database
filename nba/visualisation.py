"""Plot prepared NBA data without querying or changing the database."""

import base64
import html
import io
import uuid
from collections.abc import Sequence
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.figure import Figure


def _style(ax: Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="0.92")
    ax.set_axisbelow(True)


def streak_path(group: pd.DataFrame) -> tuple[list[Any], list[float]]:
    """Insert vertical zero resets and gaps between completed streaks.

    Leave the final observed run open: its end is not known yet.
    Work on individual games to keep full-history rendering inexpensive.
    """
    dates: list[Any] = []
    values: list[float] = []
    records = list(zip(group["game_number"], group["streak"]))
    for index, (date, raw_value) in enumerate(records):
        if pd.isna(raw_value):
            dates.append(float("nan"))
            values.append(float("nan"))
            continue
        value = float(raw_value)
        if abs(value) == 1:
            dates.append(date)
            values.append(0.0)
        dates.append(date)
        values.append(value)
        if index < len(records) - 1:
            following = records[index + 1][1]
            if pd.isna(following) or value * float(following) < 0:
                dates.extend([date, float("nan")])
                values.extend([0.0, float("nan")])
    dates.append(float("nan"))
    values.append(float("nan"))
    return dates, values


def plot_streaks(
    data: pd.DataFrame,
    team_ids: Sequence[str] | None = None,
    season_start: int | None = None,
) -> Figure:
    """Plot a single season using each team's recorded game number."""
    if season_start is None:
        season_start = int(data["season_start"].max())
    data = data[data["season_start"] == season_start]
    if team_ids is not None:
        data = data[data["team_id"].isin(team_ids)]
    if data.empty:
        raise ValueError("No streak data for the selected teams.")
    fig, ax = plt.subplots(figsize=(13, 7))
    groups = list(data.groupby("team_id", sort=False))
    palette = plt.get_cmap("turbo")
    for index, (_, group) in enumerate(groups):
        dates, values = streak_path(group)
        ax.plot(
            dates,
            values,
            lw=0.7,
            alpha=0.65,
            color=palette(index / max(1, len(groups) - 1)),
            label=str(group["team_name"].iloc[-1]),
        )
    ax.axhline(0, color="0.25", lw=0.7)
    ax.set(
        title=(
            f"Winning (+) and losing (-) streaks: "
            f"{season_start}–{str(season_start + 1)[-2:]}"
        ),
        xlabel="Team game number within the regular season",
        ylabel="Consecutive games",
    )
    ax.set_xlim(0, int(data["game_number"].max()) + 1)
    _style(ax)
    ax.legend(
        bbox_to_anchor=(1.01, 1),
        loc="upper left",
        ncol=2,
        fontsize=6.5,
        frameon=False,
        title="Latest recorded team name",
    )
    fig.tight_layout()
    return fig


def streak_season_selector(data: pd.DataFrame) -> str:
    """Return a self-contained HTML year dropdown; no widget dependency.

    Every season is pre-rendered, so selecting a year needs no live kernel.
    Only seasons represented in the source are offered.
    """
    if data.empty:
        raise ValueError("No streak data available.")
    image_id = "streak-" + uuid.uuid4().hex
    options = []
    first_image = ""
    for season in sorted(data["season_start"].unique(), reverse=True):
        figure = plot_streaks(data, season_start=int(season))
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=85)
        plt.close(figure)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        image = "data:image/png;base64," + encoded
        if not first_image:
            first_image = image
        label = f"{season}–{str(season + 1)[-2:]}"
        options.append(
            f'<option data-image="{image}">{html.escape(label)}</option>'
        )
    handler = (
        f"document.getElementById('{image_id}').src="
        "this.options[this.selectedIndex].getAttribute('data-image')"
    )
    return (
        '<div><label>NBA season: <select aria-label="NBA season" '
        f'onchange="{handler}">' + "".join(options) + "</select></label>"
        f'<img id="{image_id}" src="{first_image}" '
        'alt="Season winning and losing streaks" '
        'style="display:block;max-width:100%;height:auto"></div>'
    )


def plot_attendance(data: pd.DataFrame) -> Figure:
    """Plot recorded annual extremes without silently dropping outliers."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for column, label, colour in [
        ("maximum", "Maximum", "#0072B2"),
        ("minimum", "Minimum", "#D55E00"),
    ]:
        ax.plot(data["year"], data[column], label=label, color=colour)
    ax.set(
        title="Recorded game attendance: annual extremes",
        xlabel="Calendar year",
        ylabel="Attendance (people)",
    )
    ax.set_ylim(bottom=0)
    ax.ticklabel_format(axis="y", style="plain")
    _style(ax)
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def plot_scoring(data: pd.DataFrame) -> Figure:
    """Separate full-game and quarter scales, with aligned year axes."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(data["year"], data["game_points"], color="#0072B2")
    axes[0].set(
        title="Average combined points per game (including overtime)",
        ylabel="Points, both teams",
    )
    for q, colour in zip(
        range(1, 5), ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]
    ):
        axes[1].plot(data["year"], data[f"q{q}"], label=f"Q{q}", color=colour)
    axes[1].set(
        title="Average combined points by quarter",
        xlabel="Calendar year",
        ylabel="Points, both teams",
    )
    axes[1].legend(frameon=False, ncol=4)
    for ax in axes:
        _style(ax)
    fig.tight_layout()
    return fig


def animate_new_player_heights(
    data: pd.DataFrame,
) -> tuple[Figure, FuncAnimation]:
    """Animate debut cohorts with a background year and fixed 5 cm bins.

    Uses Matplotlib's built-in JavaScript HTML player; no video encoder.
    """
    if data.empty:
        raise ValueError("No valid player heights available.")
    years = sorted(data["year"].unique().tolist())
    bins = np.arange(
        5 * np.floor(data["height_cm"].min() / 5),
        5 * np.floor(data["height_cm"].max() / 5) + 10,
        5,
    )
    percentages = []
    sizes = []
    for year in years:
        heights = data.loc[data["year"] == year, "height_cm"]
        percentages.append(
            np.histogram(heights, bins=bins)[0] * 100.0 / len(heights)
        )
        sizes.append(len(heights))
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=80)
    background = ax.text(
        0.5,
        0.5,
        "",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=100,
        color="0.9",
        zorder=0,
    )
    bars = ax.bar(
        bins[:-1],
        percentages[0],
        width=5,
        align="edge",
        color="#0072B2",
        alpha=0.7,
        edgecolor="white",
    )
    ax.set(
        xlim=(bins[0], bins[-1]),
        ylim=(0, 1.1 * max(float(v.max()) for v in percentages)),
        xlabel="Recorded height (cm)",
        ylabel="Percentage of newcomers",
    )
    _style(ax)
    ax.grid(False)

    def update(frame: int) -> tuple[Artist, ...]:
        for bar, value in zip(bars, percentages[frame]):
            bar.set_height(float(value))
        background.set_text(str(years[frame]))
        ax.set_title(f"New NBA players: {years[frame]} (n={sizes[frame]})")
        return (*bars, background)

    update(0)
    fig.tight_layout()
    animation = FuncAnimation(
        fig, update, frames=len(years), interval=350, repeat=True
    )
    return fig, animation
