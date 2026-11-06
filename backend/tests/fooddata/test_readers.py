"""Both readers, on tiny fake files in each source's real layout (no downloads needed)."""

import zipfile

import pytest
from openpyxl import Workbook

from fooddata.cofid import parse_value, read_cofid
from fooddata.usda import read_sr_legacy

# --- USDA: three linked CSV tables inside a zip ---

NUTRIENTS = """id,name,unit_name,nutrient_nbr,rank
1003,Protein,G,203,600
1004,Total lipid (fat),G,204,800
1005,"Carbohydrate, by difference",G,205,1110
1008,Energy,KCAL,208,300
1079,"Fiber, total dietary",G,291,1200
1018,"Alcohol, ethyl",G,221,18200
"""
FOODS = """fdc_id,data_type,description,food_category_id,publication_date
172420,sr_legacy_food,"Lentils, raw",16,2019-04-01
999,sr_legacy_food,"Mystery food",16,2019-04-01
"""
CATEGORIES = """id,code,description
16,1600,Legumes and Legume Products
"""
FOOD_NUTRIENTS = """id,fdc_id,nutrient_id,amount
1,172420,1008,352
2,172420,1003,24.63
3,172420,1004,1.06
4,172420,1005,63.35
5,172420,1079,10.7
6,999,1003,5
"""


def usda_zip(tmp_path, nutrients=NUTRIENTS):
    path = tmp_path / "sr.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in [("nutrient.csv", nutrients), ("food.csv", FOODS),
                           ("food_category.csv", CATEGORIES), ("food_nutrient.csv", FOOD_NUTRIENTS)]:
            archive.writestr(f"FoodData_Central_sr_legacy_food_csv_2018-04/{name}", text)
    return path


def test_usda_reader_joins_the_three_tables(tmp_path):
    lentils, mystery = read_sr_legacy(usda_zip(tmp_path))
    assert (lentils.source_id, lentils.name, lentils.category) == ("172420", "Lentils, raw", "Legumes and Legume Products")
    assert (lentils.kcal, lentils.protein_g, lentils.fat_g, lentils.carbs_g, lentils.fiber_g) == (352, 24.63, 1.06, 63.35, 10.7)
    assert lentils.carb_basis == "by_difference"
    assert mystery.kcal is None and mystery.protein_g == 5  # missing stays missing (None), never 0


def test_usda_reader_refuses_if_a_nutrient_definition_is_missing(tmp_path):
    without_energy = "\n".join(line for line in NUTRIENTS.splitlines() if "Energy" not in line) + "\n"
    with pytest.raises(ValueError, match="Energy"):
        read_sr_legacy(usda_zip(tmp_path, without_energy))


# --- CoFID: Excel sheet with 3 header rows and text values ---

HEADER = ["Food Code", "Food Name", "Description", "Group", "Water (g)", "Protein (g)", "Fat (g)",
          "Carbohydrate (g)", "Energy (kcal) (kcal)", "Alcohol (g)", "NSP (g)", "AOAC fibre (g)",
          "Starch (g)", "Oligosaccharide (g)", "Total sugars (g)", "Glucose (g)", "Fructose (g)", "Galactose (g)",
          "Sucrose (g)", "Maltose (g)", "Lactose (g)"]
CODES = [None, None, None, None, "WATER", "PROT", "FAT", "CHO", "KCALS", "ALCO", "ENGFIB", "AOACFIB",
         "STAR", "OLIGO", "TOTSUG", "GLUC", "FRUCT", "GALACT", "SUCR", "MALT", "LACT"]
#               starch  oligo  sugars gluc  fruct  galact sucr   malt   lact
DHAL_PARTS = ["14.2", None, "2.2", "0.3", "0.2", "0.0", "1.6", "0.1", "0.0"]
SPICE_PARTS = ["40.0", None, "10.1", "N", "1.0", "0.0", "5.0", "Tr", "0.0"]


def cofid_xlsx(tmp_path, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "1.3 Proximates"
    sheet.append(HEADER)
    sheet.append(CODES)
    sheet.append(["descriptions..."] + [None] * (len(HEADER) - 1))
    for row in rows:
        sheet.append(row)
    path = tmp_path / "cofid.xlsx"
    workbook.save(path)
    return path


def test_cofid_reader_handles_trace_and_not_measured(tmp_path):
    path = cofid_xlsx(tmp_path, [
        ["17-500", "Dhal, masoor, homemade", "", "DG", "75", "7.4", "1.4", "16.4", "104", None, "N", "3.9", *DHAL_PARTS],
        ["17-501", "Spice, unknown", "", "WH", "10", "Tr", "N", "50.1", "N", None, "4.0", None, *SPICE_PARTS],
    ])
    dhal, spice = read_cofid(path)
    assert (dhal.source_id, dhal.category, dhal.kcal, dhal.protein_g, dhal.fiber_g) == ("17-500", "DG", 104, 7.4, 3.9)
    assert dhal.carb_basis == "available"
    assert spice.protein_g == 0.0      # "Tr" = trace -> 0
    assert spice.fat_g is None          # "N" = not measured -> unknown, NOT 0
    assert spice.kcal is None
    assert spice.fiber_g == 4.0         # no AOAC value -> falls back to NSP

    # Carbohydrate breakdown for the D-038 conversion
    assert dhal.carb_parts.starch_g == 14.2
    assert dhal.carb_parts.mono_sugars_g == pytest.approx(0.5)   # glucose + fructose + galactose
    assert dhal.carb_parts.di_sugars_g == pytest.approx(1.7)     # sucrose + maltose + lactose
    assert spice.carb_parts.mono_sugars_g is None                 # glucose "N" -> the sum is unknown, not partial
    assert spice.carb_parts.di_sugars_g == pytest.approx(5.0)     # maltose "Tr" -> 0


@pytest.mark.parametrize(("cell", "expected"), [("12.5", 12.5), ("Tr", 0.0), ("tr", 0.0), ("N", None),
                                                 ("", None), (None, None), (7, 7.0)])
def test_parse_value(cell, expected):
    assert parse_value(cell) == expected
