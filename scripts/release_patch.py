import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass

from semantic_version import Version

from elroy.tools.function_caller import get_function_schemas

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(REPO_ROOT, "elroy", "__init__.py"), "r") as f:
    for line in f:
        if line.startswith("__version__"):
            current_version = line.split('"')[1]
            break
    else:
        raise ValueError("Version not found in __init__.py")

NEXT_PATCH = str(Version(current_version).next_patch())


@dataclass
class Errors:
    messages: list[str]


def check_main_up_to_date(errors: Errors):
    # Fetch latest from remote
    subprocess.run(["git", "fetch", "origin", "main"], check=True)

    # Get commit hashes for local and remote main
    local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, check=True).stdout.strip()

    if local != remote:
        errors.messages.append("Error: Local branch is not up to date with remote main")


def check_on_main_branch(errors: Errors):
    """Ensure we are on the main branch"""
    current_branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if current_branch != "main":
        errors.messages.append(f"Error: Not on main branch. Current branch: {current_branch}")


def check_pyproject_version_consistent(errors: Errors):
    """Ensure version tags match between __init__.py and pyproject.toml"""
    pyproject_version = _get_version_from_pyproject()

    if current_version != pyproject_version:
        errors.messages.append(
            f"Error: Version mismatch between files: __init__.py: {current_version}, pyproject.toml: {pyproject_version}"
        )


def check_remote_tag_consistent(errors: Errors):
    """Ensure remote version tag exists and matches local tag commit"""
    try:
        # Get local tag commit
        local_tag_commit = subprocess.run(
            ["git", "rev-list", "-n", "1", f"v{current_version}"], capture_output=True, text=True, check=True
        ).stdout.strip()

        # Get remote tag commit
        remote_tag_commit = (
            subprocess.run(["git", "ls-remote", "origin", f"refs/tags/v{current_version}"], capture_output=True, text=True, check=True)
            .stdout.strip()
            .split()[0]
        )

        if not remote_tag_commit:
            errors.messages.append(f"Error: Git tag v{current_version} not found on remote")
        elif local_tag_commit != remote_tag_commit:
            errors.messages.append(f"Error: Local tag v{current_version} doesn't match remote tag")

    except subprocess.CalledProcessError:
        errors.messages.append(f"Error: Failed to check remote tag v{current_version}")


def check_local_tag(errors: Errors):
    """Ensure version tag exists locally and is an ancestor of current HEAD"""
    try:
        # Check if tag exists locally
        tag_commit = subprocess.run(
            ["git", "rev-list", "-n", "1", f"v{current_version}"], capture_output=True, text=True, check=True
        ).stdout.strip()

        # Check if tag commit is an ancestor of current HEAD
        result = subprocess.run(["git", "merge-base", "--is-ancestor", tag_commit, "HEAD"], capture_output=True, check=False)

        if result.returncode != 0:
            errors.messages.append(f"Error: Git tag v{current_version} is not an ancestor of current HEAD")

    except subprocess.CalledProcessError:
        errors.messages.append(f"Error: Git tag v{current_version} not found locally")


def run_tests(errors: Errors):
    """Run pytest with specified chat models and cache results"""
    # Get current HEAD SHA
    head_sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    # Check if we have a cached successful test run for this SHA
    cache_file = f"/tmp/elroy-tests-{head_sha}.txt"

    if os.path.exists(cache_file):
        return

    try:
        # Run pytest with specified chat models
        subprocess.run(["pytest", "--chat-models=gpt-4,claude-3-sonnet-20240229", "-n", "auto"], check=True)

        # If tests pass, create cache file
        with open(cache_file, "w") as f:
            f.write(f"Tests passed for commit {head_sha}")

    except subprocess.CalledProcessError as e:
        errors.messages.append(f"Error: Tests failed:\n{e.stdout}\n{e.stderr}")


def update_schema_doc():
    # Get the repository root directory
    schema_md_path = os.path.join(REPO_ROOT, "docs", "tools_schema.md")

    # Read the existing markdown file
    with open(schema_md_path, "r") as f:
        content = f.read()

    # Get schemas and sort by function name
    schemas = get_function_schemas()
    schemas.sort(key=lambda e: e["function"]["name"])

    # Convert schemas to JSON string with proper indentation
    json_content = json.dumps(schemas, indent=2)

    # Replace content between ```json and ``` markers
    updated_content = re.sub(r"```json\n.*?```", f"```json\n{json_content}\n```", content, flags=re.DOTALL)

    # Write the updated content back
    with open(schema_md_path, "w") as f:
        f.write(updated_content)


