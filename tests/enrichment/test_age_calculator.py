from datetime import datetime, timezone

from dep_age.enrichment.age_calculator import calculate_age, calculate_all_ages, format_age
from dep_age.models import Dependency, Ecosystem


class TestAgeCalculator:
    def test_calculate_age(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
            published_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = calculate_age(dep, now=now)
        assert result.age_days == 365

    def test_calculate_age_no_date(self):
        dep = Dependency(name="test", ecosystem=Ecosystem.NPM, current_version="1.0.0")
        result = calculate_age(dep)
        assert result.age_days is None

    def test_calculate_all_ages(self):
        deps = [
            Dependency(
                name="a",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                published_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
            ),
            Dependency(
                name="b",
                ecosystem=Ecosystem.NPM,
                current_version="2.0.0",
                published_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        now = datetime(2024, 6, 1, tzinfo=timezone.utc)
        results = calculate_all_ages(deps, now=now)
        assert results[0].age_days == 366  # 2023 to 2024 leap year
        assert results[1].age_days is not None
        assert results[1].age_days > results[0].age_days


class TestFormatAge:
    def test_format_days(self):
        assert format_age(5) == "5d"
        assert format_age(29) == "29d"

    def test_format_months(self):
        assert format_age(60) == "2m"
        assert format_age(180) == "6m"

    def test_format_years(self):
        assert format_age(400) == "1y 1m"
        assert format_age(730) == "2y"
        assert format_age(365) == "1y"

    def test_format_unknown(self):
        assert format_age(None) == "unknown"
