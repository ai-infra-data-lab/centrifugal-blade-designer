"""Run existing tests without touching old caches or the system temp directory."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    run = ROOT / "artifacts" / "test-runs" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    temporary = run / "tmp"
    temporary.mkdir()
    environment = os.environ.copy()
    environment["PYTEST_DEBUG_TEMPROOT"] = str(temporary)
    environment["PYTHONUTF8"] = "1"
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error",
               "-p", "no:cacheprovider", "--junitxml=" + str(run / "pytest.xml")]
    command.extend(sys.argv[1:] or ["tests"])
    result = subprocess.run(command, cwd=ROOT, env=environment)
    (run / "result.json").write_text(json.dumps({
        "command": command, "python": sys.version, "returncode": result.returncode,
        "test_temp": str(temporary)
    }, indent=2) + "\n", encoding="utf-8")
    print("Test report:", run)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