def check_most_recent_changelog_consistent(errors: Errors):
    """Check that the most recent changelog version matches the current version"""
    changelog_path = os.path.join(REPO_ROOT, "CHANGELOG.md")

    try:
        with open(changelog_path, "r") as f:
            # Find the first version header line
            for line in f:
                if match := re.search(r"\[(\d+\.\d+\.\d+)\]", line):
                    changelog_version = match.group(1)
                    if changelog_version != current_version:
                        errors.messages.append(
                            f"Error: Most recent changelog version [{changelog_version}] "
                            f"doesn't match current version [{current_version}]"
                        )
                    return

            errors.messages.append("Error: No version found in CHANGELOG.md")

    except FileNotFoundError:
        errors.messages.append("Error: CHANGELOG.md not found")


def check_bumpversion_config_consistent(errors: Errors):
    """Ensure version in .bumpversion.cfg matches current version"""
    config_path = os.path.join(REPO_ROOT, ".bumpversion.cfg")
    try:
        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("current_version = "):
                    config_version = line.strip().split(" = ")[1]
                    if config_version != current_version:
                        errors.messages.append(
                            f"Error: Version mismatch in .bumpversion.cfg: " f"config: {config_version}, current: {current_version}"
                        )
                    return

            errors.messages.append("Error: Version not found in .bumpversion.cfg")

    except FileNotFoundError:
        errors.messages.append("Error: .bumpversion.cfg not found")


def is_local_git_clean():
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return not result.stdout


def _get_version_from_pyproject() -> str:
    with open(os.path.join(REPO_ROOT, "pyproject.toml"), "r") as f:
        for line in f:
            if line.startswith("version = "):
                return line.split('"')[1]
    raise ValueError("Version not found in pyproject.toml")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Release a new patch version")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    args = parser.parse_args()

    errors = Errors([])
    print("Ensuring tags are consistent and up to date...")
    check_on_main_branch(errors)
    check_main_up_to_date(errors)
    check_pyproject_version_consistent(errors)
    check_bumpversion_config_consistent(errors)
    check_local_tag(errors)
    check_remote_tag_consistent(errors)
    check_most_recent_changelog_consistent(errors)

    if args.skip_tests:
        print("Skipping tests")
    else:
        run_tests(errors)

    if errors.messages:
        for message in errors.messages:
            print(message)
        sys.exit(1)
    else:
        print("Done")

    # checkout branch for new release
    subprocess.run(["git", "checkout", "-b", f"release-{NEXT_PATCH}"], check=True)

    print("Running bumpversion...")
    subprocess.run(["bumpversion", "--new-version", NEXT_PATCH, "patch"], check=True)

    print("Updating docs...")
    update_schema_doc()
    subprocess.run([os.path.join(REPO_ROOT, "scripts", "prepare-docs-for-release.sh"), NEXT_PATCH], check=True)

    # if local git state is not clean, await for user confirmation
    if not is_local_git_clean():
        print("Local git state is not clean. Please commit changes and press Enter to continue")
        input()
    # verify again that state is clean
    if not is_local_git_clean():
        print("Local git state is not clean. Aborting release")
        sys.exit(1)

    # open pr with gh cli
    print("Creating PR...")
    subprocess.run(["gh", "pr", "create", "--fill"], check=True)

    # check with user before merging
    print("Press Enter to merge the PR")
    input()

    # merge pr
    print("Merging PR...")
    subprocess.run(["gh", "pr", "merge", "--rebase", "-d"], check=True)

    # switch back to main and pull latest
    print("Switching to main branch...")
    subprocess.run(["git", "checkout", "main"], check=True)
    subprocess.run(["git", "pull", "origin", "main"], check=True)

    # create and push tag on main
    print("Creating and pushing tag...")
    subprocess.run(["git", "tag", f"v{NEXT_PATCH}"], check=True)
    subprocess.run(["git", "push", "origin", f"v{NEXT_PATCH}"], check=True)
