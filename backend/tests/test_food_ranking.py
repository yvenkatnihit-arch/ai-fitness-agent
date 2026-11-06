from app.db.food_ranking import CONTAINS, EXACT, PREFIX, SIMILAR, WHOLE_WORD, WORD, Candidate, match_tier, rank

RAW_RICE = Candidate("rice_white", "Rice (white raw)", "cereal", "review", ("chawal", "arisi"))
PARBOILED = Candidate("rice_parboiled", "Parboiled rice (raw)", "cereal", "ready", ("ukda chawal",))
STEAMED = Candidate("rice_cooked", "Steamed white rice", "dish_rice", "ready", ("chawal", "bhaat"))
PULAO = Candidate("pulao_plain", "Plain pulao", "dish_rice", "review", ("pilau", "jeera rice"))
TOOR = Candidate("toor_dal", "Toor dal (split pigeon peas)", "pulse", "ready", ("arhar dal",))
CURD = Candidate("curd", "Curd (plain whole milk)", "dairy", "ready", ("dahi",))
TOFU = Candidate("tofu", "Tofu", "pulse", "ready", ())


def keys(query, candidates):
    return [c.key for c in rank(query, candidates)]


def test_match_tiers():
    assert match_tier("dahi", ["Curd", "dahi"]) == EXACT
    assert match_tier("Curd", ["Curd (plain whole milk)"]) == WHOLE_WORD
    assert match_tier("rice", ["Steamed white rice"]) == WHOLE_WORD
    assert match_tier("dal", ["dalda"]) == PREFIX
    assert match_tier("bir", ["Chicken biryani"]) == WORD
    assert match_tier("ice", ["Steamed white rice"]) == CONTAINS
    assert match_tier("toor dhal", ["Toor dal (split pigeon peas)"]) == SIMILAR


def test_chawal_puts_cooked_rice_before_raw_rice():
    # What someone logging lunch means by "chawal" is steamed rice, not raw grain.
    assert keys("chawal", [RAW_RICE, PARBOILED, STEAMED])[0] == "rice_cooked"


def test_rice_lists_rice_dishes_before_raw_rice():
    ranked = keys("rice", [RAW_RICE, PARBOILED, STEAMED, PULAO])
    assert ranked.index("rice_cooked") < ranked.index("rice_white")
    assert ranked.index("pulao_plain") < ranked.index("rice_parboiled")


def test_a_raw_staple_still_shows_when_it_is_the_only_match():
    assert keys("toor", [TOOR, CURD]) == ["toor_dal", "curd"]  # curd only as a weak fuzzy candidate


def test_real_matches_beat_similar_looking_ones():
    # even a raw staple that really contains the text beats a dish that only looks similar
    assert keys("arhar", [STEAMED, TOOR])[0] == "toor_dal"


def test_whole_word_beats_a_word_that_only_starts_the_same():
    # Real bug found in Step 4.6: "dal" listed pomegranate (dalimbe) and vanaspati (dalda) first.
    pomegranate = Candidate("pomegranate", "Pomegranate", "fruit", "ready", ("anar", "dalimbe"))
    vanaspati = Candidate("vanaspati", "Vanaspati (vegetable ghee)", "fat_oil", "ready", ("dalda",))
    dal = Candidate("masoor_dal_cooked", "Masoor dal (cooked plain)", "dish_dal", "ready", ())
    assert keys("dal", [pomegranate, vanaspati, dal])[0] == "masoor_dal_cooked"


def test_foods_eaten_as_is_are_not_pushed_down():
    tofu_dish = Candidate("tofu_curry", "Tofu curry", "dish_curry_veg", "ready", ())
    assert keys("tofu", [tofu_dish, TOFU])[0] == "tofu"  # exact name wins; tofu isn't a "raw staple"


def test_verified_values_come_before_ones_in_review():
    a = Candidate("a", "Rice dish", "dish_rice", "review", ())
    b = Candidate("b", "Rice dish", "dish_rice", "ready", ())
    assert keys("rice", [a, b]) == ["b", "a"]
