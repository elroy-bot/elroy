import pytest

from elroy.core.ctx import ElroyContext
from elroy.repository.memories.operations import augment_memory, do_create_memory


@pytest.mark.flaky(reruns=3)
def test_augment_memory(ctx: ElroyContext):
    do_create_memory(ctx, "My best friend", "My best friend's name is Ted, his birthday is April 27", [], False)

    resp = augment_memory(ctx, "Ted bday gift: War and Peace")

    assert "april" in resp.text.lower()
    assert "best friend" in resp.text.lower()


def test_no_relevant_mems(ctx: ElroyContext):
    do_create_memory(ctx, "Chores", "I need to go to the grocery store Sunday", [], False)

    resp = augment_memory(ctx, "My dog has been sick")

    assert resp.text == "My dog has been sick"
