"""Share-your-win card generator (SVG)."""

from __future__ import annotations

from html import escape


def generate_win_share_card(
    *,
    display_name: str,
    tournament_name: str,
    score: float,
    rank: int,
    brand_name: str = "Smart Pick Pro",
) -> dict:
    """Return an auto-generated SVG share card payload."""
    name = escape(str(display_name or "Player")[:32])
    t_name = escape(str(tournament_name or "Tournament")[:42])
    score_text = f"{float(score):.2f}"
    rank_text = str(max(1, int(rank or 1)))
    brand = escape(str(brand_name or "Smart Pick Pro")[:32])

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0B1220"/>
      <stop offset="100%" stop-color="#1E293B"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <text x="70" y="90" fill="#93C5FD" font-size="36" font-family="Arial, sans-serif">{brand}</text>
  <text x="70" y="180" fill="#F8FAFC" font-size="64" font-family="Arial, sans-serif" font-weight="700">🏆 {name} WON</text>
  <text x="70" y="250" fill="#E2E8F0" font-size="42" font-family="Arial, sans-serif">{t_name}</text>
  <rect x="70" y="310" rx="16" ry="16" width="520" height="190" fill="#0F172A" stroke="#334155"/>
  <text x="100" y="385" fill="#94A3B8" font-size="28" font-family="Arial, sans-serif">FINAL SCORE</text>
  <text x="100" y="455" fill="#34D399" font-size="62" font-family="Arial, sans-serif" font-weight="700">{score_text} FP</text>
  <text x="760" y="385" fill="#94A3B8" font-size="28" font-family="Arial, sans-serif">RANK</text>
  <text x="760" y="455" fill="#FBBF24" font-size="72" font-family="Arial, sans-serif" font-weight="700">#{rank_text}</text>
</svg>"""
    filename = f"smart-pick-win-{rank_text}.svg"
    return {"format": "svg", "filename": filename, "svg": svg}

