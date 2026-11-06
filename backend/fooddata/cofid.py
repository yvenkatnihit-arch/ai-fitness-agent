"""Read UK CoFID 2021 (Excel, sheet "1.3 Proximates") into FoodRecords.

The sheet has 3 header rows: long names, short codes (PROT, FAT, CHO, KCALS...), descriptions.
We find columns by the short CODE, so a reordered sheet still reads correctly.
Cell values are text with special markers:
  "Tr" = trace (present in a tiny amount)  -> 0.0
  "N"  = present but NOT measured          -> None (unknown, never 0)
  empty                                    -> None
"""

from pathlib import Path

from openpyxl import load_workbook

from fooddata.records import CarbParts, FoodRecord

SOURCE_KEY = "uk_cofid"
SHEET = "1.3 Proximates"
CODES = {"kcal": "KCALS", "protein_g": "PROT", "fat_g": "FAT", "carbs_g": "CHO", "alcohol_g": "ALCO"}
FIBRE_CODES = ("AOACFIB", "ENGFIB")  # prefer AOAC fibre (modern method); fall back to NSP
# Carbohydrate breakdown for the D-038 conversion (all in monosaccharide equivalents).
MONO_CODES = ("GLUC", "FRUCT", "GALACT")
DI_CODES = ("SUCR", "MALT", "LACT")
PART_CODES = ("STAR", "OLIGO", "TOTSUG", *MONO_CODES, *DI_CODES)


def parse_value(cell: object) -> float | None:
    if cell is None:
        return None
    text = str(cell).strip()
    if text == "" or text.upper() == "N":
        return None
    if text.lower() == "tr":
        return 0.0
    return float(text)


def _sum_or_none(values: list[float | None]) -> float | None:
    """Sum only if every part is known: a partial sum would silently undercount."""
    return None if any(v is None for v in values) else sum(values)


def _carb_parts(row, column) -> CarbParts:
    value = {code: parse_value(row[column[code]]) for code in PART_CODES}
    return CarbParts(
        starch_g=value["STAR"],
        oligo_g=value["OLIGO"],
        total_sugars_g=value["TOTSUG"],
        mono_sugars_g=_sum_or_none([value[c] for c in MONO_CODES]),
        di_sugars_g=_sum_or_none([value[c] for c in DI_CODES]),
    )


def read_cofid(path: Path) -> list[FoodRecord]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    rows = list(workbook[SHEET].iter_rows(values_only=True))
    header, codes = rows[0], rows[1]
    column = {str(code): i for i, code in enumerate(codes) if code}
    missing = [code for code in [*CODES.values(), *FIBRE_CODES, *PART_CODES] if code not in column]
    if missing:
        raise ValueError(f"CoFID sheet {SHEET!r} is missing columns {missing}")
    code_col, name_col, group_col = header.index("Food Code"), header.index("Food Name"), header.index("Group")

    records = []
    for row in rows[3:]:
        if not row or not row[code_col]:
            continue
        values = {field: parse_value(row[column[code]]) for field, code in CODES.items()}
        fibre = next(
            (v for v in (parse_value(row[column[c]]) for c in FIBRE_CODES) if v is not None), None
        )
        records.append(
            FoodRecord(
                source=SOURCE_KEY,
                source_id=str(row[code_col]),
                name=str(row[name_col]).strip(),
                category=str(row[group_col]) if row[group_col] else None,
                fiber_g=fibre,
                carb_basis="available",
                carb_parts=_carb_parts(row, column),
                **values,
            )
        )
    return records
