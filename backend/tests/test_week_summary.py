"""Step 8.4 (D-108): the 7-day logging summary, offline. Code sums and compares; the model only reads it out."""

from datetime import date

from app.calc.week_summary import DAYS, ON_TARGET_BAND, last_days, logged_days_only, remaining_today, summarize_week

TODAY = date(2026, 11, 11)                         # a Wednesday


def day(n_ago, kcal, protein=50.0):
    from datetime import timedelta
    return TODAY - timedelta(days=n_ago), {"kcal": kcal, "protein_g": protein, "carbs_g": 100.0, "fat_g": 30.0}


def test_the_week_is_the_last_seven_days_oldest_first_ending_today():
    days = last_days(TODAY)
    assert len(days) == DAYS == 7 and days[0] == date(2026, 11, 5) and days[-1] == TODAY


def test_an_empty_week_says_nothing_was_logged_and_has_no_averages():
    out = summarize_week({}, TODAY, 1800, 100)
    assert out["days_logged"] == 0 and len(out["days"]) == 7 and not any(d["logged"] for d in out["days"])
    assert "average_when_logged" not in out and "calorie_target" not in out


def test_days_without_a_log_are_not_counted_as_zero():
    out = summarize_week(dict([day(0, 1800), day(2, 1900)]), TODAY, 1800, 100)
    assert out["days_logged"] == 2
    assert out["average_when_logged"]["kcal"] == 1850.0                         # (1800 + 1900) / 2, not / 7
    not_logged = [d for d in out["days"] if not d["logged"]]
    assert len(not_logged) == 5 and all("kcal" not in d for d in not_logged)


def test_days_within_ten_percent_of_the_calorie_target_are_counted_by_code():
    out = summarize_week(dict([day(0, 1800), day(1, 1620), day(2, 1980), day(3, 1619), day(4, 1981)]), TODAY, 1800, 100)
    assert ON_TARGET_BAND == 0.10
    assert out["days_within_10_percent_of_calorie_target"] == 3                 # 1800, 1620 and 1980 are inside the band; 1619 and 1981 are just outside
    assert out["calorie_target"] == 1800


def test_average_percent_of_each_target_is_whole_and_computed_over_logged_days_only():
    out = summarize_week(dict([day(0, 900, protein=40), day(1, 2700, protein=80)]), TODAY, 1800, 120)
    assert out["average_percent_of_calorie_target"] == 100 and out["average_percent_of_protein_target"] == 50


def test_no_target_means_no_target_fields_but_the_days_are_still_reported():
    out = summarize_week(dict([day(0, 1800)]), TODAY, None, None)
    assert out["days_logged"] == 1 and "calorie_target" not in out and "days_within_10_percent_of_calorie_target" not in out


def test_a_user_who_must_not_see_numbers_is_told_only_which_days_they_logged():
    summary = summarize_week(dict([day(0, 1800), day(2, 1900)]), TODAY, 1800, 100)
    hidden = logged_days_only(summary["days"])
    assert hidden == {"days_logged": 2, "days_checked": 7, "logged_on": ["Monday", "Wednesday"]}
    assert not any(w in repr(hidden).lower() for w in ("kcal", "protein", "1800", "average"))


def test_what_is_left_today_is_the_whole_number_target_minus_what_was_eaten_and_goes_negative_when_over():
    eaten = {"kcal": 173.7, "protein_g": 6.3, "carbs_g": 34.2, "fat_g": 0.9}
    assert remaining_today(eaten, 1407.6, 116.4, 148.2, 38.7) == {"kcal": 1234.3, "protein_g": 109.7, "carbs_g": 113.8, "fat_g": 38.1}     # 1408 - 173.7, 116 - 6.3 ...
    over = remaining_today({"kcal": 1500.0, "protein_g": 120.0, "carbs_g": 100.0, "fat_g": 40.0}, 1408, 116, 148, 39)
    assert over["kcal"] == -92.0 and over["protein_g"] == -4.0 and over["carbs_g"] == 48.0 and over["fat_g"] == -1.0
