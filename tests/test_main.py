from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

import main


def make_fake_response(chunks: list[bytes]) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.raise_for_status.return_value = None
    response.iter_content.return_value = iter(chunks)
    return response


def test_request_result_speed_mbps() -> None:
    result = main.RequestResult(elapsed_seconds=2.0, downloaded_bytes=10_000_000)
    assert result.speed_mbps == pytest.approx(5.0)


def test_run_single_request_sums_downloaded_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [b"a" * 1000, b"b" * 500, b"c" * 250]
    fake_response = make_fake_response(chunks)
    monkeypatch.setattr(main.requests, "get", MagicMock(return_value=fake_response))

    result = main.run_single_request("https://example.com/file", timeout=5)

    assert result.downloaded_bytes == sum(len(c) for c in chunks)
    assert result.elapsed_seconds >= 0
    main.requests.get.assert_called_once_with(
        "https://example.com/file", stream=True, timeout=5
    )


def test_run_single_request_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = make_fake_response([])
    fake_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
    monkeypatch.setattr(main.requests, "get", MagicMock(return_value=fake_response))

    with pytest.raises(requests.exceptions.HTTPError):
        main.run_single_request("https://example.com/missing", timeout=5)


def test_measure_speed_skips_failed_requests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ok_result = main.RequestResult(elapsed_seconds=1.0, downloaded_bytes=1_000_000)
    calls = [requests.exceptions.ConnectionError("boom"), ok_result, ok_result]

    def fake_run_single_request(url: str, timeout: float) -> main.RequestResult:
        outcome = calls.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(main, "run_single_request", fake_run_single_request)

    results = main.measure_speed("https://example.com/file", count=3, timeout=5)

    assert results == [ok_result, ok_result]
    assert "ошибка запроса" in capsys.readouterr().err


def test_print_summary_with_results(capsys: pytest.CaptureFixture[str]) -> None:
    results = [
        main.RequestResult(elapsed_seconds=1.0, downloaded_bytes=5_000_000),
        main.RequestResult(elapsed_seconds=1.0, downloaded_bytes=5_000_000),
    ]

    main.print_summary(results)
    out = capsys.readouterr().out

    assert "Успешных запросов:   2" in out
    assert "Скачано данных всего:  10.00 МБ" in out
    assert "Средняя скорость:      5.00 МБ/с" in out


def test_print_summary_without_results(capsys: pytest.CaptureFixture[str]) -> None:
    main.print_summary([])
    err = capsys.readouterr().err

    assert "Ни один запрос не завершился успешно" in err


def test_parse_args_defaults() -> None:
    args = main.parse_args([])

    assert args.url == main.DEFAULT_URL
    assert args.count == main.DEFAULT_REQUEST_COUNT
    assert args.timeout == main.DEFAULT_TIMEOUT_SECONDS


def test_parse_args_overrides() -> None:
    args = main.parse_args(["https://example.com/file", "-n", "3", "-t", "7.5"])

    assert args.url == "https://example.com/file"
    assert args.count == 3
    assert args.timeout == 7.5


def test_main_returns_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    result = main.RequestResult(elapsed_seconds=1.0, downloaded_bytes=1_000_000)
    monkeypatch.setattr(main, "measure_speed", MagicMock(return_value=[result]))

    assert main.main(["https://example.com/file", "-n", "1"]) == 0


def test_main_returns_one_when_all_requests_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "measure_speed", MagicMock(return_value=[]))

    assert main.main(["https://example.com/file", "-n", "1"]) == 1
