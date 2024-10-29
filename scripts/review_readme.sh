#!/bin/bash

aider --read elroy/cli/main.py --read elroy/tools/system_commands.py  --file README.md -m "Review main.py and the README, and tell me if the readme looks reasonably complete. Note the commands in the main file annotated by @app.command, and the system commands listed in system_commands.py. Ensure the README is up to date and accurate"
