#!/bin/bash
# Scan error sources and output a summary.
# Used by the Stop hook to surface errors after every session.

cd "$(dirname "$0")/.." || exit 1

FOUND=0

# 1. Firebase debug log
if [ -f firebase-debug.log ]; then
    ERRORS=$(tail -100 firebase-debug.log | grep -ci 'error\|exception\|failed')
    if [ "$ERRORS" -gt 0 ]; then
        echo "--- firebase-debug.log: $ERRORS error lines (last 100) ---"
        tail -100 firebase-debug.log | grep -i 'error\|exception\|failed' | tail -5
        echo ""
        FOUND=1
    fi
fi

# 2. Any .log files in data/
for logfile in data/*.log; do
    [ -f "$logfile" ] || continue
    ERRORS=$(tail -100 "$logfile" | grep -ci 'error\|exception\|traceback\|failed')
    if [ "$ERRORS" -gt 0 ]; then
        echo "--- $logfile: $ERRORS error lines (last 100) ---"
        tail -100 "$logfile" | grep -i 'error\|exception\|traceback\|failed' | tail -5
        echo ""
        FOUND=1
    fi
done

# 3. Any .log files in .tmp/
for logfile in .tmp/*.log; do
    [ -f "$logfile" ] || continue
    ERRORS=$(tail -100 "$logfile" | grep -ci 'error\|exception\|traceback\|failed')
    if [ "$ERRORS" -gt 0 ]; then
        echo "--- $logfile: $ERRORS error lines (last 100) ---"
        tail -100 "$logfile" | grep -i 'error\|exception\|traceback\|failed' | tail -5
        echo ""
        FOUND=1
    fi
done

# 4. Python tracebacks in any log file
for logfile in *.log data/*.log .tmp/*.log; do
    [ -f "$logfile" ] || continue
    TB=$(tail -200 "$logfile" | grep -c 'Traceback (most recent call last)')
    if [ "$TB" -gt 0 ]; then
        echo "--- $logfile: $TB traceback(s) in last 200 lines ---"
        tail -200 "$logfile" | grep -A 5 'Traceback (most recent call last)' | tail -10
        echo ""
        FOUND=1
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "No errors in recent logs."
fi
