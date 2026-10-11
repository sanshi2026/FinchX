"""基础安装不依赖可选库或系统 IANA 时区数据库。"""

from pathlib import Path
import subprocess
import sys


def test_base_import_without_timezone_database_or_optional_dependencies():
    source_root = Path(__file__).resolve().parents[1] / "src"
    script = """
import importlib.abc
import sys
import zoneinfo

sys.path.insert(0, sys.argv[1])
zoneinfo.reset_tzpath(())

class BlockDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'tzdata', 'pandas_market_calendars', 'playwright', 'pypdfium2'
        }:
            raise ModuleNotFoundError('dependency intentionally unavailable')

sys.meta_path.insert(0, BlockDependencies())

from finchx import FinchX
from finchx.sources.tonghuashun import articles

client = FinchX()
assert callable(client.articles.ths_get)
assert articles._timestamp(0, '时间戳') == '1970-01-01T08:00:00+08:00'
assert articles._source_time('2026-10-09 09:30') == (
    '2026-10-09T09:30+08:00', None
)
assert articles._source_time('2026-10-09T01:30:00Z') == (
    '2026-10-09T09:30:00+08:00', None
)
assert not {'tzdata', 'pandas_market_calendars', 'playwright', 'pypdfium2'} & sys.modules.keys()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(source_root)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
