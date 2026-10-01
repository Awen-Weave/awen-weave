"""No default may point at the decommissioned craidd Raspberry Pi.

Dispatch 502 (01/10/2026, ruled by Huw as Llys): the Pi is powered off only
once nothing calls it. Dispatch 498 found three defaults still dialling its
tailnet porth `100.68.238.84:8081`; all three read one constant,
`craidd.validation_gate.DEFAULT_PORTH_URL`. These tests fail if a Pi address
comes back as a default, by any of the three routes it could return:

  1. the constant itself;
  2. a function signature defaulting to something else;
  3. a CLI `--porth-url` default, read from the parsed namespace the CLI
     actually builds, not from its source text;

and, as a backstop, a Pi marker written anywhere in the shipped source.
"""

import argparse
import inspect
import sys
from pathlib import Path

import pytest

from craidd.validation_gate import DEFAULT_PORTH_URL, PorthValidator, default_gate

# The Pi's tailnet address (awen-registry DEPLOY.md:20-21 names it craidd) and
# the forms its hostname takes in a URL or an ssh target. Bare "craidd" is the
# package name, so it is not a marker on its own.
PI_MARKERS = ("100.68.238.84", "://craidd", "@craidd", "craidd:8081")

REPO = Path(__file__).resolve().parents[2]
SHIPPED = [REPO / "src", REPO / "client"]


def _is_pi(url: str) -> bool:
    return any(m in url for m in PI_MARKERS)


def test_default_porth_url_is_not_the_pi():
    assert not _is_pi(DEFAULT_PORTH_URL), DEFAULT_PORTH_URL


def test_default_porth_url_is_the_box_porth():
    # awen-porth deploy/mythic/Caddyfile:22 (vhost) + smoke-porth.sh:20 (/mcp).
    assert DEFAULT_PORTH_URL == "https://porth.awenweave.com/mcp"


@pytest.mark.parametrize("fn, param", [
    (PorthValidator.__init__, "url"),
    (default_gate, "porth_url"),
])
def test_signature_defaults_are_not_the_pi(fn, param):
    default = inspect.signature(fn).parameters[param].default
    assert default == DEFAULT_PORTH_URL
    assert not _is_pi(default)


class _Parsed(Exception):
    def __init__(self, ns):
        self.ns = ns


@pytest.mark.parametrize("module, target", [
    ("cli.craidd_snapshot", "dolgellau-gazetteer"),
    ("cli.craidd_return", "dolgellau"),
])
def test_cli_porth_url_default_is_not_the_pi(monkeypatch, module, target):
    mod = pytest.importorskip(module)
    real = argparse.ArgumentParser.parse_args

    def capture(self, args=None, namespace=None):
        raise _Parsed(real(self, args, namespace))

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    with pytest.raises(_Parsed) as got:
        mod.main([target])
    url = got.value.ns.porth_url
    assert not _is_pi(url), f"{module} --porth-url defaults to {url}"
    assert url == DEFAULT_PORTH_URL


def test_no_pi_marker_in_shipped_source():
    hits = []
    for root in SHIPPED:
        for path in sorted(root.rglob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _is_pi(line):
                    hits.append(f"{path.relative_to(REPO)}:{n}: {line.strip()}")
    assert not hits, "Pi address in shipped source:\n" + "\n".join(hits)


def test_the_scan_sees_a_planted_pi_default(tmp_path, monkeypatch):
    """The backstop must red on a real Pi default, or its green means nothing."""
    planted = tmp_path / "src" / "planted.py"
    planted.parent.mkdir()
    planted.write_text('URL = "http://100.68.238.84:8081/mcp"\n', encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "SHIPPED", [tmp_path / "src"])
    monkeypatch.setattr(sys.modules[__name__], "REPO", tmp_path)
    with pytest.raises(AssertionError, match="planted.py:1"):
        test_no_pi_marker_in_shipped_source()
