#!/bin/bash
# run.sh - Runs pipeline with 1Password secrets injection
# Secrets are injected at runtime and never written to disk
#
# Usage:
#   ./run.sh collect_linkedin
#   ./run.sh process_content
#   ./run.sh push_airtable
#   ./run.sh streamlit          # Run Streamlit web app

set -e

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if script name was provided
if [ -z "$1" ]; then
    echo "Usage: ./run.sh <script_name>"
    echo ""
    echo "Available scripts:"
    ls tools/*.py | xargs -n1 basename | sed 's/.py$//'
    echo ""
    echo "Special commands:"
    echo "  streamlit    - Run the Streamlit web app"
    echo "  claude       - Start Claude Code with secrets injected"
    exit 1
fi

# Handle streamlit specially
if [ "$1" = "streamlit" ]; then
    echo "Starting Streamlit with 1Password secrets..."
    op run --env-file=.env.tpl -- streamlit run streamlit_app.py
    exit 0
fi

# Handle claude specially (needs PTY for interactive mode)
if [ "$1" = "claude" ]; then
    echo "Starting Claude Code with 1Password secrets..."
    # Export secrets directly using op read (op run doesn't provide proper TTY)
    # Note: Secrets exported this way are visible in process listings (ps eww).
    # This is an acceptable tradeoff for Claude Code's TTY requirement.
    # Secrets are short-lived in memory and cleared when the shell exits.
    export ANTHROPIC_API_KEY="$(op read 'op://SalesCoach/SalesCoach/ANTHROPIC_API_KEY')"
    export AIRTABLE_API_KEY="$(op read 'op://SalesCoach/SalesCoach/AIRTABLE_API_KEY')"
    export AIRTABLE_BASE_ID="$(op read 'op://SalesCoach/SalesCoach/AIRTABLE_BASE_ID')"
    export AIRTABLE_TABLE_NAME="$(op read 'op://SalesCoach/SalesCoach/AIRTABLE_TABLE_NAME')"
    export SERPER_API_KEY="$(op read 'op://SalesCoach/SalesCoach/SERPER_API_KEY')"
    exec claude "${@:2}"
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
op run --env-file=.env.tpl -- python3 tools/$1.py "${@:2}"
