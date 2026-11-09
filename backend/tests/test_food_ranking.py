from app.db.food_ranking import CONTAINS, CORE_EXACT, EXACT, PREFIX, SIMILAR, WHOLE_WORD, WORD, Candidate, cores, match_tier, rank, words_score

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
    assert match_tier("Curd", ["Curd (plain whole milk)"]) == CORE_EXACT   # the name before its (...) note
    assert match_tier("curd", ["Dahi curd rice"]) == WHOLE_WORD
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


# ---------- Step 7.8a (D-083): found by the nutrition eval, with the real food names ----------

def food(key, name, category="dish", status="ready", syn=()):
    return Candidate(key, name, category, status, tuple(syn))


MILKS = [food("coconut_milk", "Coconut milk", "fat_oil"), food("curd", "Curd (plain whole milk)", "dairy"), food("milk_barfi", "Milk barfi", "sweet"),
         food("milk_whole", "Milk (whole)", "dairy"), food("milk_toned", "Milk (double toned / 1 %)", "dairy"), food("chaas", "Buttermilk (chaas)", "dairy"),
         food("oats", "Oats porridge (milk and water)", "dish")]


def test_cores_drop_the_note_and_split_on_slash():
    assert cores("Roti / chapati (no fat)") == ["roti", "chapati"]
    assert cores("Milk (double toned / 1 %)") == ["milk"]
    assert cores("Tofu") == ["tofu"] and cores("(only a note)") == []


def test_milk_lists_milk_before_coconut_milk_and_milk_sweets():
    ranked = keys("milk", MILKS)
    assert set(ranked[:2]) == {"milk_whole", "milk_toned"}
    assert ranked.index("milk_whole") < ranked.index("coconut_milk") and ranked.index("milk_whole") < ranked.index("milk_barfi")


def test_roti_lists_roti_before_white_bread():
    bread = food("bread_white", "White bread", "bread_white", syn=("double roti", "sandwich bread"))
    roti = food("roti", "Roti / chapati (no fat)", syn=("phulka",))
    roti_ghee = food("roti_ghee", "Roti / chapati with ghee or oil")
    assert keys("roti", [bread, roti_ghee, roti])[0] == "roti"


RICE_AND_DALS = [food("masoor", "Masoor dal (cooked plain)", "dish_dal"), food("urad", "Urad dal (cooked)", "dish_dal"), food("chana", "Chana dal (cooked)", "dish_dal"),
                 food("mixed", "Mixed dal (cooked)", "dish_dal"), food("brown", "Brown rice (cooked)", "dish_rice"), food("basmati", "Basmati rice (cooked)", "dish_rice"),
                 food("steamed", "Steamed white rice", "dish_rice", syn=("chawal", "bhaat")), food("pulao", "Plain pulao", "dish_rice")]


def test_cooked_rice_lists_rice_before_dals_that_only_say_cooked():
    ranked = keys("cooked rice", RICE_AND_DALS)
    assert set(ranked[:3]) == {"brown", "basmati", "steamed"}
    assert set(ranked[:2]) == {"basmati", "brown"}      # both words in the name: before the one-word match (steamed rice)
    assert ranked.index("steamed") < ranked.index("masoor")


def test_words_score_counts_whole_words_and_the_head_noun_double():
    assert words_score("cooked rice", ["Brown rice (cooked)"]) == 3
    assert words_score("cooked rice", ["Steamed white rice"]) == 2
    assert words_score("cooked rice", ["Masoor dal (cooked plain)"]) == 1
    assert words_score("cooked rice", ["Rice", "cooked"]) == 3                 # local names count too
    assert words_score("rice", ["Brown rice"]) == 0 and words_score("", ["x"]) == 0   # single-word queries are unchanged


def test_a_two_word_name_still_ranks_its_exact_match_first():
    assert keys("masoor dal", [food("t", "Toor dal (cooked)"), food("m", "Masoor dal (cooked plain)"), food("raw", "Masoor dal (raw)", "pulse")])[0] == "m"


def test_single_word_ranking_is_unchanged_for_the_old_cases():
    assert keys("chawal", [RAW_RICE, PARBOILED, STEAMED])[0] == "rice_cooked"
    assert keys("tofu", [Candidate("tofu_curry", "Tofu curry", "dish_curry_veg", "ready", ()), TOFU])[0] == "tofu"
