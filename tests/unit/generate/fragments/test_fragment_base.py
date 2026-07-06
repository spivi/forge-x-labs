from random import Random

from app.cloudforge.generate.fragments.base import (
    FragmentBundle,
    all_kinds,
    get_fragment,
    register,
)
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType


def test_register_and_retrieve_fragment():
    @register("test.dummy")
    class _Dummy:
        def build(self, ns, rng, params):
            node = GraphNode(
                id=f"{ns}/n",
                type=NodeType.S3_BUCKET,
                name="b",
                tags=NodeTags(env="staging", owner="platform-team", app="a"),
                security=NodeSecurity(criticality="low"),
            )
            return FragmentBundle(nodes=[node], edges=[], findings=[], paths=[])

    assert "test.dummy" in all_kinds()
    bundle = get_fragment("test.dummy").build("frag0", Random(0), {})
    assert bundle.nodes[0].id == "frag0/n"


def test_unknown_kind_raises():
    import pytest

    with pytest.raises(KeyError):
        get_fragment("nope.missing")
