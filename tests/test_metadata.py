import json
import subprocess
import sys

from conftest import ROOT
from scripts.metadata_generator import generate_metadata


def test_generate_metadata():
    res = generate_metadata("waterfall")
    assert res["status"] == "SUCCESS"
    assert len(res["title"]) <= 100
    assert "Waterfall" in res["title"]
    assert "#waterfall" in res["hashtags"]


def test_topic_is_not_forced_into_nature():
    res = generate_metadata("city traffic at night")
    assert "Nature" not in res["title"]
    assert "#citytrafficatnight" in res["hashtags"]


def test_long_topic_stays_within_limit():
    assert len(generate_metadata("x" * 300)["title"]) <= 100


def test_empty_topic_fails():
    assert generate_metadata("   ")["status"] == "FAILED"


def test_output_file(tmp_path):
    out = tmp_path / "meta.json"
    subprocess.run([sys.executable, "scripts/metadata_generator.py", "--topic", "rain", "--output", str(out)], cwd=ROOT, check=True, capture_output=True)
    assert json.loads(out.read_text())["topic"] == "rain"
