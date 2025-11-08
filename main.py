import io
import os
import re
import tarfile
import tempfile
import shutil
import subprocess
from pathlib import Path
from simian import run_simian
from utils import find_repo_root, safe_extract_tar_gz
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

# Limit upload size (adjust as needed)
app.config["MAX_CONTENT_LENGTH"] = 800 * 1024 * 1024  # 200 MB

# Allow abbreviated commit hashes (>=7 hex chars) up to full 40-chars SHA-1
COMMIT_HASH_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

@app.post("/upload-checkout")
def upload_and_checkout():
    if "file" not in request.files:
        return jsonify(error="missing form field 'file' (.tar.gz required)"), 400

    commit = (request.form.get("commit") or "").strip()
    if not commit or not COMMIT_HASH_RE.match(commit):
        return jsonify(error="missing/invalid 'commit' (>=7 hex chars required)"), 400
    commit = commit[:7]

    uploaded = request.files["file"]
    if not uploaded.filename.lower().endswith(".tar.gz"):
        return jsonify(error="uploaded file must have .tar.gz extension"), 400

    tmp_dir = Path(tempfile.mkdtemp(prefix="upload_repo_", dir=str(Path.cwd())))
    tar_path = tmp_dir / "upload.tar.gz"
    uploaded.save(tar_path)

    repo_dir = None

    try:
        with open(tar_path, "rb") as f:
            safe_extract_tar_gz(io.BytesIO(f.read()), tmp_dir)

        repo_dir = find_repo_root(tmp_dir)
        if not repo_dir:
            return jsonify(error="no Git repository (.git) found in the extracted content"), 400

        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "checkout", "--quiet", commit],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if proc.returncode != 0:
            return jsonify(
                error="git checkout failed",
                stdout=proc.stdout,
                stderr=proc.stderr,
            ), 400
        
        simian_result = run_simian(str(repo_dir))

        return Response(
            simian_result,
            status=200,
            mimetype="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )

    except tarfile.ReadError:
        return jsonify(error="invalid or corrupted .tar.gz"), 400
    except ValueError as ve:
        return jsonify(error=str(ve)), 400
    except subprocess.TimeoutExpired:
        return jsonify(error="timeout while running git"), 504
    except Exception as e:
        return jsonify(error=f"unexpected error: {e.__class__.__name__}"), 500
    finally:
        try:
            if tar_path.exists():
                tar_path.unlink()
        except Exception:
            pass
        try:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@app.get("/")
def health():
    return jsonify(status="ok", service="Simian-api")

def run_dev():
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)

# permite: `poetry run python -m myapi.app`
if __name__ == "__main__":
    run_dev()
