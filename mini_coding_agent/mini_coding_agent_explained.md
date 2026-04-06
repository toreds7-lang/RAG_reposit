# mini_coding_agent.py — A Beginner's Deep Dive

> **Who this is for:** Python beginners who want to understand how an AI "coding agent" works from the inside out. You should be comfortable reading Python, but you don't need any prior AI or ML experience.

---

## Table of Contents

1. [What is a Coding Agent?](#1-what-is-a-coding-agent)
2. [Big Picture: The Six Components](#2-big-picture-the-six-components)
3. [Component Walkthroughs](#3-component-walkthroughs)
   - [3a. Workspace Context](#3a-workspace-context--workspacecontext-lines-92160)
   - [3b. Prompt Shaping](#3b-prompt-shaping--build_prefix-memory_text-prompt-lines-334440)
   - [3c. Tools & Permissions](#3c-tools--permissions--build_tools-run_tool-validate_tool-approve-lines-283625)
   - [3d. Context Reduction](#3d-context-reduction--clip-history_text-lines-7175-398422)
   - [3e. Session Memory & The Agent Loop](#3e-session-memory--the-agent-loop--sessionstore-record-note_tool-ask-lines-165503)
   - [3f. Delegation](#3f-delegation--tool_delegate-lines-859878)
4. [Full End-to-End Example](#4-full-end-to-end-example)
5. [Key Design Decisions](#5-key-design-decisions)
6. [Glossary for Beginners](#6-glossary-for-beginners)

---

## 1. What is a Coding Agent?

A regular **chatbot** answers questions. You send a message, it sends back text. That's it.

A **coding agent** is different. It can *take actions* — read files, run commands, write code — and it keeps looping until the task is done. Think of it like the difference between asking a friend "how do I sort a list?" versus hiring a contractor who actually goes and sorts the list for you.

The three things that make an agent an agent:

```
  You (user)
      |
      v
  [Agent] <------- has TOOLS (read files, run shell, write code)
      |
      v
  [AI Model] <---- the "brain" that decides what to do next
      |
      v
  Tool result fed back to model → loop until done
```

The key insight: **the AI model doesn't have to know everything — it just has to know which tool to call next.** The agent runs that tool and shows the result back to the model. This Think → Act → Observe cycle repeats until the model says "I'm done."

---

## 2. Big Picture: The Six Components

The file is organized around **six distinct responsibilities**, documented at [mini_coding_agent.py:56-63](mini_coding_agent.py#L56-L63):

```
# 1) Live Repo Context         → WorkspaceContext
# 2) Prompt Shape And Cache    → build_prefix, memory_text, prompt
# 3) Structured Tools          → build_tools, run_tool, validate_tool, approve
# 4) Context Reduction         → clip, history_text
# 5) Transcripts & Memory      → SessionStore, record, note_tool, ask
# 6) Delegation                → tool_delegate
```

Here's how they interact:

```
┌──────────────────────────────────────────────────────────────┐
│                         MiniAgent                            │
│                                                              │
│  [1] WorkspaceContext ──► [2] build_prefix()                 │
│           (git info)          (system prompt)                │
│                                                              │
│  [4] clip/history_text ──► [2] prompt()                      │
│      (shrink old history)      (full prompt = prefix +       │
│                                 memory + history + request)  │
│                                                              │
│  [2] prompt ──► OpenAI API ──► raw response text             │
│                                                              │
│  parse() ──► [3] run_tool() ──► result                       │
│                 (validate, approve, execute)                  │
│                                                              │
│  [5] record() ──► saves to JSON session file                 │
│      note_tool() ──► updates working memory                  │
│                                                              │
│  [6] tool_delegate() ──► creates child MiniAgent             │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Component Walkthroughs

---

### 3a. Workspace Context — `WorkspaceContext` ([lines 92–160](mini_coding_agent.py#L92-L160))

#### What it is

Before the agent can help you, it needs to *know where it is*. The `WorkspaceContext` class collects information about your git repository and formats it as text that gets injected into the AI's instructions.

Think of it like a new employee's onboarding document: "You're working in the `feature/auth` branch. The last 5 commits were X, Y, Z. The README says this project is a web API."

#### The code

```python
# Lines 102–140
@classmethod
def build(cls, cwd):
    cwd = Path(cwd).resolve()

    def git(args, fallback=""):
        try:
            result = subprocess.run(
                ["git", *args], cwd=cwd, capture_output=True,
                text=True, check=True, timeout=5,
            )
            return result.stdout.strip() or fallback
        except Exception:
            return fallback   # ← silently handles non-git directories

    repo_root = Path(git(["rev-parse", "--show-toplevel"], str(cwd))).resolve()
    # ... reads README, pyproject.toml, AGENTS.md ...
    return cls(
        branch=git(["branch", "--show-current"], "-") or "-",
        status=clip(git(["status", "--short"], "clean") or "clean", 1500),
        recent_commits=[line for line in git(["log", "--oneline", "-5"]).splitlines() if line],
        # ...
    )
```

**What gets collected:**
- Current directory and repository root
- Current branch name and default branch
- Git status (which files are modified)
- Last 5 commit messages
- Content of `README.md`, `AGENTS.md`, `pyproject.toml`, `package.json` (up to 1200 chars each)

The `.text()` method ([line 142](mini_coding_agent.py#L142)) formats this into a block of text appended to the system prompt.

#### Why it matters

Without this, the AI would have to guess what project it's in. With this, it knows your branch, your recent changes, and what the project does — before you even type a message.

---

### 3b. Prompt Shaping — `build_prefix`, `memory_text`, `prompt` ([lines 334–440](mini_coding_agent.py#L334-L440))

#### What it is

The **prompt** is what gets sent to the AI model on every step. This component assembles the full prompt from four layers:

```
┌────────────────────────────────────────────┐
│  LAYER 1: System prefix (static)           │
│  - Rules ("use tools instead of guessing") │
│  - List of available tools                 │
│  - Valid response examples                 │
│  - Workspace context (git info)            │
├────────────────────────────────────────────┤
│  LAYER 2: Memory (dynamic)                 │
│  - Current task                            │
│  - Recently accessed files                 │
│  - Short notes from recent steps           │
├────────────────────────────────────────────┤
│  LAYER 3: Conversation history (dynamic)   │
│  - All tool calls and results so far       │
│  - All previous assistant responses        │
├────────────────────────────────────────────┤
│  LAYER 4: Current user request             │
└────────────────────────────────────────────┘
```

#### The code

**`build_prefix()`** ([line 334](mini_coding_agent.py#L334)) — builds the static system instructions:

```python
# Lines 351–381 (simplified)
return textwrap.dedent(f"""\
    You are Mini-Coding-Agent...

    Rules:
    - Use tools instead of guessing about the workspace.
    - Return exactly one <tool>...</tool> or one <final>...</final>.
    ...

    Tools:
    {tool_text}   ← auto-generated list of all available tools

    Valid response examples:
    {examples}    ← shows the AI exactly what format to use

    {self.workspace.text()}  ← git context injected here
    """)
```

**`memory_text()`** ([line 383](mini_coding_agent.py#L383)):

```python
def memory_text(self):
    memory = self.session["memory"]
    return f"""\
    Memory:
    - task: {memory['task'] or "-"}
    - files: {", ".join(memory["files"]) or "-"}
    - notes:
      {... memory["notes"] ...}
    """
```

**`prompt()`** ([line 427](mini_coding_agent.py#L427)) — assembles all four layers:

```python
def prompt(self, user_message):
    return f"""\
    {self.prefix}          ← Layer 1 (static, built once)

    {self.memory_text()}   ← Layer 2 (changes as agent works)

    Transcript:
    {self.history_text()}  ← Layer 3 (grows each step)

    Current user request:
    {user_message}         ← Layer 4 (the original task)
    """
```

#### Why it matters

The AI model has no persistent memory between API calls — **every call starts fresh**. The only way the model "remembers" what happened is by reading it in the prompt. This component is responsible for packaging everything the model needs to know into one big text block.

---

### 3c. Tools & Permissions — `build_tools`, `run_tool`, `validate_tool`, `approve` ([lines 283–625](mini_coding_agent.py#L283-L625))

#### What it is

Tools are the agent's *hands*. This component defines what the agent can do, validates that tool calls are safe, and asks for human approval before doing anything risky.

#### The 7 tools

```python
# Lines 283–329
```

| Tool | Safe? | Purpose | Key args |
|------|-------|---------|----------|
| `list_files` | Safe | List files in a directory | `path='.'` |
| `read_file` | Safe | Read lines from a file | `path`, `start=1`, `end=200` |
| `search` | Safe | Search code (uses ripgrep if available) | `pattern`, `path='.'` |
| `delegate` | Safe | Ask a child agent to investigate | `task`, `max_steps=3` |
| `run_shell` | **Risky** | Run any shell command | `command`, `timeout=20` |
| `write_file` | **Risky** | Create or overwrite a file | `path`, `content` |
| `patch_file` | **Risky** | Replace one exact block of text in a file | `path`, `old_text`, `new_text` |

#### Tool execution flow

When the model asks to use a tool, this is the exact sequence ([lines 508–527](mini_coding_agent.py#L508-L527)):

```
Model says: <tool>{"name":"write_file","args":{...}}</tool>
                          │
                          ▼
              1. Is this a known tool?
                 ├─ No  → return error message
                 └─ Yes ↓
                          │
                          ▼
              2. validate_tool(name, args)
                 ├─ Invalid args → return error + example
                 └─ Valid ↓
                          │
                          ▼
              3. repeated_tool_call()?
                 ├─ Same call twice in a row → return error
                 └─ OK ↓
                          │
                          ▼
              4. Is tool risky?
                 ├─ No  → run immediately
                 └─ Yes → approve(name, args)
                              ├─ "ask"   → prompt user [y/N]
                              ├─ "auto"  → always approve
                              └─ "never" → always deny
                          │
                          ▼
              5. tool["run"](args)  ← actual execution
                 └─ result clipped to 4000 chars → return
```

#### Validation examples

`validate_tool()` ([line 548](mini_coding_agent.py#L548)) does per-tool checks before running anything:

```python
# patch_file must find old_text exactly once (lines 591–604)
if name == "patch_file":
    text = path.read_text(encoding="utf-8")
    count = text.count(old_text)
    if count != 1:
        raise ValueError(f"old_text must occur exactly once, found {count}")
```

This prevents accidents like replacing the wrong occurrence.

#### Approval policy

```python
# Lines 614–625
def approve(self, name, args):
    if self.read_only:
        return False               # child agents: always denied
    if self.approval_policy == "auto":
        return True                # dangerous: no human check
    if self.approval_policy == "never":
        return False               # testing mode
    # Default "ask": prompt the human
    answer = input(f"approve {name} {json.dumps(args)}? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}
```

**Run with `--approval auto`** and the agent acts completely on its own. **Run with `--approval ask`** (the default) and every file write and shell command needs your thumbs up.

#### Path security

([Lines 734–752](mini_coding_agent.py#L734-L752)) Every file path is resolved and checked to make sure it stays inside the workspace root. The model can't escape with tricks like `../../../etc/passwd`.

---

### 3d. Context Reduction — `clip`, `history_text` ([lines 71–75](mini_coding_agent.py#L71-L75), [398–422](mini_coding_agent.py#L398-L422))

#### The problem

AI models have a **token limit** — they can only read so much text at once. Conversations grow longer with every tool call, so older history must be compressed to make room for new information.

#### Two strategies

**`clip(text, limit=4000)`** ([line 71](mini_coding_agent.py#L71)) — hard truncation with a note:

```python
def clip(text, limit=MAX_TOOL_OUTPUT):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
```

Used on every tool output so one large file listing can't flood the prompt.

**`history_text()`** ([line 398](mini_coding_agent.py#L398)) — smart compression of the conversation transcript:

```python
recent_start = max(0, len(history) - 6)  # last 6 items = "recent"
for index, item in enumerate(history):
    recent = index >= recent_start
    if item["role"] == "tool":
        limit = 900 if recent else 180     # ← recent = full detail
        ...                                #   old    = heavily shortened
```

**The algorithm:**
- Last 6 history items: kept with up to 900 characters each
- Older items: compressed to 180–220 characters each
- Duplicate `read_file` calls on the same file: deduplicated entirely
- Final result: clipped to `MAX_HISTORY` = 12,000 characters total

#### Why it matters

Without this, a long session would eventually exceed the model's limit and crash. With it, the agent can work on large tasks over many steps without running out of context.

---

### 3e. Session Memory & The Agent Loop — `SessionStore`, `record`, `note_tool`, `ask` ([lines 165–503](mini_coding_agent.py#L165-L503))

#### Session persistence

`SessionStore` ([line 165](mini_coding_agent.py#L165)) saves the entire conversation to a JSON file after every step:

```
.mini-coding-agent/
  sessions/
    20240406-142033-a1b2c3.json   ← one file per session
```

The session JSON looks like:

```json
{
  "id": "20240406-142033-a1b2c3",
  "created_at": "2024-04-06T14:20:33Z",
  "workspace_root": "/path/to/repo",
  "history": [
    {"role": "user",      "content": "Create a test file", "created_at": "..."},
    {"role": "tool",      "name": "list_files", "args": {"path": "."}, "content": "...", "created_at": "..."},
    {"role": "assistant", "content": "I've created test_example.py", "created_at": "..."}
  ],
  "memory": {
    "task": "Create a test file",
    "files": ["test_example.py"],
    "notes": ["list_files: [F] README.md [F] mini_coding_ag..."]
  }
}
```

Resume any session with `--resume latest` or `--resume <session-id>`.

#### The agent loop — `ask()` ([line 457](mini_coding_agent.py#L457))

This is the **heart of the agent**. Here's the pseudocode:

```
ask(user_message):
    record user message in history
    set memory.task = user_message  (if first message)

    loop up to max_steps times:
        full_prompt = prefix + memory + history + user_message
        raw_response = model.complete(full_prompt)

        kind, payload = parse(raw_response)

        if kind == "tool":
            result = run_tool(payload["name"], payload["args"])
            record tool result in history
            update memory with tool info
            continue loop  ← model gets another turn

        if kind == "retry":
            record error hint in history
            continue loop  ← model tries again with the hint

        if kind == "final":
            record final answer in history
            return final answer  ← DONE

    return "Stopped after reaching the step limit"
```

In actual code ([lines 467–496](mini_coding_agent.py#L467-L496)):

```python
while tool_steps < self.max_steps and attempts < max_attempts:
    attempts += 1
    raw = self.model_client.complete(self.prompt(user_message), self.max_new_tokens)
    kind, payload = self.parse(raw)

    if kind == "tool":
        tool_steps += 1
        name = payload.get("name", "")
        args = payload.get("args", {})
        result = self.run_tool(name, args)
        self.record({"role": "tool", "name": name, "args": args, "content": result, ...})
        self.note_tool(name, args, result)
        continue

    if kind == "retry":
        self.record({"role": "assistant", "content": payload, ...})
        continue

    final = (payload or raw).strip()
    self.record({"role": "assistant", "content": final, ...})
    return final
```

#### Response parsing — `parse()` ([line 628](mini_coding_agent.py#L628))

The model returns plain text. The agent looks for special tags:

```
<tool>{"name":"list_files","args":{"path":"."}}</tool>    ← JSON-style tool call
```

```xml
<tool name="write_file" path="hello.py">
<content>print("hello")</content>
</tool>                                                    ← XML-style (good for multi-line)
```

```
<final>I've created hello.py with a print statement.</final>   ← done
```

The parser returns one of three outcomes:
- `("tool", {"name": ..., "args": {...}})` — run a tool
- `("retry", "error hint message")` — model sent garbled output, try again
- `("final", "the answer")` — task complete, return to user

---

### 3f. Delegation — `tool_delegate` ([lines 859–878](mini_coding_agent.py#L859-L878))

#### What it is

The `delegate` tool lets the main agent spawn a **child agent** to investigate something. The child is read-only and can't write files or run commands. Think of it like a senior engineer asking a junior to "go read that module and summarize it."

#### The code

```python
def tool_delegate(self, args):
    task = str(args.get("task", "")).strip()
    child = MiniAgent(
        model_client=self.model_client,
        workspace=self.workspace,
        session_store=self.session_store,
        approval_policy="never",     # ← risky tools auto-denied
        max_steps=int(args.get("max_steps", 3)),
        depth=self.depth + 1,        # ← depth counter increases
        max_depth=self.max_depth,
        read_only=True,              # ← can't write anything
    )
    child.session["memory"]["task"] = task
    child.session["memory"]["notes"] = [clip(self.history_text(), 300)]  # ← parent context shared
    return "delegate_result:\n" + child.ask(task)
```

#### Safety guardrails

| Guardrail | How it works |
|-----------|-------------|
| **Read-only** | `read_only=True` causes `approve()` to always return `False` |
| **Depth limit** | `depth >= max_depth` → `delegate` tool is not added to child's tools ([line 322](mini_coding_agent.py#L322)) |
| **Step limit** | Child gets `max_steps=3` (default), can't run forever |
| **Auto-deny risky** | `approval_policy="never"` blocks `run_shell`, `write_file`, `patch_file` |

This prevents infinite recursion: a child cannot create grandchildren.

---

## 4. Full End-to-End Example

**Command:** `python mini_coding_agent.py "Create a hello world script"`

**Step 1 — Startup** ([lines 924–958](mini_coding_agent.py#L924-L958))

```
build_agent(args):
  load_dotenv(".env")                        ← reads OPENAI_API_KEY
  workspace = WorkspaceContext.build(".")    ← runs git commands
  store = SessionStore(".mini-coding-agent/sessions")
  model = OpenAIModelClient("gpt-4o-mini", api_key, ...)
  agent = MiniAgent(model, workspace, store, approval_policy="ask")
```

Welcome screen prints. Session ID generated: `20240406-142033-a1b2c3`.

---

**Step 2 — `ask("Create a hello world script")` begins** ([line 457](mini_coding_agent.py#L457))

- `memory["task"]` = `"Create a hello world script"`
- Record `{"role": "user", "content": "Create a hello world script"}`
- Enter loop

---

**Step 3 — Iteration 1: Model decides to look around first**

Prompt sent to OpenAI includes:
```
You are Mini-Coding-Agent...
[tools listed]
[git context: branch main, last commit "initial commit"]

Memory:
- task: Create a hello world script
- files: -
- notes: - none

Transcript:
- empty

Current user request:
Create a hello world script
```

Model responds:
```
<tool>{"name":"list_files","args":{"path":"."}}</tool>
```

- `parse()` → `("tool", {"name": "list_files", "args": {"path": "."}})`
- `run_tool("list_files", {"path": "."})` → `"[F] README.md\n[F] requirements.txt"`
- Record tool result in history
- `note_tool()` updates memory: `notes = ["list_files: [F] README.md [F] requireme..."]`

---

**Step 4 — Iteration 2: Model writes the file**

Prompt now includes the `list_files` result in the transcript. Model responds:

```xml
<tool name="write_file" path="hello.py">
<content>print("Hello, world!")
</content>
</tool>
```

- `parse()` → `("tool", {"name": "write_file", "args": {"path": "hello.py", "content": "print(...)"}})`
- `validate_tool()` → content exists, path is inside workspace ✓
- `approve()` → prints:
  ```
  approve write_file {"content": "print(\"Hello, world!\")\n", "path": "hello.py"}? [y/N]
  ```
  You type `y`
- `tool_write_file()` → creates `hello.py`, returns `"wrote hello.py (22 chars)"`
- Record tool result, update memory: `files = ["hello.py"]`

---

**Step 5 — Iteration 3: Model gives final answer**

Prompt includes both tool results. Model responds:

```
<final>I've created hello.py with a simple Hello World print statement. Run it with: python hello.py</final>
```

- `parse()` → `("final", "I've created hello.py...")`
- Record `{"role": "assistant", "content": "I've created hello.py..."}`
- Return the final answer

---

**Output you see:**

```
I've created hello.py with a simple Hello World print statement. Run it with: python hello.py
```

Session saved at `.mini-coding-agent/sessions/20240406-142033-a1b2c3.json`. Resume later with `--resume latest`.

---

## 5. Key Design Decisions

### Single file

The entire agent — 1035 lines — lives in one `.py` file. This is intentional: it's easier to learn when you can read from top to bottom without jumping between packages.

### Two response formats (JSON vs XML)

The model can respond with either:

```json
<tool>{"name":"read_file","args":{"path":"README.md"}}</tool>
```

or

```xml
<tool name="write_file" path="hello.py">
<content>print("hello")
</content>
</tool>
```

Why two? JSON is compact and machine-readable, but JSON strings can't easily contain newlines. XML-style works better for multi-line file content. The parser ([line 628](mini_coding_agent.py#L628)) handles both.

### Standard library only (except `openai`)

The only external dependency is `openai`. No `requests`, no `python-dotenv`, no `pydantic`. Even the `.env` file reader ([line 16](mini_coding_agent.py#L16)) is hand-written in stdlib. This minimizes setup friction — `pip install openai` and you're ready.

### Workspace isolation

No matter what path the model requests, `path()` ([line 746](mini_coding_agent.py#L746)) resolves it relative to the repo root and verifies it stays inside. A malicious prompt trying `../../../etc/passwd` gets an error, not a file read.

### Session persistence after every step

`record()` ([line 445](mini_coding_agent.py#L445)) writes the JSON file to disk after *every* history item. If the process crashes mid-task, you don't lose your work — just `--resume latest`.

### Bounded memory lists

`remember()` ([line 272](mini_coding_agent.py#L272)) keeps memory lists at fixed maximum sizes:

```python
@staticmethod
def remember(bucket, item, limit):
    if item in bucket:
        bucket.remove(item)
    bucket.append(item)
    del bucket[:-limit]    # ← drop oldest if over limit
```

`files` maxes out at 8 entries. `notes` maxes out at 5. This prevents memory from growing unboundedly across a long session.

---

## 6. Glossary for Beginners

| Term | Definition |
|------|-----------|
| **Agent** | A program that uses an AI model + tools in a loop to complete tasks autonomously |
| **Tool** | A function the AI can call to take an action (read a file, run a command, etc.) |
| **System Prompt** | Instructions sent to the AI at the start of every request. Defines its role, rules, and available tools |
| **Token** | The unit AI models use to measure text length. Roughly 1 token ≈ 4 characters. Models have a maximum number of tokens they can process at once |
| **Session** | A saved conversation (history + memory) stored as a JSON file so it can be resumed later |
| **Memory** | A short distillation of what the agent is working on: current task, recently touched files, and recent notes |
| **Delegation** | When the main agent creates a child agent to investigate something, without giving the child the ability to modify files |
| **Approval Policy** | Controls whether the user must confirm risky tool calls: `ask` (default, prompts you), `auto` (no prompts), `never` (blocks all risky tools) |
| **Context Reduction** | The process of compressing old conversation history so it fits within the model's token limit |
| **Workspace Root** | The root of the git repository. All file operations are restricted to within this directory |
| **Ripgrep (`rg`)** | A fast code-search tool. The agent uses it for `search` if it's installed, and falls back to a slower Python implementation otherwise |
