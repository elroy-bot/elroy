#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <next-version>"
    echo "Example: $0 0.0.44"
    exit 1
fi

NEXT_VERSION=$1

# cd to repo root
cd "$(git rev-parse --show-toplevel)"

# Get today's date
TODAY=$(date +%Y-%m-%d)

# Get git commits since last release
COMMITS=$(git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"- %s")

elroy --help > .aider.elroy.help.txt

aider --read .aider.elroy.help.txt --file README.md --no-auto-commit -m '
Review the output of `elroy --help` and README.md. Make any edits that would make the document more complete and accurate.
'

# Keep defaults.yml comments in sync with --help output
# ./elroy/defaults.yml
aider --file elroy/cli/main.py elroy/defaults.yml elroy/config/ctx.py --no-auto-commit -m '
Review main.py and elroy/defaults.yml. The configuration options in defaults.yml correspond to the command line options in main.py.
Make sure the comments in defaults.yml are in sync with the command line options in main.py.
The headings should be the same, ie the YAML should have comments corresponding to the name of the rich_help_panel of the main.py options
These headings should also be present in ctx.py for the ElroyContext constructor.
'

# First update documentation
aider --read elroy/cli/main.py --read elroy/system_commands.py  --file README.md --no-auto-commit -m '
Review main.py, system_commands.py and README.md. Make any edits that would make the document more complete.
Pay particular attention to:
- Ensuring all assistant tools are documented under the "## Available assistant and CLI Commands" section of the README. See system_commands.py for the list of available assistant/CLI tools.
- Ensure the README accurately describes which models are supported by Elroy.

Do NOT remove any links or gifs.
'

# Then update changelog
aider --file CHANGELOG.md --no-auto-commit -m "
Update CHANGELOG.md to add version $NEXT_VERSION. Here are the commits since the last release:

$COMMITS

Please:
1. Add a new entry at the top of the changelog for version $NEXT_VERSION dated $TODAY
2. Group the commits into appropriate sections (Added, Fixed, Improved, Infrastructure, etc.) based on their content
3. Clean up and standardize the commit messages to be more readable
4. Maintain the existing changelog format

Do NOT remove any existing entries.

Note that not all housekeeping updates need to be mentioned. Only those changes that a maintainer or user would be interested in should be included.
"

