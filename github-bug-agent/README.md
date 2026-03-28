# 🐛 GitHub Bug Fixing Agent — ADK + MCP

An AI-powered bug fixing agent built with **Google ADK** and **Model Context Protocol (MCP)**.
Given a GitHub repo and issue number, the agent reads the issue, explores the codebase,
identifies the root cause, and generates a precise fix — optionally posting it as a GitHub comment.

---

## 🏗️ Architecture

```
User (ADK Chat UI)
      │
      ▼
┌──────────────────────────┐     SSE / MCP      ┌───────────────────────────┐
│   ADK Agent              │ ──────────────────▶ │   MCP Server              │
│   Cloud Run              │                     │   Cloud Run               │
│                          │ ◀──────────────────  │                           │
│   gemini-2.0-flash       │   Structured JSON   │   GitHub Tools:           │
│   MCPToolset             │   tool responses    │   • list_repo_issues      │
│   Strict tool ordering   │                     │   • get_issue_details     │
└──────────────────────────┘                     │   • list_repo_files       │
                                                 │   • get_file_content      │
                                                 │   • post_fix_comment      │
                                                 └───────────────────────────┘
                                                             │
                                                             ▼
                                                      GitHub REST API
```

**Key design principle:** AI reasoning lives in the ADK agent. All GitHub data access
lives in the MCP server. The agent never touches GitHub directly — it only calls MCP tools.

---

## 📋 Prerequisites

- Python 3.11+
- Google Cloud project with billing enabled
- `gcloud` CLI authenticated (`gcloud auth login`)
- Docker (for local testing)
- GitHub Personal Access Token with **`repo`** scope

---

## ⚡ Quick Start (Local)

```bash
# 1. Clone & configure
git clone <your-repo-url> && cd github-bug-agent
cp .env.example .env
# Fill in GITHUB_TOKEN and GOOGLE_API_KEY in .env

# 2. Run both services
docker-compose up --build

# 3. Open the agent UI
open http://localhost:8080
```

**Try these prompts:**
```
List open bug issues in psf/requests

Analyze bug issue #1234 in psf/requests and suggest a fix

Fix issue #7 in myusername/myrepo and post the fix as a comment
```

---

## ☁️ Deploy to Cloud Run (One Command)

### Setup (one-time)
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com

# Store secrets
echo -n "ghp_your_token" | gcloud secrets create github-token --data-file=-
echo -n "your_gemini_key" | gcloud secrets create gemini-api-key --data-file=-
```

### Deploy everything
```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_GITHUB_SECRET=github-token,_GEMINI_SECRET=gemini-api-key
```

The build output prints your agent URL at the end — submit that URL for the hackathon.

---

## 🗂️ Project Structure

```
github-bug-agent/
├── mcp_server/
│   ├── main.py           # FastMCP server — 5 structured GitHub tools
│   ├── requirements.txt
│   └── Dockerfile
├── adk_agent/
│   ├── agent.py          # ADK Agent — strict tool order + structured output format
│   ├── main.py           # FastAPI entrypoint + ADK chat UI
│   ├── __init__.py       # Required for ADK agent discovery
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml    # Local dev
├── cloudbuild.yaml       # One-command GCP deployment
├── .env.example
└── README.md
```

---

## 🔧 MCP Tools Reference

| Tool | Returns | Description |
|------|---------|-------------|
| `list_repo_issues` | JSON + metadata | Open issues filtered by label |
| `get_issue_details` | JSON + comments | Full issue body + all comments |
| `list_repo_files` | JSON (dirs first) | Repo file structure at any path |
| `get_file_content` | JSON + content | File content (4000 char limit) |
| `post_fix_comment` | JSON confirmation | Posts formatted fix to GitHub |

All tools return structured JSON, including errors (`error`, `code`, `message`, `hint`).

---

## 🎯 Agent Output Format

Every fix response follows this structure:

```
## 🔍 Bug Analysis
Issue / Root Cause / Affected Files

## 🛠️ Fix
Before/After code snippet

## 📋 Implementation Steps
Numbered action list

## ✅ Testing
Checkbox test cases
```

---

## 🧹 Cleanup

```bash
gcloud run services delete github-bug-agent --region $REGION
gcloud run services delete github-mcp-server --region $REGION
gcloud secrets delete github-token
gcloud secrets delete gemini-api-key
```

---

## 📝 Hackathon Checklist

- [x] Built with Google ADK (`root_agent` in `agent.py`)
- [x] Uses MCP to connect to one external data source (GitHub API)
- [x] Retrieves structured data (issues, file contents, repo structure)
- [x] Uses retrieved data to generate a structured fix response
- [x] Deployed to Cloud Run — two services with IAM-based auth
- [x] All tools return structured JSON for reliable LLM parsing
- [x] Strict tool usage order enforced in agent instructions
- [x] Graceful error handling with actionable hints
