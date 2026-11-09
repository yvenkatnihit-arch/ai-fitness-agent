"""Scenarios for the workout plan eval (Step 7.7d, D-085): made-up users, never real data.

Each is a complete, valid set of inputs to the plan generator: split, level, goal, place, injuries, equipment (used at home), session
length, focus muscles and pace. The set is chosen to include the hard cases: several injuries at once, a home user with no equipment,
the long 5 and 6 day splits, focus areas, and short sessions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    split_key: str
    level: str
    goal: str
    place: str                      # "gym" or "home"
    injuries: frozenset[str] = frozenset()
    equipment: frozenset[str] = frozenset()
    minutes: int = 60
    focus: tuple[str, ...] = ()
    pace: str = "normal"


def S(name, split_key, level, goal, place, injuries=(), equipment=(), minutes=60, focus=(), pace="normal") -> Scenario:
    return Scenario(name, split_key, level, goal, place, frozenset(injuries), frozenset(equipment), minutes, tuple(focus), pace)


HOME_KIT = ("dumbbells", "bench", "resistance_bands", "pull_up_bar", "yoga_mat")

SCENARIOS: list[Scenario] = [
    S("ppl3 intermediate gym fat loss", "ppl_3", "intermediate", "fat_loss", "gym"),
    S("ppl3 beginner home, knee", "ppl_3", "beginner", "general_fitness", "home", ("knee",), HOME_KIT),
    S("upper/lower intermediate gym, shoulder", "upper_lower_4", "intermediate", "muscle_gain", "gym", ("shoulder",)),
    S("upper/lower advanced gym, focus glutes+chest", "upper_lower_4", "advanced", "muscle_gain", "gym", focus=("glutes", "chest"), minutes=90),
    S("full body 3 beginner home, no equipment, lower back", "full_body_3", "beginner", "fat_loss", "home", ("lower_back",), ()),
    S("full body 3 beginner gym, knee + lower back", "full_body_3", "beginner", "general_fitness", "gym", ("knee", "lower_back")),
    S("full body 2 intermediate home, bands and dumbbells, wrist", "full_body_2", "intermediate", "recomp", "home", ("wrist",), ("dumbbells", "resistance_bands")),
    S("5 day mixed advanced gym recomp 90 min", "upper_lower_ppl_5", "advanced", "recomp", "gym", minutes=90),
    S("bro split intermediate gym, shoulder", "bro_5", "intermediate", "muscle_gain", "gym", ("shoulder",), minutes=60),
    S("ppl6 advanced gym, focus back+chest", "ppl_6", "advanced", "muscle_gain", "gym", focus=("back", "chest"), minutes=90),
    S("arnold intermediate gym fat loss, elbow", "arnold_6", "intermediate", "fat_loss", "gym", ("elbow",)),
    S("full body 4 beginner home, no equipment, three injuries", "full_body_4", "beginner", "general_fitness", "home", ("knee", "shoulder", "lower_back"), ()),
    S("ppl3 beginner gym 30 minutes", "ppl_3", "beginner", "weight_gain", "gym", minutes=30),
    S("full body 1 intermediate gym slow pace", "full_body_1", "intermediate", "fat_loss", "gym", pace="slow"),
]
