"""PyInstaller entry point for the standalone `bp` executable.

PyInstaller freezes a script, not a console-script entry point, so this is the script.
It must use an absolute import: the script runs as `__main__`, with no parent package.

stdout/stderr are switched to UTF-8 because Blueprint's messages contain non-ASCII text and
on Windows a redirected stream (a pipe to an MCP client, a file) otherwise takes the ANSI code
page and can raise UnicodeEncodeError. Files are unaffected: Blueprint opens them with an
explicit encoding. This only applies to the frozen exe; the PyPI `bp` is unchanged.
"""

import sys

from blueprint.cli import main

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
