#!/usr/bin/env bash

# Clone a repo, then ingest all of it's documents into memory.
# Elroy will:
#   Create memories based on the document contents (which can be synthesized and consolidated with other knowledge)
#   Retain the original content of the documents for traditional RAG

set -euo pipefail

pushd ./

# /tmp just as an example, directory should be wherever you keep other repos
cd /tmp

 if [ ! -d "elroy" ]; then
     git clone --branch stable --single-branch https://github.com/elroy-bot/elroy.git
 fi


cd elroy

git pull origin main

find . -name "*.md" -type f | xargs -I {} elroy ingest -f "{}"

# This will be relatively slow for the first run.
# In subsequent runs, if the documents are unchanged, they will be skipped.

popd
