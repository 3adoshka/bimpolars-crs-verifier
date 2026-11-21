import math
from pathlib import Path
from datetime import datetime, timezone
import ifcopenshell
import polars as pl
import bimpolars as bpl
from pyproj import CRS

LINEAR_TOLERANCE_M = 0.001     # 1.0 mm maximum survey origin drift
ANGLE_TOLERANCE_DEG = 0.005    # 0.005 deg maximum True North rotation drift
VECTOR_NORM_TOL = 1e-5         # Unit-vector orthogonality tolerance for XAxisAbscissa/Ordinate

def extract_openbim_georef(ifc_file: Path) -> dict:
    model = ifcopenshell.open(str(ifc_file))
    bdf = bpl.read_ifc(str(ifc_file))
    element_count = bdf.frame.height
    schema_ver = model.schema

    crs_entities = model.by_type("IfcProjectedCRS")
    conv_entities = model.by_type("IfcMapConversion")

    if not crs_entities or not conv_entities:
        return {
            "container": ifc_file.name,
            "ifc_schema": schema_ver,
            "element_count": element_count,
            "has_georeferencing": False,
            "epsg_code": "MISSING",
            "vertical_datum": "MISSING",
            "crs_valid_pyproj": False,
            "orthogonal_vector_valid": False,
            "easting_m": None,
            "northing_m": None,
            "ortho_height_m": None,
            "grid_north_deg": None,
            "map_scale": None,
        }

    crs_entity = crs_entities[0]
    conv = conv_entities[0]
    epsg_name = str(crs_entity.Name or "UNKNOWN").strip()
    v_datum = str(getattr(crs_entity, "VerticalDatum", None) or "UNSPECIFIED").strip()

    try:
        CRS.from_user_input(epsg_name)
        crs_valid = True
    except Exception:
        crs_valid = False

    abscissa = float(conv.XAxisAbscissa) if conv.XAxisAbscissa is not None else 1.0
    ordinate = float(conv.XAxisOrdinate) if conv.XAxisOrdinate is not None else 0.0
    vec_norm = math.hypot(abscissa, ordinate)
    vector_valid = abs(vec_norm - 1.0) <= VECTOR_NORM_TOL
    angle_deg = round(math.degrees(math.atan2(ordinate, abscissa)), 6)

    return {
        "container": ifc_file.name,
        "ifc_schema": schema_ver,
        "element_count": element_count,
        "has_georeferencing": True,
        "epsg_code": epsg_name,
        "vertical_datum": v_datum,
        "crs_valid_pyproj": crs_valid,
        "orthogonal_vector_valid": vector_valid,
        "easting_m": float(conv.Eastings),
        "northing_m": float(conv.Northings),
        "ortho_height_m": float(conv.OrthogonalHeight),
        "grid_north_deg": angle_deg,
        "map_scale": float(conv.Scale) if conv.Scale is not None else 1.0,
    }

def verify_federation_crs(master_ifc: str | Path, discipline_ifcs: list[str | Path], output_dir: str | Path = "crs_audit_outputs") -> pl.DataFrame:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    master_data = extract_openbim_georef(Path(master_ifc))
    records = [master_data] + [extract_openbim_georef(Path(p)) for p in discipline_ifcs]

    df = pl.DataFrame(records).with_columns([
        pl.lit(master_data["container"]).alias("reference_master"),
        pl.lit(timestamp).alias("audit_timestamp_utc"),
        (pl.col("epsg_code") == master_data["epsg_code"]).alias("crs_match"),
        (pl.col("vertical_datum") == master_data["vertical_datum"]).alias("vertical_datum_match"),
        (pl.col("easting_m") - master_data["easting_m"]).abs().round(6).alias("delta_easting_m"),
        (pl.col("northing_m") - master_data["northing_m"]).abs().round(6).alias("delta_northing_m"),
        (pl.col("ortho_height_m") - master_data["ortho_height_m"]).abs().round(6).alias("delta_z_m"),
        (pl.col("grid_north_deg") - master_data["grid_north_deg"]).abs().round(6).alias("delta_angle_deg"),
        (pl.col("map_scale") - master_data["map_scale"]).abs().round(8).alias("delta_scale"),
    ]).with_columns([
        (
            pl.col("has_georeferencing")
            & pl.col("crs_valid_pyproj")
            & pl.col("orthogonal_vector_valid")
            & pl.col("crs_match")
            & pl.col("vertical_datum_match")
            & (pl.col("delta_easting_m") <= LINEAR_TOLERANCE_M)
            & (pl.col("delta_northing_m") <= LINEAR_TOLERANCE_M)
            & (pl.col("delta_z_m") <= LINEAR_TOLERANCE_M)
            & (pl.col("delta_angle_deg") <= ANGLE_TOLERANCE_DEG)
            & (pl.col("delta_scale") <= 1e-6)
        ).alias("federation_gate_pass")
    ])

    df.write_parquet(out_path / "federation_crs_audit.parquet")
    df.write_csv(out_path / "federation_crs_scorecard.csv")
    return df

if __name__ == "__main__":
    scorecard = verify_federation_crs(
        master_ifc="PRJ01-ARC-ZZ-00-M3-A-0001.ifc",
        discipline_ifcs=["PRJ01-STR-ZZ-00-M3-S-0001.ifc", "PRJ01-MEP-ZZ-00-M3-M-0001.ifc"],
    )
    print("=== OPENBIM LoGeoRef 50 MULTI-MODEL CRS FEDERATION SCORECARD ===")
    print(scorecard.select(["container", "ifc_schema", "epsg_code", "orthogonal_vector_valid", "delta_easting_m", "delta_northing_m", "delta_z_m", "federation_gate_pass"]))
