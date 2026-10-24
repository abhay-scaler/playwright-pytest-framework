from pwpf.utils.allure_cleanup import clean_allure_results


def test_clean_allure_results_removes_stale_files(tmp_path):
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir()
    (results_dir / "stale-result.json").write_text("{}", encoding="utf-8")
    stale_attachment_dir = results_dir / "stale-attachment-dir"
    stale_attachment_dir.mkdir()
    (stale_attachment_dir / "stale.txt").write_text("stale", encoding="utf-8")

    removed = clean_allure_results(results_dir)

    assert removed == 2
    assert list(results_dir.iterdir()) == []


def test_clean_allure_results_is_a_noop_when_directory_is_absent(tmp_path):
    missing_dir = tmp_path / "does-not-exist"

    removed = clean_allure_results(missing_dir)

    assert removed == 0
    assert not missing_dir.exists()
