# Multi-Model CRS & Site Origin Federation Verifier (`bimpolars` + `pyproj`)

Automated pre-federation BIM QA/QC gate verifying that Architectural, Structural, and MEP IFC4 models share identical **IFC4 Georeferencing (`IfcProjectedCRS` & `IfcMapConversion`)**, survey coordinates, and True North orientation within 1.0 mm tolerance prior to Navisworks/ACC federation.

## Quickstart
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "bimpolars[ifc] @ git+[https://github.com/bedrock-engineer/bimpolars.git](https://github.com/bedrock-engineer/bimpolars.git)" ifcopenshell polars pyproj
python3 generate_federated_models.py
python3 crs_alignment_verifier.py
```
