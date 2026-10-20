from datetime import date

import httpx
import pytest

from sp_designer.prices.providers import UmicoreProvider, parse_latest_price
from sp_designer.prices.store import PriceEntry, PriceStore


@pytest.mark.parametrize("text, expected", [
    ("Date,Price\n2026-10-17,9150.00\n2026-10-19,9200.00\n", (date(2026, 10, 19), 9200.0)),
    ("Datum;Preis\n17.10.2026;9.150,00\n19.10.2026;9.200,00\n", (date(2026, 10, 19), 9200.0)),
    ('"date","value"\n"19-10-2026","1,641.00"\n"18-10-2026","1,630.50"\n', (date(2026, 10, 19), 1641.0)),
    ("2026-10-19T10:00:00,Umicore,9200\n", (date(2026, 10, 19), 9200.0)),
])
def test_parse_latest_price(text, expected):
    assert parse_latest_price(text) == expected


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_latest_price("<html>not a csv</html>")


def test_umicore_provider_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/IR/" in request.url.path:
            return httpx.Response(200, text="Date,Price\n2026-10-19,9200\n")
        return httpx.Response(503)

    provider = UmicoreProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = provider.fetch(today=date(2026, 10, 20))
    assert [e.metal for e in result.entries] == ["Ir"]
    assert result.entries[0].origin == "auto"
    assert set(result.errors) == {"Pt", "Pd", "Rh", "Ru"}


def test_store_latest_and_persistence(tmp_path):
    store = PriceStore(tmp_path)
    assert store.latest("Ir").origin == "seed"
    store.add(PriceEntry(metal="Ir", value=9500, date="2026-10-20", origin="manual"))
    store.add(PriceEntry(metal="Ir", value=9400, date="2026-10-20", origin="auto"))
    assert store.latest("Ir").value == 9500  # manual wins on the same day
    assert PriceStore(tmp_path).latest("Ir").value == 9500
    assert store.delete("Ir", "2026-10-20", "manual")
    assert store.latest("Ir").value == 9400
    with pytest.raises(ValueError):
        store.add(PriceEntry(metal="Ni", value=1, date="20.10.2026"))
