# .env.tpl - References 1Password secrets
# These are NOT actual secrets - they are references that 1Password CLI resolves at runtime
# Usage: op run --env-file=.env.tpl -- python tools/script.py

ANTHROPIC_API_KEY=op://Personal/SalesCoach/ANTHROPIC_API_KEY
AIRTABLE_API_KEY=op://Personal/SalesCoach/AIRTABLE_API_KEY
AIRTABLE_BASE_ID=op://Personal/SalesCoach/AIRTABLE_BASE_ID
AIRTABLE_TABLE_NAME=op://Personal/SalesCoach/AIRTABLE_TABLE_NAME
SERPER_API_KEY=op://Personal/SalesCoach/SERPER_API_KEY
