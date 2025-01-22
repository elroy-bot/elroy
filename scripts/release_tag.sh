#!/bin/bash
set -e

# Check if tag argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <tag>"
    exit 1
fi

TAG=$1

# Check if tag exists
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Error: Tag $TAG does not exist"
    exit 1
fi

# Get the most recent tag
LATEST_TAG=$(git describe --tags --abbrev=0)

# Check if given tag is the most recent
if [ "$TAG" != "$LATEST_TAG" ]; then
    echo "Error: $TAG is not the most recent tag (latest is $LATEST_TAG)"
    exit 1
fi

# Delete tag locally and remotely
echo "Deleting tag $TAG locally and remotely..."
git tag -d "$TAG"
git push origin ":refs/tags/$TAG"

# Get current main head
MAIN_HEAD=$(git rev-parse main)

# Reapply tag to current main head
echo "Reapplying tag $TAG to current main head..."
git tag "$TAG" "$MAIN_HEAD"
git push origin "$TAG"

echo "Successfully reapplied tag $TAG to main head"

