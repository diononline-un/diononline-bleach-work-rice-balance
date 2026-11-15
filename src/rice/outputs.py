import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Output:
    id: str
    connector: str
    width: int
    height: int
    x: int
    y: int
    primary: bool


def _default_json() -> str:
    return subprocess.run(
        ["kscreen-doctor", "-j"], capture_output=True, text=True, check=True
    ).stdout


def detect_outputs(json_text: str | None = None) -> list[Output]:
    data = json.loads(json_text if json_text is not None else _default_json())
    result = []
    for index, item in enumerate(data.get("outputs", [])):
        if not item.get("connected") or not item.get("enabled"):
            continue
        geometry = item.get("geometry", {})
        result.append(Output(
            id="main" if item.get("primary") else f"output-{index + 1}",
            connector=item["name"],
            width=int(geometry.get("width", 0)),
            height=int(geometry.get("height", 0)),
            x=int(geometry.get("x", 0)),
            y=int(geometry.get("y", 0)),
            primary=bool(item.get("primary")),
        ))
    return result
