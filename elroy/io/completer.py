import os
from typing import Any, Generator

from prompt_toolkit.completion import Completion, PathCompleter, WordCompleter


def show_in_file_filter(file_path: str) -> bool:
    # check if it's actually a file
    file_path = file_path.rstrip(os.sep)
    if os.path.basename(file_path).startswith("."):
        return False
    else:
        return True


def get_path_completions(document, complete_event) -> Generator[Completion, Any, None]:
    # Use PathCompleter for file paths - let it handle directory traversal
    path_completer = PathCompleter(file_filter=show_in_file_filter)

    # Get the text after the command, handling empty case
    path_text = document.text[len("/ingest_doc") :].lstrip()
    # Get cursor position relative to the path, ensuring it stays within bounds
    path_cursor_position = min(
        len(path_text), max(0, document.cursor_position - len("/ingest_doc"))  # Don't go beyond text length  # Don't go negative
    )

    # Create a new document for the path part only
    from prompt_toolkit.document import Document

    path_document = Document(path_text, cursor_position=path_cursor_position)

    # Get completions for the path
    yield from path_completer.get_completions(path_document, complete_event)


class SlashCompleter(WordCompleter):
    def get_completions(self, document, complete_event):  # noqa F811
        text = document.text
        if not text.startswith("/"):
            return

        words = text.split()

        # Handle file path completion for /ingest_doc
        if len(words) > 0 and words[0] == "/ingest_doc":
            yield from get_path_completions(document, complete_event)
            return

        exact_cmd_prefix = False
        # If we just have "/" or are typing the command part
        if len(words) <= 1:
            cmds = {c.split()[0] for c in self.words}  # type: ignore # Get just the command parts
            for cmd in cmds:
                if cmd.startswith(text) and text != cmd:
                    yield Completion(cmd, start_position=-len(text))
                    exact_cmd_prefix = True
            if exact_cmd_prefix:
                return

        # If we have a command and are typing arguments
        cmd = words[0]
        # Get the full command templates that start with this command
        matching_commands = [w for w in self.words if w.startswith(cmd)]  # type: ignore
        if matching_commands:
            # Create a completer just for the arguments of this command
            arg_text = " ".join(words[1:])
            # Extract just the argument parts from the matching commands
            arg_options = [" ".join(m.split()[1:]) for m in matching_commands if len(m.split()) > 1]
            if arg_options:
                # Complete from the start of the argument portion
                arg_start_position = -len(arg_text) if arg_text else 0
                for arg in arg_options:
                    if arg.startswith(arg_text):
                        yield Completion(arg, start_position=arg_start_position)
