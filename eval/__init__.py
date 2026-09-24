# eval package
import sys as _sys

# Windows consoles default to cp1252 and choke on the unicode used in
# figure/experiment logging. Reconfigure once at package import so every
# eval module (run directly or via run_all) prints safely.
for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
