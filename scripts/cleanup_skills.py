#!/usr/bin/env python3
"""Delete skills irrelevant to the PLC/AI project."""
import sys, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SKILLS_DIR = Path.home() / ".claude" / "skills"

KEEP = {
    "python-patterns", "python-testing", "coding-standards",
    "gxworks2", "mcp-builder", "docker-patterns",
    "tdd-workflow", "eval-harness", "e2e-testing", "ai-regression-testing",
    "security-review", "security-scan", "safety-guard",
    "search-first", "deep-research", "exa-search", "iterative-retrieval",
    "handoff", "diagnose", "triage", "to-issues", "to-prd",
    "find-skills", "skill-creator", "zoom-out",
    "prompt-optimizer", "grill-with-docs", "prototype",
    "database-migrations", "postgres-patterns",
    "pdf", "docx", "pptx", "xlsx",
    "claude-api", "claude-devfleet", "continuous-learning-v2",
    "autonomous-loops", "agentic-engineering", "ai-first-engineering",
    "agent-harness-construction", "dmux-workflows", "enterprise-agent-ops",
    "caveman", "NoPUA-skill", "latency-critical-systems",
    "update-config", "simplify", "improve-codebase-architecture",
    "configure-ecc", "skill-stocktake", "workspace-surface-audit",
    "ui-demo", "cost-aware-llm-pipeline", "content-hash-cache-pattern",
    "production-audit", "project-flow-ops",
    "jira-integration", "google-workspace-ops",
    "nanoclaw-repl", "regex-vs-llm-structured-text",
    "kimi-webbridge",
    "网页作业自动答题", "网页作业自动答题（需要VL版本）",
    "frontend-slides",
}

all_dirs = set(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())
to_delete = all_dirs - KEEP - {"superpowers", "document-SKILLs", "setup-matt-pocock-skills"}

deleted = 0
for name in sorted(to_delete):
    path = SKILLS_DIR / name
    shutil.rmtree(path, ignore_errors=True)
    print(f"DEL {name}")
    deleted += 1

print(f"\nDone. Deleted {deleted} skills, kept {len(KEEP)}, remaining: {len(all_dirs) - deleted}")
