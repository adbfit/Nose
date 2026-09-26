import numpy as np
import pytest

from atlas3d.anatomy import NoseModel
from atlas3d.meshing import extract
from atlas3d.params import ParameterError, compute_landmarks, load_params, measured_profile


def test_every_reference_is_resolvable():
    p = load_params()
    for key, entry in p.items():
        for ref in entry.get("refs") or []:
            assert ref in p.references, (key, ref)
    assert all("pmid" in r for r in p.references.values())


@pytest.mark.parametrize("preset", ["female", "male"])
def test_landmarks_reproduce_profile_parameters(preset):
    p = load_params(preset=preset)
    m = measured_profile(compute_landmarks(p))
    assert m["nasal_length"] == pytest.approx(p["morphology.nasal_length"], abs=1e-6)
    assert m["nasofrontal_angle"] == pytest.approx(p["morphology.nasofrontal_angle"], abs=1e-6)
    assert m["nasolabial_angle"] == pytest.approx(p["morphology.nasolabial_angle"], abs=1e-6)
    assert m["goode_ratio"] == pytest.approx(p["morphology.goode_ratio"], abs=1e-6)


def test_overrides_are_validated():
    p = load_params(overrides={"nasolabial_angle": "110"})
    assert p["morphology.nasolabial_angle"] == 110.0
    with pytest.raises(ParameterError):
        load_params(overrides={"nasolabial_angle": "170"})
    with pytest.raises(ParameterError):
        load_params(overrides={"non_esiste": "1"})


@pytest.fixture(scope="module")
def fields():
    model = NoseModel(load_params(overrides={"filler.enabled": "true"}))
    return model, model.evaluate(spacing=0.8)


def test_all_structures_are_meshed(fields):
    model, f = fields
    for name in ["skin", "superficial_fat", "smas", "deep_fat", "bone",
                 "upper_lateral_cartilage", "lower_lateral_cartilage", "septum", "filler"]:
        assert not extract(f, name, smooth_iterations=0).empty, name


def test_soft_tissue_is_thinnest_at_rhinion(fields):
    model, f = fields
    thick = model._thick
    t_r = model.p["morphology.rhinion_position"]
    assert thick(t_r) < thick(0.0) and thick(t_r) < thick(0.84)


def test_filler_raises_the_dorsum():
    base = NoseModel(load_params())
    filled = NoseModel(load_params(overrides={"filler.enabled": "true", "filler.volume": "0.5"}))
    fb, ff = base.evaluate(spacing=0.8), filled.evaluate(spacing=0.8)
    # more skin volume anterior to the radix when filler is present
    assert (ff.volumes["skin"] < 0).sum() > (fb.volumes["skin"] < 0).sum()


def test_arteries_lie_above_the_framework(fields):
    model, f = fields
    vessels = model.arteries(f)
    labels = {v["label"] for v in vessels}
    assert {"angular", "lateral_nasal", "dorsal_nasal", "columellar"} <= labels
    from scipy.interpolate import RegularGridInterpolator
    S = RegularGridInterpolator(f.grid.axes, f.skin_n)
    for v in vessels:
        if v["label"] in ("lateral_nasal", "dorsal_nasal"):
            depth = -S(v["points"])
            assert np.all(depth > 0) and np.median(depth) < 4.0, v["name"]
