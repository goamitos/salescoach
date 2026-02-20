#!/bin/bash
# coach — Unified CLI for Sales Coach AI
#
# Usage:
#   coach ask "question"                    # General Q&A
#   coach leaders "query"                   # Search VP/CRO content
#   coach leaders --ask "question"          # AI-synthesized leadership advice

set -e
cd "$(dirname "$0")"

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load secrets: prefer 1Password CLI, fall back to macOS Keychain
load_secrets() {
    if command -v op &>/dev/null; then
        return 0  # op available — will use op run below
    fi

    # Fall back to macOS Keychain
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

# Run a command with secrets injected
run_with_secrets() {
    if command -v op &>/dev/null; then
        op run --env-file=.env.tpl -- "$@"
    else
        load_secrets
        "$@"
    fi
}

if [ -z "$1" ]; then
    echo "Usage: coach <command> [options] <query>"
    echo ""
    echo "Commands:"
    echo "  ask        General sales coaching Q&A"
    echo "  leaders    Search VP/CRO leadership content"
    echo ""
    echo "Examples:"
    echo "  coach ask 'how to handle objections'"
    echo "  coach leaders 'pipeline review cadence'"
    echo "  coach leaders --ask 'first 90 days as CRO'"
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    ask)
        run_with_secrets python3 tools/ask_coach.py "$@"
        ;;
    leaders)
        run_with_secrets python3 tools/search_leaders.py "$@"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available: ask, leaders"
        exit 1
        ;;
esac
