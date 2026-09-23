"""Read-only comparison of supported build-result evidence."""
import json
from pathlib import Path

from hermeneia.build_reproducibility import compare_builds


def cmd_build_compare(left: str, right: str, *, left_root: str, right_root: str) -> None:
    result = compare_builds(Path(left).absolute(), Path(right).absolute(),
                            left_root=Path(left_root), right_root=Path(right_root))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if any(result[side]["integrity"] == "invalid" for side in ("left", "right")):
        raise SystemExit(3)
    raise SystemExit({"equivalent": 0, "different": 1, "unsupported": 2}[result["comparison"]])
