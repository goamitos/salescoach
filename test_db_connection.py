#!/usr/bin/env python3
"""Test database connection to debug the issue"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.data import load_insights, _get_db_connection, DB_PATH

print(f"DB_PATH: {DB_PATH}")
print(f"DB exists: {DB_PATH.exists()}")
print(f"DB is file: {DB_PATH.is_file()}")

if DB_PATH.exists():
    print(f"DB size: {DB_PATH.stat().st_size} bytes")

print("\n--- Testing connection ---")
conn = _get_db_connection()
if conn:
    print("✅ Connection successful!")
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM insights")
        count = cursor.fetchone()[0]
        print(f"✅ Found {count} insights in database")
        conn.close()
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        conn.close()
else:
    print("❌ Connection failed - database not found")

print("\n--- Testing load_insights() ---")
try:
    insights = load_insights()
    print(f"Loaded {len(insights)} insights")
    if insights:
        print(f"First insight: {insights[0].get('key_insight', '')[:100]}...")
    else:
        print("⚠️  No insights loaded!")
except Exception as e:
    print(f"❌ Error loading insights: {e}")
    import traceback
    traceback.print_exc()
