"""Reading every food with its synonyms and household units, for meal planning (foods are read-only reference data)."""

from psycopg import Connection

from app.calc.meal_pool import PoolFood

SQL = """
select f.id, f.key, f.name, f.category, f.diet_class, f.kcal_per_100g, f.protein_g_per_100g, f.carbs_g_per_100g,
       f.fat_g_per_100g, f.review_status,
       coalesce((select array_agg(s.synonym order by s.synonym) from public.food_synonyms s where s.food_id = f.id), '{}'),
       coalesce((select array_agg(u.unit || ':' || u.grams order by u.unit) from public.food_units u where u.food_id = f.id), '{}')
from public.foods f
where f.category is not null
order by f.name
"""


def list_pool_foods(conn: Connection) -> list[PoolFood]:
    foods = []
    for r in conn.execute(SQL).fetchall():
        units = tuple((u.split(":")[0], float(u.split(":")[1])) for u in r[11])
        foods.append(PoolFood(id=r[0], key=r[1], name=r[2], category=r[3], diet_class=r[4], kcal=float(r[5]),
                              protein_g=float(r[6]), carbs_g=float(r[7]), fat_g=float(r[8]), review_status=r[9],
                              synonyms=tuple(r[10]), units=units))
    return foods
