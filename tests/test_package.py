import subprocess
import sys
import builtins
from datetime import date
from importlib.metadata import version as distribution_version
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 uses the tomli backport.
    import tomli as tomllib

import pytest


def test_public_import_and_version():
    import finchx
    import finchx as fx

    assert isinstance(finchx.__version__, str)
    assert fx.__version__ == finchx.__version__
    assert distribution_version("finchx") == finchx.__version__


def test_project_metadata_declares_supported_pydantic_floor():
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))

    assert "pydantic>=2.9,<3" in project["project"]["dependencies"]


def test_package_boundaries_import():
    import finchx.collectors
    import finchx.contracts
    import finchx.datasets
    import finchx.entities
    import finchx.providers
    import finchx.query
    import finchx.storage


def test_import_does_not_access_network():
    code = """
import socket

def forbidden(*args, **kwargs):
    raise AssertionError("network access during import")

socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden

import finchx
import finchx.config
import finchx.contracts
import finchx.entities
import finchx.providers
import finchx.datasets
import finchx.collectors
import finchx.storage
import finchx.query
from finchx import FinchX
FinchX()
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_client_construction_is_disk_free(tmp_path, monkeypatch):
    from finchx import FinchX

    monkeypatch.chdir(tmp_path)
    client = FinchX()

    assert isinstance(client, FinchX)
    assert tuple(tmp_path.iterdir()) == ()


def test_missing_optional_calendar_dependency_preserves_collector_semantics(monkeypatch):
    from finchx.collectors import Collector, MissingOptionalDependency
    from finchx.datasets import TRADING_CALENDAR_DATASET, TradingCalendarRequest
    from finchx.entities import Market

    real_import = builtins.__import__

    def missing_calendar(name, *args, **kwargs):
        if name == "pandas_market_calendars":
            raise ModuleNotFoundError(
                "No module named 'pandas_market_calendars'",
                name="pandas_market_calendars",
            )
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_calendar)
    request = TradingCalendarRequest(
        market=Market.CN_A,
        startDate=date(2026, 1, 1),
        endDate=date(2026, 1, 2),
    )

    with pytest.raises(MissingOptionalDependency, match="pandas_market_calendars"):
        Collector().fetch(
            TRADING_CALENDAR_DATASET,
            provider="pandas_market_calendars",
            request=request,
        )
