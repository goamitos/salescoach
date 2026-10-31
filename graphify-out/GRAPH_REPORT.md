# Graph Report - salescoach  (2026-10-31)

## Corpus Check
- 94 files · ~165,445 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: .toml 2, .graphify-bak 1, .example 1)

## Summary
- 1228 nodes · 2315 edges · 77 communities (57 shown, 20 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 198 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9e3d5a03`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Connection
- Content Processing Workflow
- find_advice Contract Tests
- Expert Directory Builder
- Insight and Methodology Cards
- SQLite DB Layer
- LinkedIn Collection and Config
- Registry Consistency Tests
- Expert Cards and Profiles
- Avatar Generation
- Persona Generation
- config.py
- Coach Chat AI Prompts
- test_personas.py
- Airtable Data Loading
- insight_card.py
- Audience Classification
- db.py
- CLI Ask Coach
- Weekly LinkedIn Action
- Persona Schema Tests
- Leader Search
- YouTube Transcript Collection
- Persona Prompt Tests
- Advice Schema Tests
- test_streamlit_helpers.py
- YouTube Pipeline Updater
- Advice Migration Idempotency
- Stage Filter Pills
- Content Processing
- Registry Field Tests
- Airtable Push
- Sales Coach
- Gene Grosser Transcripts
- Persona RAG Helpers
- Schema Version Tests
- Persona Prompt Builder
- _make_insight
- Persona Validator Tests
- PR Analysis Features
- record_tagged
- Shell Secret Runners
- Leadership Hub Plan Tasks
- Bites Founders Podcast
- Registry Uniqueness Tests
- upsert_insight
- Architecture and Testing Notes
- Expert Groups
- Airtable Setup Guide
- Pre-commit Config
- Registry Test Fixtures
- LinkedIn Registry Tests
- New Experts Tests
- Registry Structure Tests
- content_hash
- Claude Code Best Practices
- Browser Tests
- Tag Cache Fixtures
- test_find_advice.py
- backfill_methodology_tags.py
- Sales Coach Project
- VP/CRO Hub Docs
- Audience Classification Fields
- Error Scan Script
- export_airtable.py
- Sales Coach README
- _add
- streamlit_app.py
- requests
- post-merge-validator Agent
- LinkedIn Content Collection Workflow
- TestGapTypes
- .test_stores_correct_values

## God Nodes (most connected - your core abstractions)
1. `content_hash()` - 37 edges
2. `get_connection()` - 33 edges
3. `record_tagged()` - 27 edges
4. `_make_insight()` - 24 edges
5. `init_db()` - 24 edges
6. `load_insights()` - 20 edges
7. `main()` - 19 edges
8. `build_persona_system_prompt()` - 19 edges
9. `get_anthropic_key()` - 18 edges
10. `backfill_tags()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Four-Step Pipeline Usage` --semantically_similar_to--> `Pipeline Architecture (collect, process, push)`  [INFERRED] [semantically similar]
  README.md → files/SPEC.md
- `Airtable Data Schema` --semantically_similar_to--> `Airtable CSV Schema`  [INFERRED] [semantically similar]
  CLAUDE.md → workflows/04_airtable_export.md
- `Relevance Quality Thresholds (7 / 5-6 / <5)` --semantically_similar_to--> `Content Processing Rules (model, rate limit, score >= 7)`  [INFERRED] [semantically similar]
  workflows/03_content_processing.md → CLAUDE.md
- `graphify Knowledge Graph Rules` --semantically_similar_to--> `graphify Skill Trigger (/graphify)`  [INFERRED] [semantically similar]
  CLAUDE.md → .claude/CLAUDE.md
- `Give Claude a Way to Verify Its Work` --semantically_similar_to--> `Test Strategy (unit, integration, full)`  [INFERRED] [semantically similar]
  files/best-practices.md → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Bite full learning cycle (story, question, summary, discussion)** — docs_yt_learning_sharks_bites_founders_bite_structure, docs_yt_learning_sharks_bites_founders_three_pillars, docs_yt_learning_sharks_bites_founders_two_way_feedback [EXTRACTED 1.00]
- **Four-Stage Content Pipeline Workflows** — workflows_01_linkedin_collection, workflows_02_youtube_collection, workflows_03_content_processing, workflows_04_airtable_export [EXTRACTED 1.00]
- **GTM engineering agents (lead agent, dealbot, GTM engineer)** — docs_yt_transcripts_2videos_gtm_engineer, docs_yt_transcripts_2videos_lead_agent, docs_yt_transcripts_2videos_dealbot [EXTRACTED 1.00]
- **Three PRs transforming Sales Coach into a production multipage app** — docs_pr_analysis_report_pr2_ai_personas, docs_pr_analysis_report_pr3_multipage_refactor, docs_pr_analysis_report_pr4_sqlite_migration [EXTRACTED 1.00]
- **Working Principles and Best Practices** — files_best_practices_plan_mode, files_best_practices_self_improvement_loop, files_best_practices_verification, claude_wat_architecture [INFERRED 0.75]
- **Project Guardrail Agents and Test Strategy** — _claude_agents_cost_auditor, _claude_agents_post_merge_validator, claude_test_strategy [INFERRED 0.75]
- **VP/CRO audience classification flow** — docs_plans_2026_02_20_vp_cro_content_hub_plan_migrate_audience_columns, tools_classify_audience, docs_plans_2026_02_20_vp_cro_content_hub_plan_search_leaders_db, docs_plans_2026_02_20_vp_cro_content_hub_plan_forward_integration [INFERRED 0.85]
- **VP/CRO hub access surfaces (CLI and Streamlit)** — docs_plans_2026_02_20_vp_cro_content_hub_plan_search_leaders_cli, docs_plans_2026_02_20_vp_cro_content_hub_plan_coach_sh, docs_plans_2026_02_20_vp_cro_content_hub_plan_leaders_page [INFERRED 0.85]

## Communities (77 total, 20 thin omitted)

### Community 0 - "Connection"
Cohesion: 0.13
Nodes (3): TestEnsureTagCacheTable, TestSelectForTagging, select_for_tagging()

### Community 1 - "Content Processing Workflow"
Cohesion: 0.19
Nodes (14): Airtable Data Schema, Content Processing Rules (model, rate limit, score >= 7), Pipeline Architecture (collect, process, push), Four-Step Pipeline Usage, YouTube Content Collection Workflow, Transcript Chunking Strategy (~500 words, 50 overlap), .tmp/youtube_raw.json output, Content Processing Workflow (+6 more)

### Community 2 - "find_advice Contract Tests"
Cohesion: 0.09
Nodes (8): TestCuratedRanking, TestGapFiltering, TestKCap, TestOutputFields, TestSchemaVersionGuard, TestSourceClassFilter, _build_fts_query(), find_advice()

### Community 3 - "Expert Directory Builder"
Cohesion: 0.07
Nodes (19): build_experts_md(), count_target_videos(), fetch_airtable_stats(), load_experts(), main(), push_expert_directory(), _push_to_table(), api_call() (+11 more)

### Community 4 - "Insight and Methodology Cards"
Cohesion: 0.09
Nodes (15): insight_card_html(), methodology_card_html(), methodology_component_detail_html(), main(), _render_insights_browser(), _render_methodology_explorer(), show_component(), filter_insights() (+7 more)

### Community 5 - "SQLite DB Layer"
Cohesion: 0.14
Nodes (10): conn(), get_connection(), get_stats(), init_db(), migrate_audience_columns(), upsert_component(), upsert_methodology(), push_to_sqlite() (+2 more)

### Community 6 - "LinkedIn Collection and Config"
Cohesion: 0.12
Nodes (9): _build_influencer_list(), build_influencer_queries(), collect_posts(), fetch_post_preview(), _fetch_url(), search_serper(), _serper_request(), get_random_user_agent() (+1 more)

### Community 7 - "Registry Consistency Tests"
Cohesion: 0.06
Nodes (10): active_names(), active_slugs(), avatar_files(), avatar_script_slugs(), linkedin_names(), registry_data(), TestAvatarFiles, TestAvatarScriptConsistency (+2 more)

### Community 8 - "Expert Cards and Profiles"
Cohesion: 0.12
Nodes (14): expert_card_html(), expert_profile_html(), _render_coaching_mode(), _render_context_bar(), _render_expert_selector(), main(), _render_expert_grid(), show_profile() (+6 more)

### Community 9 - "Avatar Generation"
Cohesion: 0.10
Nodes (5): TestGetInitials, _build_influencer_list(), create_avatar(), get_initials(), main()

### Community 10 - "Persona Generation"
Cohesion: 0.10
Nodes (14): aggregate_per_expert(), assemble_personas(), build_batch_requests(), _build_content_samples(), compute_confidence(), fetch_airtable_records(), load_influencers(), load_raw_content() (+6 more)

### Community 11 - "config.py"
Cohesion: 0.16
Nodes (5): get_anthropic_key(), build_prompt(), generate_all(), generate_content(), list_existing()

### Community 12 - "Coach Chat AI Prompts"
Cohesion: 0.09
Nodes (16): main(), _process_message(), _render_header(), _render_stage_summary(), _render_welcome_state(), _build_general_prompt(), _build_persona_prompt(), generate_conversation_title() (+8 more)

### Community 13 - "test_personas.py"
Cohesion: 0.06
Nodes (18): tmp_data(), influencers(), low_confidence_persona(), personas(), personas_data(), sample_persona(), TestPersonaCoverage, TestParseArgs (+10 more)

### Community 14 - "Airtable Data Loading"
Cohesion: 0.09
Nodes (12): _get_airtable_secrets(), _get_db_connection(), get_influencer_details(), get_leader_stats(), get_methodology(), load_insights(), _load_insights_airtable(), _load_insights_sqlite() (+4 more)

### Community 15 - "insight_card.py"
Cohesion: 0.21
Nodes (4): render_chat_messages(), methodology_tag_html(), source_card_html(), get_methodology_color()

### Community 16 - "Audience Classification"
Cohesion: 0.11
Nodes (11): Forward integration into process_content.py, conn(), db(), TestBuildPrompt, TestParseResponse, build_classification_prompt(), classify_all(), _max_items_arg() (+3 more)

### Community 17 - "db.py"
Cohesion: 0.12
Nodes (6): conn(), db(), get_insights_by_methodology(), get_tags_for_insights(), search_insights(), tag_insight_methodology()

### Community 18 - "CLI Ask Coach"
Cohesion: 0.15
Nodes (9): build_context(), fetch_records(), find_relevant_records(), get_coaching_advice(), main(), print_sources(), score_record(), load_influencer_meta() (+1 more)

### Community 19 - "Weekly LinkedIn Action"
Cohesion: 0.10
Nodes (20): runs-on, steps, AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, ANTHROPIC_API_KEY, SERPER_API_KEY, jobs (+12 more)

### Community 21 - "Leader Search"
Cohesion: 0.16
Nodes (6): _make_insight(), TestSearchLeaders, search_leaders(), display_results(), main(), synthesize_answer()

### Community 22 - "YouTube Transcript Collection"
Cohesion: 0.14
Nodes (6): chunk_transcript(), collect_transcripts(), _fetch_transcript(), get_existing_video_urls(), get_transcript(), _load_target_videos()

### Community 24 - "Advice Schema Tests"
Cohesion: 0.22
Nodes (3): _make_minimal_insight(), TestColumnDefaults, TestNewColumnsPresent

### Community 25 - "test_streamlit_helpers.py"
Cohesion: 0.05
Nodes (10): format_followers(), get_influencer_details(), get_influencer_name(), influencers(), load_influencers_from_registry(), TestFormatFollowers, TestGetInfluencerDetails, TestGetInfluencerName (+2 more)

### Community 26 - "YouTube Pipeline Updater"
Cohesion: 0.16
Nodes (6): discover_new_videos(), fetch_channel_videos(), get_existing_video_urls(), main(), run_pipeline(), update_collect_youtube()

### Community 27 - "Advice Migration Idempotency"
Cohesion: 0.17
Nodes (4): conn(), db(), TestIdempotency, migrate_advice_columns()

### Community 28 - "Stage Filter Pills"
Cohesion: 0.16
Nodes (6): stage_badge_html(), stage_group_options(), stage_option_to_value(), value_to_stage_option(), _render_filters(), get_stage_color()

### Community 29 - "Content Processing"
Cohesion: 0.21
Nodes (4): build_batch_requests(), load_collected_content(), load_existing_processed(), process_all_content()

### Community 31 - "Airtable Push"
Cohesion: 0.19
Nodes (5): format_list_field(), format_multiline_field(), push_to_airtable(), sanitize_stage(), _slugify()

### Community 32 - "Sales Coach"
Cohesion: 0.07
Nodes (28): AI-Powered Q&A, Airtable Interface (Browse Mode), CLI Tool, Commands, Content Processing, Data Schema (Airtable), Deal Stages (for categorization), Demo Questions (+20 more)

### Community 33 - "Gene Grosser Transcripts"
Cohesion: 0.18
Nodes (10): YouTube transcripts: two Gene Grosser videos, Driver trees and lead-to-revenue model, Video 1: What makes an extraordinary scale-up executive (cHp7HqUfBe0), Executive interview process with workshop prompts, Gene Grosser (COO at Vercel, ex-Stripe), Go-to-market as a product (whiteboard discovery, value at every touchpoint), Video 2: Go-to-market masterclass on Lenny's Podcast (RmnWHz8HD74), PLG ceiling, pricing as product, sales comp and hiring profiles (+2 more)

### Community 34 - "Persona RAG Helpers"
Cohesion: 0.16
Nodes (3): TestRAGHelpers, adjust_top_n(), build_persona_context_prefix()

### Community 35 - "Schema Version Tests"
Cohesion: 0.17
Nodes (3): TestSchemaVersion, get_schema_version(), set_schema_version()

### Community 36 - "Persona Prompt Builder"
Cohesion: 0.17
Nodes (5): _build_confidence_modifier(), _build_framework_section(), _build_instructions(), _build_phrase_section(), _build_voice_section()

### Community 37 - "_make_insight"
Cohesion: 0.12
Nodes (3): _make_insight(), TestContentHash, TestSeedFromExisting

### Community 38 - "Persona Validator Tests"
Cohesion: 0.15
Nodes (3): TestUIHelpers, get_persona_info(), validate_persona()

### Community 39 - "PR Analysis Features"
Cohesion: 0.24
Nodes (8): Expert slug identifiers, PR Analysis Report (PRs #2-#4), Methodology Explorer (10 methodologies, 41 components), PR #2 AI Persona System (48 experts), PR #3 Multipage Streamlit Refactor, PR #4 SQLite Migration with FTS5, Sales methodologies (MEDDIC, SPIN, Challenger, Gap Selling, etc.), URL deep linking (expert, stage, methodology params)

### Community 40 - "record_tagged"
Cohesion: 0.14
Nodes (5): TestNeedsRetag, TestTaggerNamespace, needs_retag(), record_tagged(), seed_from_existing()

### Community 41 - "Shell Secret Runners"
Cohesion: 0.36
Nodes (6): load_secrets(), run_with_secrets(), coach.sh script, load_keychain_secrets(), run_with_secrets(), run.sh script

### Community 42 - "Leadership Hub Plan Tasks"
Cohesion: 0.22
Nodes (9): coach CLI command, Streamlit Leadership Hub tab, coach.sh CLI entry point, Task 1: DB Schema Migration, pages/4_leaders.py Leadership Hub page, load_leader_insights / get_leader_stats, migrate_audience_columns, search_leaders.py CLI (+1 more)

### Community 43 - "Bites Founders Podcast"
Cohesion: 0.25
Nodes (7): Stage summaries via Claude Haiku synthesis, Learning Sharks Podcast with Bites founders Eran and Tal, Bite structure: story, question, summary, discussion, Bites frontline micro-learning platform, COVID government agency 48-hour rollout use case, Bites three pillars: creation app, instant-messaging delivery, monitoring, Two-way comment threads and personal knowledge feed

### Community 45 - "upsert_insight"
Cohesion: 0.14
Nodes (7): TestAudienceColumns, upsert_insight(), map_airtable_record(), migrate(), parse_bullet_field(), parse_csv_field(), slugify()

### Community 46 - "Architecture and Testing Notes"
Cohesion: 0.25
Nodes (7): Sales Coach pipeline architecture (collect, Claude analysis, Airtable, Q&A), Stop hooks for automated verification, FTS5 search_insights_fts empty methodology_tags bug, Recommended 58-case testing plan, Dealbot / Lostbot built on Gong transcripts, Go-to-market engineer role (agents for GTM workflows), Inbound lead agent (10 SDRs reduced to 1 reviewer)

### Community 47 - "Expert Groups"
Cohesion: 0.32
Nodes (8): Expert Directory (51 total), Company profiles (30MPC, Gong.io, Pavilion), Monday CRM Top 25 experts group, Original 16 experts group, Proposify Best Sales Voices experts group, Sales Coach Influencers, 30MPC podcast (Armand Farrokh and Nick Cegelski), Avatar sourcing convention (assets/avatars/{slug}.png)

### Community 48 - "Airtable Setup Guide"
Cohesion: 0.38
Nodes (7): Airtable Setup Guide, Ask the Coach Q&A tools (CLI and Streamlit), Interview demo script, Airtable Interface (Browse Mode), Sales Wisdom Airtable table schema, Streamlit Cloud deployment with secrets, Expert corpus stats (1893 insights, 1000 LinkedIn posts, 588 videos)

### Community 49 - "Pre-commit Config"
Cohesion: 0.29
Nodes (6): id, language_version, repos, hooks, repo, rev

### Community 50 - "Registry Test Fixtures"
Cohesion: 0.43
Nodes (4): active_influencers(), company_influencers(), influencers(), registry()

### Community 54 - "content_hash"
Cohesion: 0.24
Nodes (7): _add(), _row(), _tags(), TestSelectInsights, TestWriteInsightTags, write_insight_tags(), content_hash()

### Community 55 - "Claude Code Best Practices"
Cohesion: 0.47
Nodes (4): Claude Code Best Practices, Challenge, don't just instruct (prompting patterns), Self-improvement loop (WAT framework), Subagents for context hygiene

### Community 58 - "test_find_advice.py"
Cohesion: 0.18
Nodes (6): conn(), db(), _minimal_insight(), seeded_conn(), _set_extras(), TestContractVersion

### Community 59 - "backfill_methodology_tags.py"
Cohesion: 0.18
Nodes (9): _arg_value(), backfill_tags(), build_batch_requests(), build_components_list(), _load_all_insights(), seed_cache(), select_insights(), get_methodology_tree() (+1 more)

### Community 60 - "Sales Coach Project"
Cohesion: 0.24
Nodes (8): graphify Skill Trigger (/graphify), graphify Knowledge Graph Rules, Sales Coach Project, Weekly GitHub Actions Automation, Bug and Issue Backlog, test_consistency.py AST parsing fix, Architecture Spec, TODO Backlog

### Community 64 - "export_airtable.py"
Cohesion: 0.31
Nodes (3): export_to_csv(), format_list_field(), format_multiline_field()

### Community 69 - "Sales Coach README"
Cohesion: 0.29
Nodes (8): Ask the Coach Q&A (CLI and Streamlit), 15 Deal Stages, Sidebar Stage Groups, Migrate to pyproject.toml, 13 Sales Influencers, Sales Coach README, Streamlit Cloud Deployment, requirements.txt Python Dependencies

### Community 70 - "_add"
Cohesion: 0.46
Nodes (3): _add(), _row(), TestSelectInsights

### Community 73 - "post-merge-validator Agent"
Cohesion: 0.40
Nodes (3): post-merge-validator Agent, Test Strategy (unit, integration, full), Claude Code Best Practices

### Community 74 - "LinkedIn Content Collection Workflow"
Cohesion: 0.40
Nodes (3): LinkedIn Content Collection Workflow, Google X-ray Search Pattern, .tmp/linkedin_raw.json output

## Knowledge Gaps
- **31 isolated node(s):** `Bites three pillars: creation app, instant-messaging delivery, monitoring`, `Two-way comment threads and personal knowledge feed`, `Learning Sharks Podcast with Bites founders Eran and Tal`, `Weekly GitHub Actions Automation`, `13 Sales Influencers` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 524 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Sales Coach README` connect `Sales Coach README` to `Content Processing Workflow`, `Expert Groups`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `content_hash()` (e.g. with `.test_audience_cache_rows_do_not_count()` and `.test_edited_insight_is_selected_again()`) actually correct?**
  _`content_hash()` has 27 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Bites three pillars: creation app, instant-messaging delivery, monitoring`, `Two-way comment threads and personal knowledge feed`, `Learning Sharks Podcast with Bites founders Eran and Tal` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Connection` be split into smaller, more focused modules?**
  _Cohesion score 0.12807881773399016 - nodes in this community are weakly interconnected._
- **Why does `Sales Coach Influencers` connect `Expert Groups` to `Sales Coach README`, `PR Analysis Features`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `get_connection()` (e.g. with `conn()` and `.test_second_call_leaves_columns_unchanged()`) actually correct?**
  _`get_connection()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `find_advice Contract Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.08870967741935484 - nodes in this community are weakly interconnected._