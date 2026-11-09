"""Eval cases for the nutrition specialist (Step 7.7c, D-082): (question, kind).

kind "lookup" = a plain nutrition question; "amount" = asks about a quantity (the specialist must NOT calculate: it gives per-100 g
values and unit weights as the tool returns them); "maybe_absent" = a food that may not be in our table (when the search finds
nothing, the answer must say so and contain no invented numbers).
"""

Case = tuple[str, str]

CASES: list[Case] = [
    ("How much protein is in paneer?", "lookup"),
    ("calories in a roti", "lookup"),
    ("is toor dal high in carbs?", "lookup"),
    ("what are the macros of a boiled egg", "lookup"),
    ("how much fat is in ghee", "lookup"),
    ("how many calories does idli have", "lookup"),
    ("protein in a glass of milk", "lookup"),
    ("is banana high in sugar or calories", "lookup"),
    ("how many grams is one katori of cooked rice", "lookup"),
    ("how many calories are in 150 g of paneer", "amount"),
    ("how much protein do 3 rotis give me", "amount"),
    ("calories in two boiled eggs", "amount"),
    ("how much protein is in 200 ml of milk", "amount"),
    ("I ate 250 g of cooked rice, how many carbs is that", "amount"),
    # added AFTER the prompt was tightened on the roti failure: unseen "one piece / one portion" questions (held-out check)
    ("calories in one idli", "amount"),
    ("how much protein is in one piece of paneer", "amount"),
    ("how many carbs in one banana", "amount"),
    ("calories in a katori of dal", "amount"),
    ("how much fat in a tablespoon of ghee", "amount"),
    ("protein in one egg", "amount"),
    ("nutrition of sushi", "maybe_absent"),
    ("calories in tiramisu", "maybe_absent"),
    ("protein in dragon fruit smoothie bowl", "maybe_absent"),
    ("macros of a kale and quinoa power salad", "maybe_absent"),
]
