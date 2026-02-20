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

# Load secrets: prefer 1Password CLI, fall back to macOS Keychain
load_keychain_secrets() {
    KEYS="ANTHROPIC_API_KEY AIRTABLE_API_KEY AIRTABLE_BASE_ID AIRTABLE_TABLE_NAME SERPER_API_KEY YOUTUBE_API_KEY DECODO_PROXY_URL"
    for key in $KEYS; do
        if [ -z "${!key}" ]; then
            val=$(security find-generic-password -s "$key" -w 2>/dev/null || true)
            if [ -n "$val" ]; then
                export "$key=$val"
            fi
        fi
    done
}

# Run a command with secrets injected (1Password or Keychain)
run_with_secrets() {
    if command -v op &>/dev/null; then
        op run --env-file=.env.tpl -- "$@"
    else
        load_keychain_secrets
        "$@"
    fi
}

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
    echo "Starting Streamlit..."
    run_with_secrets streamlit run streamlit_app.py
    exit 0
fi

# Handle claude specially (needs PTY for interactive mode)
if [ "$1" = "claude" ]; then
    echo "Starting Claude Code with secrets..."
    load_keychain_secrets
    if command -v op &>/dev/null; then
        export ANTHROPIC_API_KEY="$(op read 'op://SalesCoach/SalesCoach/ANTHROPIC_API_KEY')"
        export AIRTABLE_API_KEY="$(op read 'op://SalesCoach/SalesCoach/AIRTABLE_API_KEY')"
        export AIRTABLE_BASE_ID="$(op read 'op://SalesCoach/SalesCoach/AIRTABLE_BASE_ID')"
        export AIRTABLE_TABLE_NAME="$(op read 'op://SalesCoach/SalesCoach/AIRTABLE_TABLE_NAME')"
        export SERPER_API_KEY="$(op read 'op://SalesCoach/SalesCoach/SERPER_API_KEY')"
    fi
    exec claude "${@:2}"
fi

# Check if the script exists
if [ ! -f "tools/$1.py" ]; then
    echo "Error: tools/$1.py not found"
    echo "Available scripts:"
    ls tools/*.py | xargs -n1 basename | sed 's/.py$//'
    exit 1
fi

# Run with secrets injected
echo "Running tools/$1.py..."
run_with_secrets python3 tools/$1.py "${@:2}"
