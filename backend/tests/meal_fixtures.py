"""A synthetic but realistic set of foods for the meal-week tests (not a test module)."""

from app.calc.meal_pool import PoolFood

_next_id = iter(range(1, 10_000))


def _food(key, name, category, diet, kcal, p, c, f, units=(), status="ready"):
    return PoolFood(id=next(_next_id), key=key, name=name, category=category, diet_class=diet, kcal=float(kcal),
                    protein_g=float(p), carbs_g=float(c), fat_g=float(f), review_status=status, units=tuple(units))


def make_foods() -> list[PoolFood]:
    foods = []
    for i in range(3):   # rice dishes (katori 150 g)
        foods.append(_food(f"rice_{i}", f"Rice {i}", "dish_rice", "vegan", 128 + 8 * i, 2.6 + 0.4 * i, 27 + i, 0.4 + 0.8 * i, [("katori", 150.0)]))
    for i in range(3):   # breads (piece 40 g)
        foods.append(_food(f"bread_{i}", f"Bread {i}", "dish_bread", "vegan", 260 + 15 * i, 8 + 0.3 * i, 44 + i, 4 + 2 * i, [("piece", 40.0)]))
    for i in range(8):   # dals and legume curries (katori 150 g)
        foods.append(_food(f"dal_{i}", f"Dal {i}", "dish_dal", "vegan", 105 + 5 * i, 6 + 0.4 * i, 13 + 0.5 * i, 2 + 0.3 * i, [("katori", 150.0)]))
    for i in range(8):   # vegetable dishes (katori 120 g)
        foods.append(_food(f"sabzi_{i}", f"Sabzi {i}", "dish_sabzi", "vegan", 80 + 5 * i, 2 + 0.2 * i, 8 + i, 4 + 0.4 * i, [("katori", 120.0)]))
    for i in range(8):   # breakfast mains (piece 45 g)
        foods.append(_food(f"brk_{i}", f"Breakfast {i}", "dish_breakfast", "vegan", 140 + 6 * i, 4 + 0.3 * i, 25 + i, 2 + 0.3 * i, [("piece", 45.0)]))
    for i in range(4):   # fruit (piece 120 g)
        foods.append(_food(f"fruit_{i}", f"Fruit {i}", "fruit", "vegan", 55 + 8 * i, 0.6, 13 + 2 * i, 0.2, [("piece", 120.0)]))
    foods += [
        _food("paneer", "Paneer", "dairy", "vegetarian", 265, 18, 3, 20, [("katori", 100.0)]),
        _food("curd", "Curd", "dairy", "vegetarian", 61, 3.5, 4.7, 3.3, [("katori", 100.0)]),
        _food("chaas", "Chaas", "dairy", "vegetarian", 40, 3.3, 4.8, 0.9, [("glass", 250.0)]),
        _food("milk_whole", "Milk", "dairy", "vegetarian", 61, 3.2, 4.8, 3.3, [("glass", 250.0)]),
        _food("raita", "Raita", "dish_side", "vegetarian", 65, 3, 5, 3.5, [("katori", 100.0)]),
        _food("boiled_potato", "Boiled potato", "dish_side", "vegan", 87, 1.9, 20, 0.1, [("piece", 150.0)]),
        _food("chana_boiled", "Boiled chana", "dish_side", "vegan", 130, 8.6, 17, 3, [("katori", 100.0)]),
        _food("moong_boiled", "Boiled moong", "dish_side", "vegan", 105, 7, 19, 0.4, [("katori", 100.0)]),
        _food("almonds", "Almonds", "nut_seed", "vegan", 579, 21, 22, 50),
        _food("peanuts", "Peanuts", "nut_seed", "vegan", 567, 26, 16, 49),
        _food("egg", "Egg", "egg", "eggetarian", 143, 12.6, 0.7, 9.5, [("piece", 50.0)]),
    ]
    return foods
