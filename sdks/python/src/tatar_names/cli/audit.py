from __future__ import annotations

import json

from tatar_names.audit import analyze_patterns


def main() -> None:
    print(json.dumps(analyze_patterns(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
