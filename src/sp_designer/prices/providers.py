"""Automatic price providers.

Currently implemented: Umicore Precious Metals Management, which publishes indicative prices
for Pt, Pd, Rh, Ir and Ru and offers a CSV export per metal. Check Umicore's terms of use
before relying on it; the provider can be switched off in the settings.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import httpx

from .store import PriceEntry


@dataclass
class FetchResult:
    entries: list[PriceEntry] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class UmicoreProvider:
    name = "umicore"
    label = "Umicore PMM (Pt, Pd, Rh, Ir, Ru)"
    codes = {"Pt": "PT", "Pd": "PD", "Rh": "RH", "Ir": "IR", "Ru": "RU"}
    url = "https://pmm.umicore.com/api/chart/export/csv/{code}/{start}/{end}/AMUS/"

    def __init__(self, client: httpx.Client | None = None, lookback_days: int = 14) -> None:
        self.client = client or httpx.Client(timeout=20, follow_redirects=True)
        self.lookback_days = lookback_days

    def fetch(self, today: date | None = None) -> FetchResult:
        today = today or date.today()
        start = today - timedelta(days=self.lookback_days)
        result = FetchResult()
        for metal, code in self.codes.items():
            url = self.url.format(code=code, start=start.isoformat(), end=today.isoformat())
            try:
                response = self.client.get(url)
                response.raise_for_status()
                latest = parse_latest_price(response.text)
            except (httpx.HTTPError, ValueError) as exc:
                result.errors[metal] = str(exc) or exc.__class__.__name__
                continue
            entry_date, value = latest
            result.entries.append(PriceEntry(
                metal=metal, value=value, date=entry_date.isoformat(),
                source="Umicore PMM (automatic, indicative)", origin="auto",
            ))
        return result


PROVIDERS = {UmicoreProvider.name: UmicoreProvider}

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%Y", "%Y/%m/%d")


def _parse_date(text: str) -> date | None:
    text = text.strip().strip('"')
    candidate = text.split("T")[0].split(" ")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _parse_number(text: str) -> float | None:
    text = text.strip().strip('"').replace(" ", "").replace(" ", "")
    if not re.fullmatch(r"[0-9.,]+", text) or not re.search(r"\d", text):
        return None
    if "," in text and "." in text:
        # the right-most separator is the decimal separator
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = text.replace(",", "") if len(tail) == 3 and head else text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_latest_price(text: str) -> tuple[date, float]:
    """Return (date, price) of the most recent row in a price CSV export.

    The format is detected leniently: each row must contain a date cell followed by a numeric cell.
    """
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows: list[tuple[date, float]] = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        found_date: date | None = None
        for cell in row:
            if found_date is None:
                found_date = _parse_date(cell)
                continue
            number = _parse_number(cell)
            if number is not None and number > 0:
                rows.append((found_date, number))
                break
    if not rows:
        raise ValueError("no price rows found in response")
    return max(rows, key=lambda r: r[0])
