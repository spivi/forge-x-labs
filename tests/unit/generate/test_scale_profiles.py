from app.cloudforge.generate.scale_profiles import SCALE_PROFILES, get_profile


def test_all_five_profiles_present():
    assert set(SCALE_PROFILES) == {"tiny", "small", "medium", "large", "xlarge"}


def test_bands_are_monotonic_increasing():
    order = ["tiny", "small", "medium", "large", "xlarge"]
    maxes = [SCALE_PROFILES[k].max_nodes for k in order]
    assert maxes == sorted(maxes)


def test_xlarge_is_graph_only():
    assert get_profile("xlarge").emit_terraform is False
    assert get_profile("small").emit_terraform is True
