# GitHub Bug Fixing Agent — ADK + MCP

An AI-powered bug fixing agent built with **Google ADK** and **Model Context Protocol (MCP)**.
Given a GitHub repo and issue number, the agent reads the issue, explores the codebase,
identifies the root cause, and generates a precise fix — optionally posting it as a GitHub comment.

---

## Architecture

```
User (ADK Chat UI)
      |
      v
+----------------------------+     SSE / MCP      +-----------------------------+
|   ADK Agent                | -----------------> |   MCP Server                |
|   Cloud Run                |                    |   Cloud Run                 |
|                            | <----------------- |                             |
|   gemini-2.0-flash         |   Structured JSON  |   GitHub Tools:             |
|   MCPToolset               |   tool responses   |   - list_repo_issues        |
|   Error recovery prompting |                    |   - get_issue_details       |
+----------------------------+                    |   - list_repo_files         |
                                                  |   - get_file_content        |
                                                  |   - post_fix_comment        |
                                                  +-----------------------------+
                                                             |
                                                             v
                                                      GitHub REST API
```

AI reasoning lives in the ADK agent. All GitHub data access
lives in the MCP server. The agent never touches GitHub directly — it only calls MCP tools.

---

## Prerequisites

- Python 3.11+
- Google Cloud project with billing enabled
- `gcloud` CLI authenticated
- Docker (for local testing)
- GitHub Personal Access Token with **`repo`** scope

---

## Quick Start (Local)

```bash
git clone <your-repo-url> && cd github-bug-agent
cp .env.example .env
# Fill in GITHUB_TOKEN and GOOGLE_API_KEY in .env

docker-compose up --build

# Open http://localhost:8080
```

**Try these prompts:**
```
List open bug issues in psf/requests

Analyze bug issue #1234 in psf/requests and suggest a fix

Fix issue #7 in myusername/myrepo and post the fix as a comment
```

---

## Deploy to Cloud Run

### Setup (one-time)
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud config set project $PROJECT_ID

gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com

echo -n "ghp_your_token" | gcloud secrets create github-token --data-file=-
echo -n "your_gemini_key" | gcloud secrets create gemini-api-key --data-file=-
```

### Deploy
```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_GITHUB_SECRET=github-token,_GEMINI_SECRET=gemini-api-key
```

---

## Project Structure

```
github-bug-agent/
├── mcp_server/
│   ├── main.py             # FastMCP server — 5 GitHub tools, shared error handler, cached client
│   ├── requirements.txt
│   └── Dockerfile
├── adk_agent/
│   ├── agent.py            # ADK Agent — tool ordering, error recovery, structured output
│   ├── main.py             # FastAPI entrypoint + ADK chat UI
│   ├── __init__.py
│   ├── requirements.txt
│   └── Dockerfile
├── lessons/                # Step-by-step learning guide (start at 00-overview-and-map.md)
├── docker-compose.yml
├── cloudbuild.yaml
├── .env.example
└── README.md
```

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_repo_issues` | Open issues filtered by label |
| `get_issue_details` | Full issue body + all comments |
| `list_repo_files` | Repo file structure at any path |
| `get_file_content` | File content (10000 char limit) |
| `post_fix_comment` | Posts formatted fix to GitHub |

All tools return structured JSON. Errors include `code`, `message`, and `hint` fields.
A shared `@_handle_github_errors` decorator handles all GitHub exceptions consistently.

---

## Agent Output Format

Every fix response follows this structure:

```
## Bug Analysis        — Issue / Root Cause / Affected Files
## Fix                 — Before/After code snippet
## Implementation Steps — Numbered action list
## Testing             — Checkbox test cases
```

---

## Learning Guide

The `lessons/` folder contains a step-by-step walkthrough of the entire codebase:

| Lesson | Topic |
|--------|-------|
| 00 | Project overview, file map, MCP roles |
| 01 | MCP server section-by-section (tools, decorator, caching) |
| 02 | ADK agent section-by-section (prompt, MCPToolset, error recovery) |
| 03 | Complete execution flow from startup to fix |
| 04 | MCP protocol basics (transports, JSON-RPC, tool discovery) |
| 05 | Host & web server (FastAPI, sessions, __init__.py) |
| 06 | Issues found & improvements applied |
| 07 | Build your own minimal 2-file version |
| 08 | Glossary & concept reference |

---

## Cleanup

```bash
gcloud run services delete github-bug-agent --region $REGION
gcloud run services delete github-mcp-server --region $REGION
gcloud secrets delete github-token
gcloud secrets delete gemini-api-key
```
