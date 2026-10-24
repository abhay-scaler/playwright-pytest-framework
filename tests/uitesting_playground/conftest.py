import pytest

from pwpf.core.app_config import load_app_config


@pytest.fixture(scope="session")
def app_config():
    return load_app_config("uitesting_playground")
