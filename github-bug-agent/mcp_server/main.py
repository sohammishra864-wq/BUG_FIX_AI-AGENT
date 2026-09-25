import os
import json
import functools
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
from github import Github, GithubException, UnknownObjectException, RateLimitExceededException

mcp = FastMCP(
    "github-bug-tools",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
)

_gh_client: Github | None = None

def _github() -> Github:
    global _gh_client
    if _gh_client is None:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise EnvironmentError(
                "GITHUB_TOKEN is not set. "
                "Create one at https://github.com/settings/tokens with 'repo' scope."
            )
        _gh_client = Github(token)
    return _gh_client


def _error(code: str, message: str, hint: str = "") -> str:
    payload = {"error": True, "code": code, "message": message}
    if hint:
        payload["hint"] = hint
    return json.dumps(payload, indent=2)


def _handle_github_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except UnknownObjectException:
            return _error("NOT_FOUND", "The requested resource was not found or is not accessible.",
                          "Check the repo name, path, or issue number.")
        except RateLimitExceededException:
            return _error("RATE_LIMITED", "GitHub API rate limit exceeded.", "Wait ~60 seconds and retry.")
        except GithubException as e:
            msg = e.data.get("message", str(e)) if isinstance(e.data, dict) else str(e)
            if "Resource not accessible" in msg:
                return _error("PERMISSION_DENIED", "Token lacks write access.", "Ensure 'repo' scope.")
            return _error("GITHUB_API_ERROR", msg)
        except EnvironmentError as e:
            return _error("CONFIG_ERROR", str(e))
        except Exception as e:
            return _error("UNEXPECTED_ERROR", str(e))
    return wrapper


@mcp.tool()
@_handle_github_errors
def list_repo_issues(repo_name: str, label: str = "bug", max_issues: int = 5) -> str:
    """
    List open GitHub issues filtered by label.

    Args:
        repo_name:  Full repo, e.g. 'owner/repo'
        label:      Label to filter by (default: 'bug'). Use '' for all open issues.
        max_issues: Max results to return (default: 5, max: 20)

    Returns:
        JSON with repo metadata and a list of matching issues.
    """
    max_issues = min(max_issues, 20)
    g = _github()
    repo = g.get_repo(repo_name)

    kwargs = {"state": "open"}
    if label:
        kwargs["labels"] = [label]
    issues_page = repo.get_issues(**kwargs)

    issues = []
    for i, issue in enumerate(issues_page):
        if i >= max_issues:
            break
        issues.append({
            "number":       issue.number,
            "title":        issue.title,
            "body_preview": (issue.body or "")[:400].strip(),
            "labels":       [lb.name for lb in issue.labels],
            "state":        issue.state,
            "comments":     issue.comments,
            "created_at":   issue.created_at.isoformat(),
            "updated_at":   issue.updated_at.isoformat(),
            "url":          issue.html_url,
            "author":       issue.user.login if issue.user else "unknown",
        })

    return json.dumps({
        "repo":           repo_name,
        "default_branch": repo.default_branch,
        "total_found":    len(issues),
        "label_filter":   label or "none",
        "issues":         issues,
    }, indent=2)


@mcp.tool()
@_handle_github_errors
def get_issue_details(repo_name: str, issue_number: int) -> str:
    """
    Get full details of a specific GitHub issue including all comments.

    Args:
        repo_name:    Full repo, e.g. 'owner/repo'
        issue_number: Issue number (integer)

    Returns:
        JSON with full issue body, labels, assignees, and all comments.
    """
    g = _github()
    repo = g.get_repo(repo_name)
    issue = repo.get_issue(number=issue_number)

    comments = []
    for c in issue.get_comments():
        comments.append({
            "id":         c.id,
            "author":     c.user.login if c.user else "unknown",
            "body":       c.body or "",
            "created_at": c.created_at.isoformat(),
            "url":        c.html_url,
        })

    return json.dumps({
        "repo":          repo_name,
        "number":        issue.number,
        "title":         issue.title,
        "state":         issue.state,
        "body":          issue.body or "",
        "labels":        [lb.name for lb in issue.labels],
        "assignees":     [a.login for a in issue.assignees],
        "author":        issue.user.login if issue.user else "unknown",
        "created_at":    issue.created_at.isoformat(),
        "updated_at":    issue.updated_at.isoformat(),
        "url":           issue.html_url,
        "comment_count": len(comments),
        "comments":      comments,
    }, indent=2)


