"""
The CDSCO endpoint accepts iDisplayStart and iDisplayLength and then ignores
them, returning the whole registry in every response. These tests pin the
behaviour that follows from that.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.scrapers.cdsco import CDSCOScraper


def _record(n: int) -> dict:
    return {
        "firm_name": f"Firm {n}",
        "license_number": f"LIC-{n}",
        "generic_name": f"Generic {n}",
        "brand_name": f"Brand {n}",
    }


def _response(rows: list, total: int) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"aaData": rows, "iTotalRecords": total}
    return response


@pytest.fixture
def scraper(tmp_path):
    with patch("src.scrapers.cdsco.SEEDS_DIR", tmp_path), patch(
        "src.scrapers.cdsco.REFERENCE_CSV", tmp_path / "cdsco_reference.csv"
    ):
        instance = CDSCOScraper()
        instance.rate_limiter = MagicMock()
        yield instance


def test_stops_after_one_request_when_the_first_response_holds_everything(scraper):
    rows = [_record(n) for n in range(250)]
    scraper.session = MagicMock()
    scraper.session.get.return_value = _response(rows, total=250)

    with patch.object(scraper, "_fetch_single_page") as fetch_page:
        scraper.fetch_and_save(force=True)

    assert scraper.session.get.call_count == 1
    fetch_page.assert_not_called()


def test_writes_every_record_from_that_single_response(scraper):
    rows = [_record(n) for n in range(250)]
    scraper.session = MagicMock()
    scraper.session.get.return_value = _response(rows, total=250)

    with patch.object(scraper, "_write_reference_csv") as write_csv:
        scraper.fetch_and_save(force=True)

    written = write_csv.call_args.args[0]
    assert len(written) == 250


def test_still_paginates_when_the_server_honours_page_size(scraper):
    page_one = [_record(n) for n in range(100)]
    scraper.session = MagicMock()
    scraper.session.get.return_value = _response(page_one, total=300)

    with patch.object(scraper, "_fetch_single_page", return_value=[]) as fetch_page:
        scraper.fetch_and_save(force=True)

    # Pages 2 and 3, the first having arrived with the probe.
    assert fetch_page.call_count == 2
