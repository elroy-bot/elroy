import pytest

from elroy.core.ctx import ElroyConfig
from elroy.core.session import open_turn_context
from elroy.repository.memo import augment_text
from elroy.repository.memories.factory import build_memory_lifecycle_orchestrator


@pytest.mark.flaky(reruns=3)
def test_augment_memory(ctx: ElroyConfig):
    with open_turn_context(ctx) as turn:
        build_memory_lifecycle_orchestrator(turn).do_create_memory(
            "My best friend", "My best friend's name is Ted, his birthday is April 27", [], False
        )

    resp = augment_text(ctx, "Ted bday gift: War and Peace")

    assert "april" in resp.lower()
    assert "best friend" in resp.lower()


def test_no_relevant_mems(ctx: ElroyConfig):
    with open_turn_context(ctx) as turn:
        build_memory_lifecycle_orchestrator(turn).do_create_memory("Chores", "I need to go to the grocery store Sunday", [], False)

    resp = augment_text(ctx, "My dog has been sick")

    assert resp == "My dog has been sick"
