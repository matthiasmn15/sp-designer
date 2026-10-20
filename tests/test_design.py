import math

import pytest
from pydantic import ValidationError

from sp_designer.design.geometry import disc_rect_overlap, evaluate
from sp_designer.design.library import DesignLibrary
from sp_designer.design.models import Design, Electrode


@pytest.mark.parametrize("r, w, h, expected", [
    (1.0, 10.0, 10.0, math.pi),  # disc inside rectangle
    (10.0, 1.0, 2.0, 2.0),  # rectangle inside disc
    (1.0, 2.0, 2.0, math.pi),  # inscribed disc
])
def test_disc_rect_overlap_limits(r, w, h, expected):
    assert disc_rect_overlap(r, w, h) == pytest.approx(expected)


def test_disc_rect_overlap_partial_matches_numeric():
    r, w, h = 1.0, 1.2, 3.0
    n = 4000
    dx = w / n
    numeric = sum(2 * min(math.sqrt(max(r * r - x * x, 0)), h / 2) * dx
                  for x in (-w / 2 + (i + 0.5) * dx for i in range(n)))
    assert disc_rect_overlap(r, w, h) == pytest.approx(numeric, rel=1e-4)


def test_j_gap_smallest_common_area_and_mass(db):
    design = Design(type="j_gap", gap=0.3,
                    center=Electrode(material_id="Ir", shape="round", diameter=2.0, thickness=0.8),
                    ground=Electrode(material_id="Pt", shape="rect", width=2.5, height=2.5, thickness=0.8))
    r = evaluate(design, db)
    assert r.common_area == pytest.approx(math.pi)  # disc fully inside the larger rectangle
    assert r.center.pm_volume == pytest.approx(math.pi * 0.8)
    assert r.ground.pm_volume == pytest.approx(2.5 * 2.5 * 0.8)
    assert r.ground.wearable_volume == pytest.approx(math.pi * 0.8)
    ir_density = db.get("Ir").properties["density"].value
    assert r.center.pm_mass == pytest.approx(math.pi * 0.8 * ir_density * 1e-3)  # mg
    assert any("centre pad defines" in w for w in r.warnings)


def test_multi_pad_scales_with_number_of_gaps(db):
    design = Design(type="multi_pad", n_ground=4,
                    center=Electrode(width=1.5, height=2.0, thickness=0.6),
                    ground=Electrode(width=1.2, height=2.5, thickness=0.5))
    r = evaluate(design, db)
    assert r.n_gaps == 4
    assert r.common_area == pytest.approx(1.2 * 2.0)
    assert r.total_wear_area == pytest.approx(4 * 1.2 * 2.0)
    assert r.center.pm_volume == pytest.approx(4 * 1.5 * 2.0 * 0.6)
    assert r.ground.wearable_volume == pytest.approx(4 * 2.4 * 0.5)


def test_annular_geometry(db):
    design = Design(type="annular", gap=0.3,
                    center=Electrode(diameter=4.0, length=3.0, thickness=0.5),
                    ground=Electrode(length=2.5, thickness=0.5))
    r = evaluate(design, db)
    assert r.ground_inner_diameter == pytest.approx(4.6)
    assert r.common_area == pytest.approx(math.pi * 4.0 * 2.5)  # centre surface over overlap length
    assert r.center.pm_volume == pytest.approx(math.pi / 4 * (16 - 9) * 3.0)
    assert r.ground.pm_volume == pytest.approx(math.pi / 4 * (5.6 ** 2 - 4.6 ** 2) * 2.5)


def test_annular_rejects_too_thick_sleeve():
    with pytest.raises(ValidationError):
        Design(type="annular", center=Electrode(diameter=1.0, thickness=0.5))


def test_cost_missing_without_price_and_warning_for_non_precious(db):
    design = Design(type="j_gap", center=Electrode(material_id="Ni"), ground=Electrode(material_id="Ir"))
    r = evaluate(design, db)
    assert r.center.pm_cost is None and r.pm_cost is None
    assert any("not a precious metal" in w for w in r.warnings)


def test_library_ids_and_update(tmp_path):
    lib = DesignLibrary(tmp_path)
    a = lib.save(Design(name="Test plug"))
    b = lib.save(Design(name="Test plug"))
    assert (a.id, b.id) == ("Test-plug", "Test-plug-2")
    lib.save(a.model_copy(update={"gap": 0.4}))
    assert DesignLibrary(tmp_path).get("Test-plug").gap == 0.4
    lib.delete("Test-plug-2")
    assert [d.id for d in lib.all()] == ["Test-plug"]


def test_design_api(client):
    body = [{"name": "J", "type": "j_gap", "center": {"shape": "round", "diameter": 2.0}}]
    r = client.post("/api/designs/evaluate", json=body)
    assert r.status_code == 200 and r.json()[0]["result"]["n_gaps"] == 1
    assert client.post("/api/designs/evaluate", json=[{"gap": -1}]).status_code == 422
    saved = client.post("/api/designs", json=body[0]).json()
    assert [d["id"] for d in client.get("/api/designs").json()] == [saved["id"]]
    x = client.post("/api/designs/export", json={"designs": body, "format": "csv"})
    assert x.text.splitlines()[0] == "Group;Parameter;Unit;J"
    assert client.post("/api/designs/export", json={"designs": body, "format": "xlsx"}).status_code == 200
    assert client.delete(f"/api/designs/{saved['id']}").status_code == 204
