from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """CWD-independent entry point for Hermes Desktop / GUI operators.

    The package is installed editable from the harness checkout. Resolve the
    controller from this module's own location rather than trusting the GUI
    session working directory.
    """
    root = Path(__file__).resolve().parents[1]
    controller = root / "integrations" / "hermes" / "pilot_controller.py"
    runtime = root / "write_runtime.py"
    if not runtime.is_file() or not controller.is_file():
        print(
            f"deterministic writing runtime checkout is incomplete: {root}",
            file=sys.stderr,
        )
        return 2

    args = list(sys.argv[1:] if argv is None else argv)
    proc = subprocess.run([sys.executable, str(controller), *args], cwd=root)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
