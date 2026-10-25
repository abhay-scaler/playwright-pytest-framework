import importlib


def test_worker_id_defaults_to_main_when_serial(monkeypatch):
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

    import pwpf.utils.logger as logger_module

    reloaded = importlib.reload(logger_module)

    assert reloaded.WORKER_ID == "main"


def test_worker_id_reflects_xdist_worker_env_var(monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")

    import pwpf.utils.logger as logger_module

    reloaded = importlib.reload(logger_module)

    assert reloaded.WORKER_ID == "gw3"


def test_log_records_are_attributed_to_the_worker(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw7")
    monkeypatch.setattr("pwpf.config.settings.log_dir", lambda: tmp_path)

    import pwpf.utils.logger as logger_module

    reloaded = importlib.reload(logger_module)
    # Each call gets a fresh, unique logger name so this test's handler isn't
    # short-circuited by another test's already-attached handlers for the
    # same logger name (get_logger is a no-op on a logger that already has
    # handlers - see the duplicate-handler guard below).
    logger = reloaded.get_logger("tests.test_logger.gw7_case")
    logger.info("hello from a worker")

    log_file = tmp_path / "gw7" / "framework.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "[gw7]" in contents
    assert "hello from a worker" in contents


def test_get_logger_does_not_duplicate_handlers():
    import pwpf.utils.logger as logger_module

    logger = logger_module.get_logger("tests.test_logger.duplicate_guard_case")
    handler_count = len(logger.handlers)

    same_logger = logger_module.get_logger("tests.test_logger.duplicate_guard_case")

    assert same_logger is logger
    assert len(same_logger.handlers) == handler_count
