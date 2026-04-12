# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangGraph-based autonomous Python coding agent. Takes a natural language goal and iterates through a plan → code → test → fix loop until working code is produced.

## Architecture

- **Graph**: LangGraph StateGraph with 5 nodes: `goal_analyzer` → `planner` → `coder` → `tester` → `fixer`, where `fixer` loops back to `planner` on failure
- **State**: Shared `TypedDict` carrying goal, plan, files, error info, and iteration count
- **Tools**: File operations (`write_file`, `read_file`, `apply_patch`, `list_files`), plan operations (`write_plan_md`), and execution (`run_command` via subprocess with 30s timeout)
- **Prompts**: Stored as text files in `prompts/` directory, one per node
- **Workspace**: Agent-generated code goes into `workspace/` directory

## Key Design Decisions

- Error classification is priority-based: syntax → import → test_fail → runtime → logic → none
- Each iteration limits changes to max 3 files to prevent cascading rewrites
- `apply_patch` (string replacement) is preferred over full file rewrites for stability
- Max 5 iterations by default to prevent infinite loops

## Commands

```bash
pip install -r requirements.txt
pytest tests/ -v
python main.py  # CLI entry point
```
