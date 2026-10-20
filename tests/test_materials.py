import pytest

from sp_designer.materials.database import MaterialDatabase
from sp_designer.materials.models import MaterialDef, PropertyInput
from sp_designer.materials.ranking import rank_materials


def test_elements_get_auto_values_in_si(db):
    ir = db.get("Ir")
    assert ir.properties["density"].origin == "auto"
    assert ir.properties["density"].value == pytest.approx(22562, rel=0.01)  # kg/m³
    assert ir.properties["melting_point"].value == pytest.approx(2446, abs=5)  # °C
    assert ir.properties["specific_heat"].value == pytest.approx(131, rel=0.02)  # J/(kg·K)
    assert ir.properties["thermal_expansion"].origin == "manual"


def test_manual_beats_auto_and_user_beats_manual(db, data_dir, prices):
    alloy = db.get("Alloy-600")
    assert alloy.properties["density"].origin == "manual"
    assert alloy.properties["density"].value == 8470
    db.set_overrides("Ir", {"density": PropertyInput(value=22500, source="test")})
    assert db.get("Ir").properties["density"].origin == "user"
    # overrides persist
    reloaded = MaterialDatabase(data_dir, prices)
    assert reloaded.get("Ir").properties["density"].value == 22500
    reloaded.set_overrides("Ir", {"density": None})
    assert reloaded.get("Ir").properties["density"].origin == "auto"


def test_alloy_estimates(db):
    ir, rh, alloy = db.get("Ir"), db.get("Rh"), db.get("Ir-10Rh")
    rho = 1 / (0.9 / ir.properties["density"].value + 0.1 / rh.properties["density"].value)
    assert alloy.properties["density"].origin == "estimated"
    assert alloy.properties["density"].value == pytest.approx(rho)
    assert "thermal_conductivity" not in alloy.properties  # not estimated on purpose


def test_derived_melt_energy_density(db):
    ir = db.get("Ir")
    p = {k: v.value for k, v in ir.properties.items()}
    expected = p["density"] * (p["specific_heat"] * (p["melting_point"] - 25) + p["fusion_heat"] * 1000) * 1e-9
    assert ir.properties["melt_energy_density"].value == pytest.approx(expected)
    assert 9 < expected < 12  # J/mm³ plausibility


def test_prices_and_cost_per_volume(db):
    pt = db.get("Pt")
    assert pt.properties["price"].value == pytest.approx(1641.0 / 31.1034768)
    assert pt.properties["cost_per_volume"].value == pytest.approx(
        pt.properties["price"].value * pt.properties["density"].value / 1000)
    # base metal without price is ignored for precious alloys and noted
    ptni = db.get("Pt-5Ni")
    assert ptni.properties["price"].value == pytest.approx(0.95 * pt.properties["price"].value)
    assert "Ni" in ptni.properties["price"].note
    # carrier alloys without base metal prices have no price
    assert "price" not in db.get("Alloy-600").properties


def test_user_material_lifecycle(db):
    mdef = MaterialDef(id="Ir-5Rh", name="Ir-5Rh", kind="alloy", categories=["precious"],
                       composition={"Ir": 95, "Rh": 5})
    mat = db.add_material(mdef)
    assert mat.user_defined
    assert mat.composition["Ir"] == pytest.approx(0.95)
    with pytest.raises(ValueError):
        db.add_material(mdef)
    with pytest.raises(ValueError):
        db.delete_material("Ir")  # seed materials cannot be deleted
    db.delete_material("Ir-5Rh")
    assert "Ir-5Rh" not in db.ids()


def test_unknown_constituent_rejected(db):
    with pytest.raises(ValueError, match="unknown constituents"):
        db.add_material(MaterialDef(id="X", name="X", kind="alloy", categories=["precious"],
                                    composition={"Os": 1.0}))


def test_ranking_direction_and_coverage(db):
    mats = [db.get(i) for i in ("Ir", "Pt", "Pd")]
    ranked = rank_materials(mats, {"melting_point": 1.0})
    assert [r.id for r in ranked] == ["Ir", "Pt", "Pd"]
    assert ranked[0].score == 1.0 and ranked[-1].score == 0.0
    ranked = rank_materials(mats, {"cost_per_volume": 1.0})  # lower is better
    assert ranked[0].id == "Pd"
    ranked = rank_materials(mats, {"melting_point": 1.0, "oxidation_resistance": 1.0})
    assert all(r.coverage == pytest.approx(0.5) for r in ranked)  # ratings not set
