from random import Random

import pytest

from app.cloudforge.generate.fragments import base
from app.cloudforge.generate.fragments.base import (
    FragmentBundle,
    all_kinds,
    get_fragment,
    register,
)
from app.cloudforge.models.graph import GraphNode, NodeSecurity, NodeTags, NodeType


@pytest.fixture(autouse=True)
def _isolate_fragment_registry():
    """Snapshot ``base._REGISTRY`` and restore it after each test.

    ``test_register_and_retrieve_fragment`` below registers ``"test.dummy"``
    into the module-global registry via ``@register``. Without cleanup that
    entry leaks into ``all_kinds()`` for the rest of the test process.
    """
    snapshot = dict(base._REGISTRY)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(snapshot)


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
    with pytest.raises(KeyError):
        get_fragment("nope.missing")
