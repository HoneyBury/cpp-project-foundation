"""C++ project foundation tooling."""

import sys

if sys.version_info < (3, 11):  # noqa: UP036 - provide a clear runtime message
    raise SystemExit(
        "cpp-project-foundation requires Python 3.11 or newer; "
        f"detected Python {sys.version_info.major}.{sys.version_info.minor}."
    )

__version__ = "0.4.0"
