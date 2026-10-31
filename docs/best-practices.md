# Claude Code Best Practices

Working principles for effective Claude Code sessions. Based on patterns from the Claude Code team, adapted for the WAT framework.

## Session Discipline

### Always Start in Plan Mode
Before writing any code, switch to Plan Mode (shift+tab twice in terminal, or toggle in VS Code). Go back and forth until the plan feels right. Only then switch to execution.

### Re-plan When Stuck
When something goes sideways mid-task, **stop pushing forward**. Switch back to Plan Mode and re-plan with what you now know. Don't stack fixes on top of fixes â€” that's how you end up with fragile code that nobody understands.

### One Task Per Session
Keep each Claude Code session focused on a single objective. If a new task comes up mid-session, note it and start a fresh session. This keeps the context window clean and prevents Claude from losing track of what it's doing.

## Prompting Patterns

### Challenge, Don't Just Instruct
Treat Claude Code as a peer who needs to justify their work, not an assistant who does what you say:

- **After implementation:** "Prove to me this works. Show me evidence."
- **After a mediocre fix:** "Knowing everything you know now, scrap this and implement the elegant solution."
- **Before committing:** "Grill me on these changes â€” what could go wrong?"
- **When exploring options:** "Read the relevant files and give me 3 options with tradeoffs before you build anything."

### Give Claude a Way to Verify Its Work
Always include a verification step. This 2-3x the quality of the result:

- "Run the app and confirm this works"
- "Write a test that proves this behavior"
- "Check the output and tell me if it looks right"
- For UI work: "Open the browser and visually verify"

Without a feedback loop, Claude is guessing. With one, it iterates to quality.

### Use Voice Dictation for Complex Prompts
Press fn twice on macOS to dictate. You speak 3x faster than you type, and your prompts naturally include more context and nuance. Especially useful for Plan Mode sessions where you're describing what you want to build.

## CLAUDE.md as Living Memory

### Update After Every Mistake
When Claude Code does something wrong, end the session with:
"Update CLAUDE.md so you don't make that mistake again."

Claude is surprisingly good at writing rules for itself. Over time, your CLAUDE.md becomes a set of battle-tested instructions that prevent repeat errors.

### Keep It Under 150 Lines
CLAUDE.md should contain only universally applicable information. Use progressive disclosure â€” point to files in `.claude/docs/` for specialized topics rather than cramming everything into the main file.

### Review and Prune Regularly
CLAUDE.md should evolve but not grow endlessly. Periodically review it and remove rules that are no longer relevant or that Claude has internalized through better patterns.

## The Self-Improvement Loop

After every session where something went wrong:

1. Identify what broke
2. Fix the tool or code
3. Verify the fix works
4. Update the workflow with the new approach
5. Update CLAUDE.md if it's a pattern Claude should always follow

This is how the WAT framework compounds â€” every failure makes the system stronger.

## Advanced Patterns

### Parallelization Across Projects
When running multiple Claude Code sessions across worktrees or branches (e.g., Sales Coach and Applo simultaneously), keep each session scoped to its own task. The isolation is the point â€” don't let sessions bleed context into each other. Use numbered terminal tabs or named tabs so you can quickly identify which project each session is working on.

### Subagents for Context Hygiene
For complex tasks, append "Use subagents" to your prompt. This tells Claude Code to spin up sub-tasks independently, keeping the main agent's context window clean and focused on orchestration.

When to use subagents:
- A task has multiple independent parts (e.g., "update the scraper AND redesign the dashboard")
- You want Claude to throw more compute at a problem without losing the main thread
- Long-running tasks where you want the main session to stay responsive

Think of it like delegation in the WAT framework â€” the main agent is the manager, subagents are the workers.

### Stop Hooks for Verification
For long-running tasks where you walk away, use a Stop hook to automatically verify Claude's work when it finishes. This is the automated version of "prove to me this works" â€” Claude runs its own QA check before calling the task done.

### Permission Management
In sandboxed environments or when you trust the session scope, use `--permission-mode=dontAsk` or enable Bypass Permissions in VS Code settings. This lets Claude cook without blocking on approval prompts. Only do this when you're confident in the task boundaries.
