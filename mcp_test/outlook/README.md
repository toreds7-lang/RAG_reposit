# Outlook MCP Agent

An interactive AI agent that manages Microsoft Outlook emails using LangChain + MCP (Model Context Protocol). It connects to the [outlook-mcp-server](https://github.com/Wallisking1991/outlook-mcp-server) which provides email functionality through Windows COM automation.

## About the MCP Server

The outlook-mcp-server is a Python-based MCP server that interfaces with Microsoft Outlook desktop client via `pywin32` COM automation. It does **not** use the Microsoft Graph API — it talks directly to the locally installed Outlook application.

**Key characteristics:**
- Windows only (requires `pywin32` COM interface)
- Microsoft Outlook must be installed and configured with an active account
- Text-only email support (no HTML rendering)
- Maximum email history limited to 30 days
- No calendar or contacts support — email only

**Available tools (6 total):**

| Tool | Description |
|------|-------------|
| `list_folders` | Lists all available mail folders in Outlook |
| `list_recent_emails` | Retrieves emails from a specified number of days |
| `search_emails` | Searches by contact name, keyword, or phrase (supports OR operators) |
| `get_email_by_number` | Views complete email content including attachments |
| `reply_to_email_by_number` | Replies to a specific email |
| `compose_email` | Creates and sends a new email |

## Prerequisites

- Windows OS
- Python 3.10+
- Microsoft Outlook installed and configured with an active email account
- Anthropic API key (set in `.env`)

## Setup

### 1. Clone the MCP server (if not already done)

```bash
cd d:\2026_Agent\mcp_test\outlook
git clone https://github.com/Wallisking1991/outlook-mcp-server.git
```

### 2. Create virtual environment

```bash
python -m venv .venv
```

### 3. Activate virtual environment

```bash
# Windows CMD
.venv\Scripts\activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Git Bash / MSYS2
source .venv/Scripts/activate
```

### 4. Install dependencies

```bash
pip install python-dotenv langchain-anthropic langchain langchain-mcp-adapters "mcp>=1.2.0" "pywin32>=305"
```

### 5. Configure environment variables

Create a `.env` file (or verify the existing one has your Anthropic key):

```
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Optional LangSmith tracing:

```
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=your-project-name
```

## Running the Agent

Make sure the virtual environment is activated, then:

```bash
python outlook_agent.py
```

Expected output:

```
Connecting to Outlook MCP server...
Loaded 6 tools: list_folders, list_recent_emails, search_emails, get_email_by_number, reply_to_email_by_number, compose_email

Outlook Agent ready. Type your instructions (or 'quit' to exit).

You:
```

Type `quit`, `exit`, or `q` to stop. Press `Ctrl+C` also works.

## Test Examples

Below are example prompts you can try once the agent is running. Make sure Outlook is open and connected.

### Example 1: List mail folders

```
You: Show me all my mail folders
```

Expected: The agent calls `list_folders` and displays all folders (Inbox, Sent Items, Drafts, etc.)

### Example 2: View recent emails

```
You: Show me my emails from the last 3 days
```

Expected: The agent calls `list_recent_emails` with `days=3` and lists email subjects with sender info.

### Example 3: Search emails by keyword

```
You: Search for emails about "quarterly report" from the last 2 weeks
```

Expected: The agent calls `search_emails` with the keyword and returns matching results.

### Example 4: Search with OR operator

```
You: Find emails mentioning "budget OR forecast OR planning"
```

Expected: The agent searches for emails matching any of those terms.

### Example 5: Read a specific email

```
You: Show me the full content of email #2
```

Expected: The agent calls `get_email_by_number` and displays the complete email body, sender, date, and attachment info.

### Example 6: Reply to an email

```
You: Reply to email #1 with: "Thank you for the update. I will review the document and share my feedback by end of day."
```

Expected: The agent calls `reply_to_email_by_number` and sends the reply through Outlook.

### Example 7: Compose and send a new email

```
You: Send an email to john.doe@example.com with subject "Meeting Follow-up" and body "Hi John, thanks for the meeting today. I've attached the action items we discussed. Let me know if I missed anything."
```

Expected: The agent calls `compose_email` and sends the email via Outlook.

### Example 8: Multi-step workflow

```
You: Check my inbox from the last 7 days, find any emails from my manager about the project deadline, and summarize them for me
```

Expected: The agent chains multiple tools — first listing recent emails, then searching/reading relevant ones, and providing a summary.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Outlook is not running"** | Open Microsoft Outlook before starting the agent |
| **COM permission errors** | Run the terminal as administrator, or check Outlook security settings |
| **Server connection timeout** | Ensure Outlook is fully loaded (not stuck on login/sync) |
| **No emails returned** | Check that the date range is within 30 days and the folder exists |
| **pywin32 import error** | Reinstall: `pip install --force-reinstall pywin32` |

## Security Note

This agent has full access to your Outlook email — it can read, search, and send emails. Only run it in a trusted environment. Never share your `.env` file or API keys.
