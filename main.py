import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from simian import run_simian
from utils import find_repo_root

app = Flask(__name__)
CORS(app)

# Accept abbreviated SHA-1 (>=7) up to 40 chars
COMMIT_HASH_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
# http(s) or SCP-like (git@host:org/repo.git)
GIT_URL_RE = re.compile(r"^(https?|git)://|^[\w.@:/~-]+@[\w.-]+:.+\.git$")

REPOS_DIR = Path.cwd() / "repos"
REPOS_DIR.mkdir(exist_ok=True)


def _dir_name_from_url(repo_url: str) -> str:
    path = urlparse(repo_url).path
    if not path:  # scp-like: git@github.com:org/proj.git
        path = repo_url.split(":", 1)[-1]
    tail = Path(path).name
    return tail[:-4] if tail.endswith(".git") else tail


def _run(cmd, cwd=None, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _ensure_repo(repo_url: str) -> Path:
    repo_dir = REPOS_DIR / _dir_name_from_url(repo_url)

    if repo_dir.exists() and (repo_dir / ".git").exists():
        fetch = _run(["git", "fetch", "--all", "--tags", "--prune"], cwd=repo_dir)
        if fetch.returncode != 0:
            raise RuntimeError(f"git fetch failed: {fetch.stderr.strip()}")
        return repo_dir

    clone = _run(["git", "clone", repo_url, str(repo_dir)])
    if clone.returncode != 0:
        shutil.rmtree(repo_dir, ignore_errors=True)
        raise RuntimeError(f"git clone failed: {clone.stderr.strip()}")

    fetch = _run(["git", "fetch", "--all", "--tags", "--prune"], cwd=repo_dir)
    if fetch.returncode != 0:
        raise RuntimeError(f"git fetch failed: {fetch.stderr.strip()}")

    return repo_dir


@app.route("/clone-detection/trigger", methods=["GET"])
def trigger_clone_detection():
    repo_url = (request.args.get("repo") or "").strip()
    ref = (request.args.get("sha") or "").strip()

    if not repo_url or not GIT_URL_RE.search(repo_url):
        return jsonify(error="missing/invalid 'repo'"), 400
    if not ref:
        return jsonify(error="missing 'sha' (commit-ish required)"), 400

    try:
        repo_dir = _ensure_repo(repo_url)
    except RuntimeError as e:
        return jsonify(error=str(e)), 400

    root = find_repo_root(repo_dir) or repo_dir
    if not (root / ".git").exists():
        return jsonify(error="invalid repository (.git not found)"), 400

    rp = _run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=root)
    if rp.returncode != 0:
        return jsonify(error="commit-ish not found in repository", ref=ref), 404
    full_sha = (rp.stdout or "").strip()
    if not full_sha:
        return jsonify(error="could not resolve commit-ish", ref=ref), 404

    co = _run(["git", "checkout", "--quiet", full_sha], cwd=root, timeout=60)
    if co.returncode != 0:
        return jsonify(error="git checkout failed", stdout=co.stdout, stderr=co.stderr), 400

    simian_result = run_simian(str(root))
    return Response(
        simian_result,
        status=200,
        mimetype="application/xml",
        headers={"Content-Type": "application/xml; charset=utf-8"},
    )




@app.get("/")
def health():
    return jsonify(status="ok", service="Simian-api")


def run_dev():
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    run_dev()
