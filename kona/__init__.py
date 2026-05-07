"""
KonaDB — A MySQL-compatible database engine with AI features.

Usage:
    import kona
    conn = kona.connect(":memory:")      # in-memory database
    conn = kona.connect("mydb.kona")     # file-based database
"""

__version__ = "1.0.0"
__author__ = "Kona"

from kona.core.connection import KonaConnection
from kona.core.database import KonaDB


def connect(database=":memory:", auto_save=True):
    """
    Connect to a KonaDB database.

    Args:
        database: Path to .kona file, or ":memory:" for in-memory mode.
        auto_save: If True, auto-save on every write (default: True).

    Returns:
        KonaConnection instance.

    Examples:
        >>> conn = kona.connect(":memory:")
        >>> conn = kona.connect("mydb.kona")
        >>> conn = kona.connect("data/app.kona", auto_save=False)
    """
    path = None if database == ":memory:" else database
    return KonaConnection(database_path=path, auto_save=auto_save)
