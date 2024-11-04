from ..repository.data_models import EmbeddableSqlModel, Goal, Memory


def to_fact(row: EmbeddableSqlModel) -> str:
    if isinstance(row, Goal):
        from ..repository.goals.operations import goal_to_fact

        return goal_to_fact(row)
    elif isinstance(row, Memory):
        from ..repository.memory import memory_to_fact

        return memory_to_fact(row)
    else:
        raise ValueError(f"Unsupported type: {type(row)}")
