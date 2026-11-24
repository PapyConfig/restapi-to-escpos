import base64
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from escpos_api.models import ImageCommand, PrintJob

EXAMPLES = Path(__file__).parent.parent / "examples"


def job(*commands, **kw):
    return PrintJob.model_validate({"commands": list(commands), **kw})


@pytest.mark.parametrize(
    "command",
    [
        {"type": "unknown"},
        {"type": "text"},
        {"type": "text", "content": ""},
        {"type": "text", "content": "x", "width": 9},
        {"type": "text", "content": "x", "colour": "red"},
        {"type": "style"},
        {"type": "feed", "lines": 0},
        {"type": "separator", "char": "--"},
        {"type": "qr", "content": "x", "ec": "Z"},
        {"type": "barcode", "content": "1", "symbology": "PDF417"},
        {"type": "image", "data": "not base64!"},
        {"type": "cut", "mode": "half"},
        {"type": "cashdraw", "pin": 3},
    ],
)
def test_invalid_commands(command):
    with pytest.raises(ValidationError):
        job(command)


def test_job_bounds():
    with pytest.raises(ValidationError):
        PrintJob.model_validate({"commands": []})
    with pytest.raises(ValidationError):
        job(*[{"type": "feed"}] * 501)


def test_data_url_is_accepted():
    payload = base64.b64encode(b"abc").decode()
    cmd = ImageCommand(type="image", data=f"data:image/png;base64,{payload}")
    assert cmd.image_bytes() == b"abc"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.json")), ids=lambda p: p.name)
def test_examples_are_valid_jobs(path):
    PrintJob.model_validate(json.loads(path.read_text()))


def test_openapi_example_is_valid():
    example = PrintJob.model_config["json_schema_extra"]["examples"][0]
    PrintJob.model_validate(example)
