"""FastAPI webhook entry point for GitHub pull-request events."""

import hashlib
import hmac
import json
import logging
import os

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from github import Github, GithubException
from github.PullRequest import PullRequest
from fastapi.concurrency import run_in_threadpool
from comment_formatter import format_pr_comment
from history_store import already_processed, record_analysis, record_processed
from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PR Risk Analysis Agent")

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("GITHUB_WEBHOOK_SECRET must be configured")


def _github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN is not configured")
    return Github(token)


def _fetch_changed_files(pr: PullRequest) -> list[dict]:
    """Fetch changed-file patches and proposed file contents from GitHub."""
    changed_files = [] # 1A
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
        changed_files.append( # 1A
            {
                "filename": changed_file.filename,
                "patch": getattr(changed_file, "patch", "") or "",
                "content": content,
                "status": changed_file.status,
            }
        )
    return changed_files


async def verify_signature(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
) -> bytes:
    """Validate GitHub's HMAC signature and return the raw payload."""
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    body = await request.body()
    expected_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return body


def _process_pull_request(
    repository_name: str, pull_request_number: int, head_sha: str
) -> dict:
    """Run the blocking GitHub and analysis work for one pull request."""
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
    record_analysis(repository_name, pull_request_number, pull_request.title, results)
    record_processed(repository_name, pull_request_number, head_sha)
    return {
        "status": "ok",
        "files_analyzed": len(changed_files),
        "findings": sum(len(result["findings"]) for result in results),
    }


@app.post("/webhook")
async def github_webhook(
    body: bytes = Depends(verify_signature),
    x_github_event: str | None = Header(default=None),
) -> dict:
    """Process opened, synchronized, and reopened GitHub pull requests."""
    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("Malformed webhook JSON: %s", error)
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be an object")
    if payload.get("action") not in {"opened", "synchronize", "reopened"}:
        return {"status": "ignored", "action": payload.get("action")}

    pull_request_data = payload.get("pull_request", {})
    repository_data = payload.get("repository", {})
    if not isinstance(pull_request_data, dict) or not isinstance(repository_data, dict):
        raise HTTPException(status_code=400, detail="Invalid pull request payload")

    repository_name = repository_data.get("full_name")
    pull_request_number = pull_request_data.get("number")
    head_data = pull_request_data.get("head", {})
    head_sha = head_data.get("sha") if isinstance(head_data, dict) else None
    if not repository_name or not pull_request_number or not head_sha:
        raise HTTPException(
            status_code=400,
            detail="Missing repository, pull request number, or head SHA",
        )

    if already_processed(repository_name, pull_request_number, head_sha):
        return {"status": "skipped", "reason": "already processed"}

    try:
        return await run_in_threadpool(
            _process_pull_request, repository_name, pull_request_number, head_sha
        )
    except GithubException as error:
        if error.status == 429 or (
            error.status == 403 and "rate limit" in str(error).lower()
        ):
            logger.warning("GitHub rate limit failure: %s", error)
            raise HTTPException(
                status_code=503, detail="GitHub API rate limit reached"
            ) from error
        if error.status == 403:
            logger.warning("GitHub token permission failure: %s", error)
            raise HTTPException(
                status_code=502,
                detail="GitHub token cannot read or comment on this repository",
            ) from error
        logger.exception("GitHub API failure during webhook processing")
        raise HTTPException(status_code=502, detail="GitHub API request failed") from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Webhook processing failed")
        raise HTTPException(status_code=500, detail="Webhook processing failed") from error


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
