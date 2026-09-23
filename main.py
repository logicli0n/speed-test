#!/usr/bin/env python3
"""Простой замерщик скорости интернет-соединения.

Скрипт выполняет несколько последовательных HTTP GET запросов к указанному
URL (как правило, это большой файл/картинка), измеряет время каждого запроса
и объём скачанных данных, после чего печатает сводную статистику: среднее
время запроса и среднюю скорость скачивания.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass

import requests

DEFAULT_URL = "https://proof.ovh.net/files/10Mb.dat"
DEFAULT_REQUEST_COUNT = 10
DEFAULT_TIMEOUT_SECONDS = 30
CHUNK_SIZE_BYTES = 1024 * 64
BYTES_PER_MB = 1_000_000


@dataclass(frozen=True)
class RequestResult:
    elapsed_seconds: float
    downloaded_bytes: int

    @property
    def speed_mbps(self) -> float:
        return (self.downloaded_bytes / BYTES_PER_MB) / self.elapsed_seconds


def run_single_request(url: str, timeout: float) -> RequestResult:
    """Выполняет один GET запрос и возвращает время выполнения и объём данных."""
    downloaded_bytes = 0
    start = time.perf_counter()
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE_BYTES):
            downloaded_bytes += len(chunk)
    elapsed = time.perf_counter() - start
    return RequestResult(elapsed_seconds=elapsed, downloaded_bytes=downloaded_bytes)


def measure_speed(url: str, count: int, timeout: float) -> list[RequestResult]:
    """Последовательно выполняет `count` запросов, печатая прогресс по каждому."""
    results: list[RequestResult] = []
    for attempt in range(1, count + 1):
        try:
            result = run_single_request(url, timeout)
        except requests.exceptions.RequestException as exc:
            print(f"[{attempt}/{count}] ошибка запроса: {exc}", file=sys.stderr)
            continue

        results.append(result)
        print(
            f"[{attempt}/{count}] "
            f"время: {result.elapsed_seconds:.3f} с, "
            f"объём: {result.downloaded_bytes / BYTES_PER_MB:.2f} МБ, "
            f"скорость: {result.speed_mbps:.2f} МБ/с"
        )
    return results


def print_summary(results: list[RequestResult]) -> None:
    if not results:
        print("Ни один запрос не завершился успешно.", file=sys.stderr)
        return

    total_bytes = sum(r.downloaded_bytes for r in results)
    total_time = sum(r.elapsed_seconds for r in results)
    avg_time = statistics.mean(r.elapsed_seconds for r in results)
    avg_speed = (total_bytes / BYTES_PER_MB) / total_time

    print("\n--- Итог ---")
    print(f"Успешных запросов:   {len(results)}")
    print(f"Среднее время запроса: {avg_time:.3f} с")
    print(f"Скачано данных всего:  {total_bytes / BYTES_PER_MB:.2f} МБ")
    print(f"Средняя скорость:      {avg_speed:.2f} МБ/с")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help="URL файла для скачивания (по умолчанию: тестовый файл 10 МБ на proof.ovh.net)",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=DEFAULT_REQUEST_COUNT,
        help=f"количество последовательных запросов (по умолчанию: {DEFAULT_REQUEST_COUNT})",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"таймаут одного запроса в секундах (по умолчанию: {DEFAULT_TIMEOUT_SECONDS})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"Замер скорости: {args.url}\n")
    results = measure_speed(args.url, args.count, args.timeout)
    print_summary(results)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
