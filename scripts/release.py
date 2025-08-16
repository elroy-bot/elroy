#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

from semantic_version import Version

from elroy.tools.registry import get_system_tool_schemas

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(REPO_ROOT, "elroy", "__init__.py"), "r") as f:
    for line in f:
        if line.startswith("__version__"):
            current_version = line.split('"')[1]
            break
    else:
        raise ValueError("Version not found in __init__.py")


@dataclass
class Errors:
    messages: list[str]


def get_next_version(release_type: str) -> str:
    """Calculate the next version based on release type"""
    version = Version(current_version)
    if release_type == "major":
        return str(version.next_major())
    elif release_type == "minor":
        return str(version.next_minor())
    elif release_type == "patch":
        return str(version.next_patch())
    else:
        raise ValueError(f"Invalid release type: {release_type}")


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


def validate_docker_build(errors: Errors):
    print("Validating docker build...")
    try:
        # Create a unique tag for this validation run
        validation_tag = f"elroy-dev-validation-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # First build the image
        subprocess.run(
            [
                "docker",
                "build",
                "-f",
                os.path.join(REPO_ROOT, "Dockerfile.dev"),
                "-t",
                validation_tag,
                "--platform",
                "linux/arm64",
                "--no-cache",
                ".",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Run the container with --rm flag to remove it after execution
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/arm64",
                "-it",
                "-e",
                "OPENAI_API_KEY",
                validation_tag,
                "message",
                "--plain",
                "this is an automated system test, repeat after me: hello world",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Check if output contains "hello world" (case insensitive)
        if "hello world" not in result.stdout.lower():
            errors.messages.append(f"Error: Docker test message did not contain expected response. Output: {result.stdout.lower()}")

        # Clean up the image after testing
        subprocess.run(["docker", "rmi", validation_tag], check=False)

    except subprocess.CalledProcessError as e:
        errors.messages.append(f"Error: Docker build/run failed:\n{e.stdout}\n{e.stderr}")


def update_schema_doc():
    print("Updating schema documentation...")
    # Get the repository root directory
    schema_md_path = os.path.join(REPO_ROOT, "docs", "tools_schema.md")

    # Read the existing markdown file
    with open(schema_md_path, "r") as f:
        content = f.read()

    # Get schemas and sort by function name
    schemas = get_system_tool_schemas()
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
    print("ensuring changelog is up to date")
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


def handle_errors(errors):
    if errors.messages:
        print("\nErrors found:")
        for msg in errors.messages:
            print(f"  {msg}")
        response = input("\nDo you want to continue anyway? [y/N] ").lower()
        if response != "y":
            sys.exit(1)
        errors.messages.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Release a new version")
    parser.add_argument("release_type", choices=["major", "minor", "patch"], help="Type of release (major, minor, or patch)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-docker", action="store_true", help="Skip running docker build test")
    args = parser.parse_args()

    # Calculate next version
    next_version = get_next_version(args.release_type)
    print(f"Preparing {args.release_type} release: {current_version} -> {next_version}")

    errors = Errors([])
    print("Ensuring tags are consistent and up to date...")
    check_on_main_branch(errors)
    check_main_up_to_date(errors)
    check_pyproject_version_consistent(errors)
    check_bumpversion_config_consistent(errors)
    check_local_tag(errors)
    check_remote_tag_consistent(errors)
    check_most_recent_changelog_consistent(errors)

    handle_errors(errors)
    errors = Errors([])

    if args.skip_docker:
        print("Skipping docker build test")
    else:
        validate_docker_build(errors)

    handle_errors(errors)
    errors = Errors([])

    # checkout branch for new release
    subprocess.run(["git", "checkout", "-b", f"release-{next_version}"], check=True)

    print("Running bumpversion...")
    subprocess.run(["bumpversion", "--new-version", next_version, args.release_type], check=True)

    print("Updating docs...")
    update_schema_doc()

    repo_root = os.popen("git rev-parse --show-toplevel").read().strip()
    os.chdir(repo_root)

    # Call write_release_notes.sh script to generate changelog
    print("Generating release notes...")
    write_notes_script = os.path.join(os.path.dirname(__file__), "write_release_notes.sh")
    subprocess.run([write_notes_script, "--type", args.release_type], check=True)

    # if local git state is not clean, await for user confirmation
    if not is_local_git_clean():
        print("Documents have been updated. Please press Enter to continue")
        input()

    os.system("git add .")
    os.system(f"git commit -m 'Release {next_version}'")
    os.system("git push")

    # verify again that state is clean
    if not is_local_git_clean():
        print("Local git state is not clean. Aborting release")
        sys.exit(1)

    # open pr with gh cli
    print("Creating PR...")
    subprocess.run(["git", "push", "origin"], check=True)
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
    subprocess.run(["git", "tag", f"v{next_version}"], check=True)
    subprocess.run(["git", "push", "origin", f"v{next_version}"], check=True)
