from ..config.config import ElroyContext


def only_in_debug(context: ElroyContext):
    return context.config.debug_mode


# TODO: implement @tool decorator


def example_debug_tool(context: ElroyContext):
    if only_in_debug(context):
        print("This is a debug tool")
    else:
        print("This is not a debug tool")
