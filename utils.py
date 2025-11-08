import io
import os
import tarfile
from pathlib import Path

def is_within_directory(directory: Path, target: Path) -> bool:
    directory = directory.resolve()
    try:
        target = target.resolve()
    except FileNotFoundError:
        # During extraction, file may not exist yet; resolve parent safely
        target = (directory / target).resolve()
    return str(target).startswith(str(directory))


def safe_extract_tar_gz(fileobj: io.BytesIO, dest: Path) -> None:
    with tarfile.open(fileobj=fileobj, mode="r:gz") as tar:
        for member in tar.getmembers():
            name = member.name

            # Block absolute paths and parent directory escapes
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"unsafe entry detected in tar: {name}")

            # Block device files and FIFOs
            if member.isdev():
                raise ValueError(f"device/FIFO entries are not allowed: {name}")

            # Block hard links
            if member.islnk():
                raise ValueError(f"hard links are not allowed: {name}")

            # Block symbolic links (optional; you can allow with extra checks)
            if member.issym():
                raise ValueError(f"symbolic links are not allowed: {name}")

            target_path = dest / name
            if not is_within_directory(dest, target_path):
                raise ValueError(f"extraction would escape destination: {name}")

        # Passed all checks: extract
        tar.extractall(path=dest)


def find_repo_root(base: Path) -> Path | None:
    if (base / ".git").is_dir():
        return base

    children = [p for p in base.iterdir() if p.is_dir()]
    if len(children) == 1 and (children[0] / ".git").is_dir():
        return children[0]

    # Shallow recursive search (limit depth for performance)
    max_depth = 3
    for root, dirs, _files in os.walk(base):
        rel_parts = Path(root).relative_to(base).parts
        if len(rel_parts) > max_depth:
            dirs[:] = []
            continue
        if (Path(root) / ".git").is_dir():
            return Path(root)
    return None
