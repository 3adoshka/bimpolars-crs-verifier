import ifcopenshell
import ifcopenshell.api

def build_discipline_ifc(filename: str, discipline: str, epsg: str, easting: float, northing: float, height: float, x_axis_abscissa: float = 1.0, x_axis_ordinate: float = 0.0):
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="PRJ01")
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")

    # Configure IFC4 Georeferencing (IfcProjectedCRS + IfcMapConversion)
    ifcopenshell.api.run("georeference.add_georeferencing", model)
    ifcopenshell.api.run(
        "georeference.edit_georeferencing",
        model,
        projected_crs={"Name": epsg, "Description": "Project Survey CRS"},
        map_conversion={
            "Eastings": easting,
            "Northings": northing,
            "OrthogonalHeight": height,
            "XAxisAbscissa": x_axis_abscissa,
            "XAxisOrdinate": x_axis_ordinate,
            "Scale": 1.0,
        },
    )

    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="SITE_01")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="BLDG_01")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="LVL_00")

    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])

    elem = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcColumn", name=f"{discipline}_COL_GRID_A1")
    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[elem])

    model.write(filename)
    print(f"Created {filename} ({epsg} | E:{easting}, N:{northing}, Z:{height})")

if __name__ == "__main__":
    # 1. Master Architectural Model (Reference Baseline)
    build_discipline_ifc("PRJ01-ARC-ZZ-00-M3-A-0001.ifc", "ARC", "EPSG:32638", 654321.000, 2812345.000, 12.500)
    # 2. Structural Model (Aligned within 1mm tolerance -> PASS)
    build_discipline_ifc("PRJ01-STR-ZZ-00-M3-S-0001.ifc", "STR", "EPSG:32638", 654321.0005, 2812345.0002, 12.500)
    # 3. MEP Model (Wrong EPSG & unshifted local 0,0,0 origin -> FAIL)
    build_discipline_ifc("PRJ01-MEP-ZZ-00-M3-M-0001.ifc", "MEP", "EPSG:4326", 0.0, 0.0, 0.0, 0.866025, 0.5)
