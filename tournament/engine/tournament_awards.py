"""Tournament awards engine — 28 badges, career levels, and season awards.

Provides badge definitions, evaluation criteria, career-level mapping,
and season award computation (MVP, DPOY, GM of the Year, Clutch Award).
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Career Levels (LP → Title)
# ---------------------------------------------------------------------------

CAREER_LEVELS: list[dict[str, Any]] = [
    {"level": 1, "min_lp": 0, "title": "Rookie"},
    {"level": 5, "min_lp": 100, "title": "Contributor"},
    {"level": 10, "min_lp": 500, "title": "Veteran"},
    {"level": 15, "min_lp": 1000, "title": "All-Star"},
    {"level": 20, "min_lp": 2000, "title": "Legend"},
    {"level": 25, "min_lp": 3500, "title": "Hall of Famer"},
    {"level": 30, "min_lp": 5000, "title": "GOAT"},
]


def career_level_for_lp(lp: int) -> dict[str, Any]:
    """Return the career level dict for a given LP total."""
    lp = max(0, int(lp))
    result = CAREER_LEVELS[0]
    for entry in CAREER_LEVELS:
        if lp >= entry["min_lp"]:
            result = entry
    return dict(result)


def career_title_for_lp(lp: int) -> str:
    """Return just the title string for a given LP total."""
    return str(career_level_for_lp(lp).get("title", "Rookie"))


# ---------------------------------------------------------------------------
# 28 Badge Definitions
# ---------------------------------------------------------------------------

BADGE_DEFINITIONS: list[dict[str, Any]] = [
    # --- Win-based ---
    {
        "key": "first_blood",
        "name": "First Blood",
        "emoji": "🏅",
        "description": "Win your very first paid tournament",
        "category": "win",
    },
    {
        "key": "streak_master",
        "name": "Streak Master",
        "emoji": "🔥",
        "description": "Win 3+ paid tournaments in a row",
        "category": "win",
    },
    {
        "key": "triple_crown",
        "name": "Triple Crown",
        "emoji": "👑",
        "description": "Win Open, Pro, and Elite within 31 days",
        "category": "win",
    },
    {
        "key": "championship_winner",
        "name": "Championship Winner",
        "emoji": "🏆",
        "description": "Win a Championship Night tournament",
        "category": "win",
    },
    {
        "key": "repeat_champion",
        "name": "Repeat Champion",
        "emoji": "🏆🏆",
        "description": "Win 2+ Championship tournaments",
        "category": "win",
    },
    {
        "key": "dynasty",
        "name": "Dynasty",
        "emoji": "👑🏆",
        "description": "Win 5+ Championship tournaments",
        "category": "win",
    },
    # --- Roster construction ---
    {
        "key": "diamond_manager",
        "name": "Diamond Manager",
        "emoji": "💎",
        "description": "Win spending <$42K of $50K active cap",
        "category": "roster",
    },
    {
        "key": "underdog_king",
        "name": "Underdog King",
        "emoji": "🐕",
        "description": "Win with 0 Superstar-tier players",
        "category": "roster",
    },
    {
        "key": "galaxy_brain",
        "name": "Galaxy Brain",
        "emoji": "🧠",
        "description": "Win with <15% max player ownership across field",
        "category": "roster",
    },
    {
        "key": "goat_whisperer",
        "name": "GOAT Whisperer",
        "emoji": "🐐",
        "description": "Win 5 times with the same Legend",
        "category": "roster",
    },
    # --- Scoring ---
    {
        "key": "photo_finish",
        "name": "Photo Finish",
        "emoji": "📸",
        "description": "Win by less than 1.0 FP margin",
        "category": "scoring",
    },
    {
        "key": "five_by_five_club",
        "name": "5×5 Club",
        "emoji": "🖐️",
        "description": "Have a rostered player hit a 5×5 bonus",
        "category": "scoring",
    },
    {
        "key": "century_club",
        "name": "Century Club",
        "emoji": "💯",
        "description": "Score 100+ total FP in a single tournament",
        "category": "scoring",
    },
    {
        "key": "blowout_artist",
        "name": "Blowout Artist",
        "emoji": "💥",
        "description": "Win by 20+ FP margin over 2nd place",
        "category": "scoring",
    },
    # --- Career milestones ---
    {
        "key": "sniper",
        "name": "Sniper",
        "emoji": "🎯",
        "description": "Cash top-5 in 10+ consecutive paid tournaments",
        "category": "career",
    },
    {
        "key": "grinder",
        "name": "Grinder",
        "emoji": "⚙️",
        "description": "Enter 50+ total tournaments",
        "category": "career",
    },
    {
        "key": "money_maker",
        "name": "Money Maker",
        "emoji": "💰",
        "description": "Earn $1,000+ lifetime tournament winnings",
        "category": "career",
    },
    {
        "key": "lp_climber",
        "name": "LP Climber",
        "emoji": "🚀",
        "description": "Reach 500 lifetime LP",
        "category": "career",
    },
    {
        "key": "all_star_rank",
        "name": "All-Star Rank",
        "emoji": "⭐",
        "description": "Reach 1,000 lifetime LP (All-Star career level)",
        "category": "career",
    },
    {
        "key": "legend_rank",
        "name": "Legend Rank",
        "emoji": "🌟",
        "description": "Reach 2,000 lifetime LP (Legend career level)",
        "category": "career",
    },
    {
        "key": "goat_rank",
        "name": "GOAT Rank",
        "emoji": "🐐🏅",
        "description": "Reach 5,000 lifetime LP (GOAT career level)",
        "category": "career",
    },
    # --- Legend-related ---
    {
        "key": "legend_slayer",
        "name": "Legend Slayer",
        "emoji": "⚔️",
        "description": "Win without a legend when others had one",
        "category": "legend",
    },
    {
        "key": "legend_collector",
        "name": "Legend Collector",
        "emoji": "🃏",
        "description": "Roster 10 different legends across all tournaments",
        "category": "legend",
    },
    # --- Season ---
    {
        "key": "mvp_award",
        "name": "MVP Award",
        "emoji": "🏅",
        "description": "Win the season MVP award (highest average score)",
        "category": "season",
    },
    {
        "key": "dpoy_award",
        "name": "DPOY Award",
        "emoji": "🛡️",
        "description": "Win Defensive Player of the Year (most steals+blocks FP)",
        "category": "season",
    },
    {
        "key": "gm_of_the_year",
        "name": "GM of the Year",
        "emoji": "📋",
        "description": "Win GM of the Year (best salary efficiency)",
        "category": "season",
    },
    {
        "key": "clutch_award",
        "name": "Clutch Award",
        "emoji": "🔥🏀",
        "description": "Win Clutch Award (most wins by <3 FP margin)",
        "category": "season",
    },
    # --- Hall of Fame ---
    {
        "key": "hall_of_fame",
        "name": "Hall of Fame",
        "emoji": "🏛️",
        "description": "2,000+ LP, 5+ Championships, 50+ wins",
        "category": "hall_of_fame",
    },
]

# Quick lookup
BADGE_BY_KEY: dict[str, dict[str, Any]] = {b["key"]: b for b in BADGE_DEFINITIONS}


def get_badge_definition(badge_key: str) -> dict[str, Any] | None:
    """Return the badge definition for a given key, or None."""
    return BADGE_BY_KEY.get(str(badge_key or "").strip())


def list_all_badges() -> list[dict[str, Any]]:
    """Return a copy of all 28 badge definitions."""
    return [dict(b) for b in BADGE_DEFINITIONS]


def list_badges_by_category(category: str) -> list[dict[str, Any]]:
    """Return badges filtered by category."""
    cat = str(category or "").strip().lower()
    return [dict(b) for b in BADGE_DEFINITIONS if b.get("category") == cat]


# ---------------------------------------------------------------------------
# Badge Evaluation Helpers
# ---------------------------------------------------------------------------

def evaluate_career_badges(career_stats: dict) -> list[str]:
    """Evaluate which career-milestone badges a user qualifies for.

    Returns a list of badge keys the user has newly earned.
    Does NOT check whether the badge was already granted — that is the
    caller's responsibility.
    """
    earned: list[str] = []
    entries = int(career_stats.get("lifetime_entries", 0) or 0)
    wins = int(career_stats.get("lifetime_wins", 0) or 0)
    earnings = float(career_stats.get("lifetime_earnings", 0.0) or 0.0)
    lp = int(career_stats.get("lifetime_lp", 0) or 0)
    championships = int(career_stats.get("championship_wins", 0) or 0)

    if entries >= 50:
        earned.append("grinder")
    if earnings >= 1000.0:
        earned.append("money_maker")
    if lp >= 500:
        earned.append("lp_climber")
    if lp >= 1000:
        earned.append("all_star_rank")
    if lp >= 2000:
        earned.append("legend_rank")
    if lp >= 5000:
        earned.append("goat_rank")
    if championships >= 2:
        earned.append("repeat_champion")
    if championships >= 5:
        earned.append("dynasty")

    # Hall of Fame: 2,000+ LP + 5 Championships + 50 wins
    if lp >= 2000 and championships >= 5 and wins >= 50:
        earned.append("hall_of_fame")

    return earned


def evaluate_tournament_result_badges(
    *,
    rank: int,
    total_score: float,
    margin_over_second: float,
    salary_used: int,
    has_superstar: bool,
    has_legend: bool,
    field_has_legend: bool,
    has_five_by_five: bool,
    prior_wins: int,
    win_streak: int,
    court_tier: str,
    is_paid: bool,
) -> list[str]:
    """Evaluate post-tournament badges for a single entry.

    Returns badge keys that the entry triggered. Caller must check for
    duplicates before persisting.
    """
    earned: list[str] = []

    if rank == 1:
        # First Blood — first paid win
        if is_paid and prior_wins == 0:
            earned.append("first_blood")

        # Streak Master — 3+ consecutive paid wins
        if is_paid and win_streak >= 3:
            earned.append("streak_master")

        # Diamond Manager — win spending <$42K active cap
        if salary_used < 42000:
            earned.append("diamond_manager")

        # Underdog King — no superstars
        if not has_superstar:
            earned.append("underdog_king")

        # Photo Finish — margin < 1.0
        if 0 < margin_over_second < 1.0:
            earned.append("photo_finish")

        # Blowout Artist — margin >= 20
        if margin_over_second >= 20.0:
            earned.append("blowout_artist")

        # Legend Slayer
        if not has_legend and field_has_legend:
            earned.append("legend_slayer")

        # Championship Winner
        if str(court_tier).strip() == "Championship":
            earned.append("championship_winner")

    # Century Club — anyone with 100+ FP
    if total_score >= 100.0:
        earned.append("century_club")

    # 5×5 Club
    if has_five_by_five:
        earned.append("five_by_five_club")

    return earned


# ---------------------------------------------------------------------------
# Season Awards Definitions
# ---------------------------------------------------------------------------

SEASON_AWARDS: list[dict[str, str]] = [
    {"key": "mvp_award", "name": "MVP", "description": "Highest average tournament score (3+ entries)"},
    {"key": "dpoy_award", "name": "DPOY", "description": "Highest steals+blocks fantasy points across tournaments"},
    {"key": "gm_of_the_year", "name": "GM of the Year", "description": "Best salary efficiency (score per $1K salary spent)"},
    {"key": "clutch_award", "name": "Clutch Award", "description": "Most wins by <3 FP margin"},
]


# ---------------------------------------------------------------------------
# Hall of Fame Criteria
# ---------------------------------------------------------------------------

HOF_CRITERIA = {
    "min_lp": 2000,
    "min_championships": 5,
    "min_wins": 50,
}


def qualifies_for_hall_of_fame(
    *,
    lifetime_lp: int,
    championship_wins: int,
    lifetime_wins: int,
) -> bool:
    """Check if a player meets Hall of Fame requirements."""
    return (
        int(lifetime_lp) >= HOF_CRITERIA["min_lp"]
        and int(championship_wins) >= HOF_CRITERIA["min_championships"]
        and int(lifetime_wins) >= HOF_CRITERIA["min_wins"]
    )
