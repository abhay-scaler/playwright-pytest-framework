"""Load the framework's own pytest plugin from the source tree.

An installed consumer gets `pwpf.plugin` automatically through the `pytest11`
entry point in pyproject.toml and needs no conftest.py for it. This repository
develops the plugin, so it points at the module directly: the suite then
exercises the same code path a consumer does, whether or not the distribution
happens to be installed in the current environment. pytest registers a plugin
module once, so having both routes available never double-registers it.
"""

pytest_plugins = ["pwpf.plugin"]
