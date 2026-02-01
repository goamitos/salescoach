#!/bin/bash
# run.sh - Runs pipeline with 1Password secrets injection
# Secrets are injected at runtime and never written to disk
#
# Usage:
#   ./run.sh collect_linkedin
#   ./run.sh process_content
#   ./run.sh push_airtable

set -e

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if script name was provided
if [ -z "$1" ]; then
    echo "Usage: ./run.sh <script_name>"
    echo "Available scripts:"
    ls tools/*.py | xargs -n1 basename | sed 's/.py$//'
    exit 1
fi

# Check if the script exists
if [ ! -f "tools/$1.py" ]; then
    echo "Error: tools/$1.py not found"
    echo "Available scripts:"
    ls tools/*.py | xargs -n1 basename | sed 's/.py$//'
    exit 1
fi

# Run with secrets injected via 1Password CLI
echo "Running tools/$1.py with 1Password secrets..."
op run --account=my.1password.com --env-file=.env.tpl -- python tools/$1.py
