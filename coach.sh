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
        op run --env-file=.env.tpl -- python3 tools/ask_coach.py "$@"
        ;;
    leaders)
        op run --env-file=.env.tpl -- python3 tools/search_leaders.py "$@"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Available: ask, leaders"
        exit 1
        ;;
esac
