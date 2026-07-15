"""FastAPI webhook entry point for GitHub pull-request events."""

import logging
import os

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, Header, HTTPException, Request
from github import Github, GithubException
from github.PullRequest import PullRequest

from comment_formatter import format_pr_comment
from history_store import record_analysis
from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PR Risk Analysis Agent")


def _github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN is not configured")
    return Github(token)


def _fetch_changed_files(pr: PullRequest) -> list[dict]:
    """Fetch changed-file patches and proposed file contents from GitHub."""
    changed_files = []
    for changed_file in pr.get_files():
        if not changed_file.filename.endswith(".py"):
            continue
        content = ""
        if changed_file.status != "removed":
            try:
                blob = pr.base.repo.get_contents(changed_file.filename, ref=pr.head.sha)
                content = blob.decoded_content.decode("utf-8")
            except Exception:
                logger.exception("Could not fetch proposed content for %s", changed_file.filename)
        changed_files.append(
            {
                "filename": changed_file.filename,
                "patch": getattr(changed_file, "patch", "") or "",
                "content": content,
                "status": changed_file.status,
            }
        )
    return changed_files


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
) -> dict:
    """Process opened, synchronized, and reopened GitHub pull requests."""
    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    try:
        payload = await request.json()
    except ValueError as error:
        logger.warning("Malformed webhook JSON: %s", error)
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be an object")
    if payload.get("action") not in {"opened", "synchronize", "reopened"}:
        return {"status": "ignored", "action": payload.get("action")}

    pull_request_data = payload.get("pull_request", {})
    repository_name = payload.get("repository", {}).get("full_name")
    pull_request_number = pull_request_data.get("number")
    if not repository_name or not pull_request_number:
        raise HTTPException(status_code=400, detail="Missing repository or pull request number")

    try:
        github = _github_client()
        repository = github.get_repo(repository_name)
        pull_request = repository.get_pull(pull_request_number)
        changed_files = _fetch_changed_files(pull_request)
        results = [
            run_pipeline(file_data["content"], file_data["filename"])
            for file_data in changed_files
        ]
        comment = format_pr_comment(results, pull_request.title)
        pull_request.create_issue_comment(comment)
        record_analysis(pull_request_number, pull_request.title, results)
        return {
            "status": "ok",
            "files_analyzed": len(changed_files),
            "findings": sum(len(result["findings"]) for result in results),
        }
    except GithubException as error:
        if error.status == 429 or (
            error.status == 403 and "rate limit" in str(error).lower()
        ):
            logger.warning("GitHub rate limit failure: %s", error)
            return {"status": "error", "message": "GitHub API rate limit reached"}
        if error.status == 403:
            logger.warning("GitHub token permission failure: %s", error)
            return {
                "status": "error",
                "message": "GitHub token cannot read or comment on this repository",
            }
        logger.exception("GitHub API failure during webhook processing")
        return {"status": "error", "message": "GitHub API request failed"}
    except Exception as error:
        logger.exception("Webhook processing failed")
        return {"status": "error", "message": str(error)}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
