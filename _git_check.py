"""One-off helper; delete after verifying git."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
r = subprocess.run(
    ["git", "status", "--short"],
    cwd=root,
    capture_output=True,
    text=True,
)
Path(root / "_git_status_out.txt").write_text(
    r.stdout + "\n--- STDERR ---\n" + r.stderr + "\ncode=%s\n" % r.returncode,
    encoding="utf-8",
)