@mcp.tool()
@_handle_github_errors
def list_repo_files(repo_name: str, path: str = "", ref: str = "") -> str:
    """
    List files and directories at a given path in a GitHub repository.

    Args:
        repo_name: Full repo, e.g. 'owner/repo'
        path:      Directory path (empty = repo root)
        ref:       Branch or commit SHA (empty = default branch)

    Returns:
        JSON with repo info and file listing with types and sizes.
    """
    g = _github()
    repo = g.get_repo(repo_name)
    branch = ref or repo.default_branch
    contents = repo.get_contents(path, ref=branch)

    if not isinstance(contents, list):
        contents = [contents]

    files = sorted(
        [{"path": f.path, "name": f.name, "type": f.type, "size_bytes": f.size} for f in contents],
        key=lambda x: (x["type"] != "dir", x["name"]),
    )

    return json.dumps({
        "repo":       repo_name,
        "branch":     branch,
        "path":       path or "/",
        "item_count": len(files),
        "contents":   files,
    }, indent=2)


@mcp.tool()
@_handle_github_errors
def get_file_content(repo_name: str, file_path: str, ref: str = "") -> str:
    """
    Fetch the content of a specific file from a GitHub repository.

    Args:
        repo_name: Full repo, e.g. 'owner/repo'
        file_path: File path, e.g. 'src/utils.py'
        ref:       Branch or commit SHA (empty = default branch)

    Returns:
        JSON with file metadata and content (truncated to 10000 chars if large).
    """
    CONTENT_LIMIT = 10000
    g = _github()
    repo = g.get_repo(repo_name)
    branch = ref or repo.default_branch
    file_obj = repo.get_contents(file_path, ref=branch)

    if isinstance(file_obj, list):
        listing = [{"path": f.path, "type": f.type} for f in file_obj]
        return _error(
            "PATH_IS_DIRECTORY",
            f"'{file_path}' is a directory, not a file.",
            f"Use list_repo_files to browse it. Contents: {json.dumps(listing)}",
        )

    try:
        raw = file_obj.decoded_content.decode("utf-8")
    except UnicodeDecodeError:
        return _error(
            "BINARY_FILE",
            f"'{file_path}' appears to be a binary file and cannot be read as text.",
            "Try a different file.",
        )

    truncated = len(raw) > CONTENT_LIMIT
    content = raw[:CONTENT_LIMIT] + ("\n\n... [truncated] ..." if truncated else "")

    return json.dumps({
        "repo":       repo_name,
        "branch":     branch,
        "path":       file_path,
        "size_bytes": file_obj.size,
        "truncated":  truncated,
        "content":    content,
    }, indent=2)


@mcp.tool()
@_handle_github_errors
def post_fix_comment(repo_name: str, issue_number: int, fix_suggestion: str) -> str:
    """
    Post a formatted AI-generated bug fix as a comment on a GitHub issue.

    Args:
        repo_name:      Full repo, e.g. 'owner/repo'
        issue_number:   Issue number to comment on
        fix_suggestion: The full fix analysis text (markdown)

    Returns:
        JSON confirmation with comment URL and timestamp.
    """
    g = _github()
    repo = g.get_repo(repo_name)
    issue = repo.get_issue(number=issue_number)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    comment_body = f"""## AI Bug Fix Suggestion

> **Generated by:** GitHub Bug Fixing Agent | **Powered by:** Google ADK + MCP + Gemini 2.0 Flash
> **Analyzed at:** {timestamp}

---

{fix_suggestion.strip()}

---

<details>
<summary>About this suggestion</summary>

This fix was generated automatically by an AI agent that:
1. Read the full issue description and comments
2. Explored the repository structure via MCP tools
3. Read the relevant source files
4. Performed root-cause analysis using Gemini 2.0 Flash

**Please review carefully before applying.**

</details>
"""
    comment = issue.create_comment(comment_body)

    return json.dumps({
        "success":     True,
        "comment_id":  comment.id,
        "comment_url": comment.html_url,
        "issue_url":   issue.html_url,
        "posted_at":   timestamp,
    }, indent=2)


if __name__ == "__main__":
    mcp.run(transport="sse")
