#!/usr/bin/env python3
"""Take a screenshot of the Elroy TUI, optionally simulating user input.

Usage:
    # Just launch and screenshot after 3s
    python scripts/screenshot.py

    # Type a message, wait for response, then screenshot
    python scripts/screenshot.py --message "What do you know about me?" --wait 15

    # Custom output path and terminal size
    python scripts/screenshot.py --output out.svg --width 140 --height 45
"""

import argparse
import asyncio
from pathlib import Path


async def main(output: str, message: str | None, wait: float, width: int, height: int, show_internal_thought: bool | None) -> None:
    from elroy.core.session import init_elroy_session
    from elroy.io.textual_app import make_app

    overrides: dict = {"enable_assistant_greeting": False}
    if show_internal_thought is not None:
        overrides["show_internal_thought"] = show_internal_thought
    app = make_app(**overrides)

    with init_elroy_session(app.ctx, app.io, check_db_migration=True, should_onboard_interactive=False):
        async with app.run_test(headless=True, size=(width, height)) as pilot:
            # Let the app mount and session init settle
            await pilot.pause(1.0)

            if message:
                # Set the input value directly and submit
                from textual.widgets import Input

                input_widget = pilot.app.query_one("#chat-input", Input)
                input_widget.value = message
                await pilot.press("enter")

            # Wait for response (or just for visual state to settle)
            await pilot.pause(wait)
            svg = app.export_screenshot()

    Path(output).write_text(svg)
    print(f"Screenshot saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screenshot the Elroy TUI")
    parser.add_argument("--output", default="screenshot.svg", help="Output SVG path")
    parser.add_argument("--message", default=None, help="Message to type and submit before screenshotting")
    parser.add_argument("--wait", type=float, default=3.0, help="Seconds to wait after input before capturing")
    parser.add_argument("--width", type=int, default=120, help="Terminal width in columns")
    parser.add_argument("--height", type=int, default=40, help="Terminal height in rows")
    parser.add_argument(
        "--show-internal-thought",
        dest="show_internal_thought",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override show_internal_thought setting (default: use config/defaults.yml)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.output, args.message, args.wait, args.width, args.height, args.show_internal_thought))
