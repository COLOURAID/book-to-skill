import sys
from pathlib import Path


def read_text_file(path: str) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return Path(path).read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except (OSError, PermissionError) as exc:
            print(f"Cannot read {path}: {exc}", file=sys.stderr)
            return None
    return None
