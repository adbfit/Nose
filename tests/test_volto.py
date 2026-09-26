import pytest

from atlas3d.volto.arterie import FACIAL_ARTERY, REFERENCES
from atlas3d.volto.catalogo import STRUTTURE


def test_catalogue_tissues_are_known():
    kinds = {k for _, k in STRUTTURE.values()}
    assert kinds <= {"skin", "eyebrow", "bone", "cartilage", "eye", "muscle", "tooth"}
    assert "FMA7163" in STRUTTURE and STRUTTURE["FMA7163"][1] == "skin"


def test_facial_artery_depth_profile_follows_meta_analysis():
    depths = {name: d for name, d, _, _ in FACIAL_ARTERY}
    assert depths["commissura"] == pytest.approx(9.7, abs=0.1)
    assert depths["canto_mediale"] == pytest.approx(2.4, abs=0.1)
    diam = [dia for _, _, dia, _ in FACIAL_ARTERY]
    assert diam == sorted(diam, reverse=True)       # the artery tapers towards its termination


def test_references_have_identifiers():
    for key, ref in REFERENCES.items():
        assert ref["citation"] and "pmid" in ref, key
