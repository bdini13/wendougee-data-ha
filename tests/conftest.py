"""Keep protocol-only tests runnable without installing Home Assistant."""

from importlib.util import find_spec

collect_ignore = ["ha"] if find_spec("homeassistant") is None else []
