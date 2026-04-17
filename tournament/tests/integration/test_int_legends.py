"""Integration tests for tournament.legends — static legend pool."""

from datetime import date

from tournament.legends import LEGEND_PROFILES, get_active_monthly_legends, get_monthly_legends


class TestLegendProfiles:
    def test_count(self):
        assert len(LEGEND_PROFILES) == 20

    def test_jordan_first(self):
        assert LEGEND_PROFILES[0]["player_id"] == "L001"
        assert "Jordan" in LEGEND_PROFILES[0]["player_name"]

    def test_all_have_required_keys(self):
        for legend in LEGEND_PROFILES:
            assert "player_id" in legend
            assert "player_name" in legend
            assert "position" in legend
            assert "overall_rating" in legend
            assert "salary" in legend
            assert "archetype" in legend

    def test_unique_ids(self):
        ids = [l["player_id"] for l in LEGEND_PROFILES]
        assert len(ids) == len(set(ids))


class TestGetMonthlyLegends:
    def test_month_1_returns_all(self):
        legends = get_monthly_legends(1)
        assert len(legends) == 20

    def test_other_months_return_8(self):
        for month in (2, 3, 6, 12):
            legends = get_monthly_legends(month)
            assert len(legends) == 8

    def test_jordan_and_lebron_always_included(self):
        for month in range(1, 13):
            legends = get_monthly_legends(month)
            ids = {l["player_id"] for l in legends}
            assert "L001" in ids  # Jordan
            assert "L002" in ids  # LeBron

    def test_returns_deep_copies(self):
        legends = get_monthly_legends(3)
        legends[0]["player_name"] = "MODIFIED"
        fresh = get_monthly_legends(3)
        assert fresh[0]["player_name"] != "MODIFIED"

    def test_get_active_monthly_legends_uses_date(self):
        legends = get_active_monthly_legends(date(2026, 1, 5))
        assert len(legends) == 20
