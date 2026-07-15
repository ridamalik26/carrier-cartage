"""Master data ingestion (Section 4) — Fleet, Loads, kms travelled, OGRA fleet.

The source file is ~80MB (one row per shipment/trip). Streamed with
openpyxl(read_only=True) so the whole sheet is never materialized as a
DataFrame in memory at once.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import openpyxl

from backend.common import normalize_cc_number, parse_numeric

OGRA_MARKER = "OGRA Compliance"


@dataclass
class MasterDataResult:
    total_loads: dict[int, int] = field(default_factory=dict)
    kms_travelled: dict[int, float] = field(default_factory=dict)
    fleet_vehicles: dict[int, set] = field(default_factory=dict)      # cc_number -> {Vehicle No, ...}
    ogra_fleet_vehicles: dict[int, set] = field(default_factory=dict)  # cc_number -> {Vehicle No, ...}

    def as_table(self) -> dict[int, dict]:
        cc_numbers = set(self.total_loads) | set(self.fleet_vehicles)
        table = {}
        for cc in cc_numbers:
            table[cc] = {
                "total_loads": self.total_loads.get(cc, 0),
                "kms_travelled": self.kms_travelled.get(cc, 0.0),
                "fleet": len(self.fleet_vehicles.get(cc, set())),
                "ogra_fleet": len(self.ogra_fleet_vehicles.get(cc, set())),
            }
        return table


def ingest_master_data(file_path: str, sheet_name: str = "Data") -> MasterDataResult:
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb[sheet_name]

    rows = ws.iter_rows(values_only=True)
    header = [str(c).strip() if c is not None else "" for c in next(rows)]
    col_idx = {name: i for i, name in enumerate(header)}

    required = ["Carrier", "Vehicle No", "Distance", "TD-Vehicle Classification Group"]
    missing = [c for c in required if c not in col_idx]
    if missing:
        raise ValueError(f"master data sheet missing expected columns: {missing}")

    result = MasterDataResult()

    for row in rows:
        raw_carrier = row[col_idx["Carrier"]]
        if raw_carrier is None or str(raw_carrier).strip() == "":
            continue
        try:
            cc = normalize_cc_number(raw_carrier)
        except ValueError:
            continue

        vehicle_no = row[col_idx["Vehicle No"]]
        distance_raw = row[col_idx["Distance"]]
        classification = row[col_idx["TD-Vehicle Classification Group"]]

        result.total_loads[cc] = result.total_loads.get(cc, 0) + 1

        if distance_raw not in (None, ""):
            try:
                result.kms_travelled[cc] = result.kms_travelled.get(cc, 0.0) + parse_numeric(distance_raw)
            except ValueError:
                pass

        if vehicle_no not in (None, ""):
            result.fleet_vehicles.setdefault(cc, set()).add(vehicle_no)
            if classification and OGRA_MARKER in str(classification):
                result.ogra_fleet_vehicles.setdefault(cc, set()).add(vehicle_no)

    wb.close()
    return result
