import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

# Ensure src.* imports resolve when running pytest from apps/etl/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.loaders.supabase_loader import SupabaseLoader


class FakeExecuteResponse:
    def __init__(self, data=None):
        self.data = data or []


class FakeTable:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.pending_payload = None
        self.pending_update = None
        self.eq_filters = []
        self.operation = None
        self.limit_value = None
        self.range_bounds = None

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.pending_payload = payload
        self.client.upsert_calls.append((self.name, payload, on_conflict))
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.pending_payload = payload
        self.client.insert_calls.append((self.name, payload))
        return self

    def select(self, *_args):
        self.operation = "select"
        self.client.last_select_args = _args
        self.client.select_calls.append(self.name)
        return self

    def update(self, payload):
        self.operation = "update"
        self.pending_update = payload
        return self

    def eq(self, column, value):
        self.eq_filters.append((column, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def execute(self):
        if self.operation == "select":
            rows = list(self.client.table_rows.get(self.name, []))
            for column, value in self.eq_filters:
                rows = [row for row in rows if row.get(column) == value]
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            if self.range_bounds is not None:
                start, end = self.range_bounds
                rows = rows[start : end + 1]
            return FakeExecuteResponse(rows)

        if self.operation == "update":
            row_id = next(
                (value for column, value in self.eq_filters if column == "id"), None
            )
            if row_id in self.client.update_fail_ids:
                raise Exception("503: retry metadata update failed")
            self.client.update_calls.append(
                (self.name, self.pending_update, self.eq_filters)
            )
            for row in self.client.retry_rows:
                if row.get("id") == row_id:
                    row.update(self.pending_update)
            return FakeExecuteResponse()

        if self.operation == "insert":
            payload = dict(self.pending_payload)
            payload.setdefault("id", f"insert-{len(self.client.retry_rows) + 1}")
            self.client.retry_rows.append(payload)
            self.client.table_rows.setdefault(self.name, []).append(payload)
            return FakeExecuteResponse()

        if self.operation == "upsert":
            payload = self.pending_payload
            if isinstance(payload, list) and len(payload) > 1:
                self.client.transient_batch_attempts += 1
                if (
                    self.client.transient_batch_attempts
                    <= self.client.transient_batch_failures
                ):
                    raise TimeoutError("connection timed out during batch upsert")
            if (
                isinstance(payload, list)
                and len(payload) > 1
                and self.client.fail_batches
            ):
                raise Exception("22P02: invalid input syntax for type double precision")
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                if row.get("generic_name") in self.client.errors_by_generic_name:
                    raise Exception(
                        self.client.errors_by_generic_name[row.get("generic_name")]
                    )
                if row.get("generic_name") in self.client.fail_generic_names:
                    raise Exception(
                        "23505: duplicate key value violates unique constraint"
                    )
            for row in rows:
                self.client.upsert_table_row(self.name, row)
            return FakeExecuteResponse()

        return FakeExecuteResponse()


class FakeSupabaseClient:
    def __init__(
        self,
        *,
        fail_batches=False,
        fail_generic_names=None,
        retry_rows=None,
        errors_by_generic_name=None,
        update_fail_ids=None,
        table_rows=None,
        transient_batch_failures=0,
    ):
        self.fail_batches = fail_batches
        self.fail_generic_names = set(fail_generic_names or [])
        self.errors_by_generic_name = errors_by_generic_name or {}
        self.retry_rows = retry_rows or []
        self.update_fail_ids = set(update_fail_ids or [])
        self.table_rows = table_rows if table_rows is not None else {"medicines": []}
        self.transient_batch_failures = transient_batch_failures
        self.transient_batch_attempts = 0
        self.upsert_calls = []
        self.insert_calls = []
        self.update_calls = []
        self.last_select_args = None
        self.select_calls = []

    def table(self, name):
        return FakeTable(name, self)

    def upsert_table_row(self, table, row):
        rows = self.table_rows.setdefault(table, [])
        if table == "medicines":
            conflict_columns = (
                "generic_name",
                "brand_name",
                "manufacturer",
                "barcode_id",
            )
        else:
            rows.append(dict(row))
            return

        for existing in rows:
            if all(
                existing.get(column) == row.get(column) for column in conflict_columns
            ):
                existing.update(row)
                return
        rows.append(dict(row))


def make_loader(client, tmp_path):
    loader = SupabaseLoader.__new__(SupabaseLoader)
    loader.client = client
    loader.failed_rows_dir = tmp_path
    loader.pipeline_name = "janaushadhi"
    return loader


def test_batch_success_returns_summary_without_failed_rows_csv(tmp_path):
    client = FakeSupabaseClient()
    loader = make_loader(client, tmp_path)
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "strength": "500mg",
                "dosage_form": "Tablet",
            },
            {"generic_name": "Cetirizine", "strength": "10mg", "dosage_form": "Tablet"},
        ]
    )

    stats = loader.load(df)

    assert stats["total"] == 2
    assert stats["inserted"] == 2
    assert stats["failed"] == 0
    assert stats["skipped_unchanged"] == 0
    assert stats["success_rate"] == 100.0
    assert stats["error_counts"] == {}
    assert stats["failed_rows_csv"] is None
    assert len(client.upsert_calls) == 1


def test_transient_batch_upsert_retries_with_exponential_backoff(tmp_path, monkeypatch):
    client = FakeSupabaseClient(transient_batch_failures=2)
    loader = make_loader(client, tmp_path)
    sleep_calls = []
    monkeypatch.setattr(
        "src.loaders.supabase_loader.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "strength": "500mg",
                "dosage_form": "Tablet",
            },
            {"generic_name": "Cetirizine", "strength": "10mg", "dosage_form": "Tablet"},
        ]
    )

    stats = loader.load(df)

    assert stats["total"] == 2
    assert stats["inserted"] == 2
    assert stats["failed"] == 0
    assert stats["failed_rows_csv"] is None
    assert client.transient_batch_attempts == 3
    assert len(client.upsert_calls) == 3
    assert all(len(payload) == 2 for _, payload, _ in client.upsert_calls)
    assert len(sleep_calls) == 2

    assert 2.1 <= sleep_calls[0] <= 3.0
    assert 4.1 <= sleep_calls[1] <= 5.0


def test_transient_batch_upsert_falls_back_after_retries(tmp_path, monkeypatch):
    client = FakeSupabaseClient(transient_batch_failures=4)
    loader = make_loader(client, tmp_path)
    sleep_calls = []
    monkeypatch.setattr(
        "src.loaders.supabase_loader.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "strength": "500mg",
                "dosage_form": "Tablet",
            },
            {"generic_name": "Cetirizine", "strength": "10mg", "dosage_form": "Tablet"},
        ]
    )

    stats = loader.load(df)

    assert stats["inserted"] == 2
    assert stats["failed"] == 0
    assert client.transient_batch_attempts == 4
    assert [len(payload) for _, payload, _ in client.upsert_calls] == [
        2,
        2,
        2,
        2,
        1,
        1,
    ]
    assert len(sleep_calls) == 3

    assert 2.1 <= sleep_calls[0] <= 3.0
    assert 4.1 <= sleep_calls[1] <= 5.0
    assert 8.1 <= sleep_calls[2] <= 9.0


def test_load_skips_unchanged_rows_already_present_in_target_db(tmp_path):
    table_rows = {"medicines": []}
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Micro Labs",
                "strength": "500mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000012",
                "mrp": 18.5,
                "cdsco_match_score": 97.2,
            },
            {
                "generic_name": "Cetirizine",
                "brand_name": "Cetzine",
                "manufacturer": "GSK",
                "strength": "10mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000029",
                "mrp": 25.0,
                "cdsco_match_score": 95.0,
            },
        ]
    )

    first_client = FakeSupabaseClient(table_rows=table_rows)
    first_loader = make_loader(first_client, tmp_path)
    first_stats = first_loader.load(df)

    second_client = FakeSupabaseClient(table_rows=table_rows)
    second_loader = make_loader(second_client, tmp_path)
    validation_only_change = df.copy()
    validation_only_change["cdsco_match_score"] = [88.1, 90.4]
    second_stats = second_loader.load(validation_only_change)

    assert first_stats["inserted"] == 2
    assert first_stats["skipped_unchanged"] == 0
    assert len(first_client.upsert_calls) == 1

    assert second_stats["total"] == 2
    assert second_stats["inserted"] == 2
    assert second_stats["failed"] == 0
    assert second_stats["skipped_unchanged"] == 0
    assert second_stats["success_rate"] == 100.0
    assert len(second_client.upsert_calls) == 1
    _, payload, _ = second_client.upsert_calls[0]
    assert [row["cdsco_match_score"] for row in payload] == [88.1, 90.4]


def test_load_does_not_request_invalid_fingerprint_column(tmp_path):
    client = FakeSupabaseClient(table_rows={"medicines": []})
    loader = make_loader(client, tmp_path)
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Micro Labs",
                "strength": "500mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000012",
                "mrp": 18.5,
            }
        ]
    )

    loader.load(df)

    assert client.last_select_args is not None
    assert all("fingerprint" not in str(arg) for arg in client.last_select_args)


def test_load_preserves_existing_jan_aushadhi_price_when_payload_has_null(tmp_path):
    existing_row = {
        "generic_name": "Paracetamol",
        "brand_name": "Dolo",
        "manufacturer": "Micro Labs",
        "strength": "500mg",
        "dosage_form": "Tablet",
        "source": "commercial",
        "barcode_id": "8900000000012",
        "mrp": 18.5,
        "jan_aushadhi_price": 42.0,
    }
    client = FakeSupabaseClient(table_rows={"medicines": [existing_row.copy()]})
    loader = make_loader(client, tmp_path)
    df = pd.DataFrame(
        [
            {
                **existing_row,
                "mrp": 18.5,
                "jan_aushadhi_price": None,
            }
        ]
    )

    stats = loader.load(df)

    assert stats["total"] == 1
    assert stats["inserted"] == 0
    assert stats["failed"] == 0
    assert stats["skipped_unchanged"] == 1
    assert len(client.upsert_calls) == 0
    assert client.table_rows["medicines"][0]["jan_aushadhi_price"] == 42.0


def test_load_persists_cdsco_validation_evidence_fields(tmp_path):
    client = FakeSupabaseClient(table_rows={"medicines": []})
    loader = make_loader(client, tmp_path)
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo 650",
                "manufacturer": "Micro Labs",
                "barcode_id": "8900000000012",
                "cdsco_approval_status": "approved",
                "is_counterfeit_alert": False,
                "is_cdsco_verified": True,
                "cdsco_match_score": 97.2,
                "matched_cdsco_product": "Dolo 650",
                "matched_cdsco_manufacturer": "Micro Labs",
                "product_match_score": 96.0,
                "manufacturer_match_score": 100.0,
            }
        ]
    )

    stats = loader.load(df)

    assert stats["inserted"] == 1
    assert len(client.upsert_calls) == 1
    _, payload, _ = client.upsert_calls[0]
    assert payload == [
        {
            "generic_name": "Paracetamol",
            "brand_name": "Dolo 650",
            "manufacturer": "Micro Labs",
            "barcode_id": "8900000000012",
            "cdsco_approval_status": "approved",
            "is_counterfeit_alert": False,
            "is_cdsco_verified": True,
            "cdsco_match_score": 97.2,
            "matched_cdsco_product": "Dolo 650",
            "matched_cdsco_manufacturer": "Micro Labs",
            "product_match_score": 96.0,
            "manufacturer_match_score": 100.0,
        }
    ]


def test_load_upserts_only_rows_whose_hash_changed(tmp_path):
    table_rows = {"medicines": []}
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Micro Labs",
                "strength": "500mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000012",
                "mrp": 18.5,
            },
            {
                "generic_name": "Cetirizine",
                "brand_name": "Cetzine",
                "manufacturer": "GSK",
                "strength": "10mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000029",
                "mrp": 25.0,
            },
        ]
    )
    changed_df = df.copy()
    changed_df.loc[changed_df["generic_name"] == "Cetirizine", "mrp"] = 27.5

    first_client = FakeSupabaseClient(table_rows=table_rows)
    first_loader = make_loader(first_client, tmp_path)
    first_loader.load(df)

    second_client = FakeSupabaseClient(table_rows=table_rows)
    second_loader = make_loader(second_client, tmp_path)
    stats = second_loader.load(changed_df)

    assert stats["total"] == 2
    assert stats["inserted"] == 1
    assert stats["failed"] == 0
    assert stats["skipped_unchanged"] == 1
    assert stats["success_rate"] == 100.0
    assert len(second_client.upsert_calls) == 1
    _, payload, _ = second_client.upsert_calls[0]
    assert payload == [
        {
            "generic_name": "Cetirizine",
            "brand_name": "Cetzine",
            "manufacturer": "GSK",
            "strength": "10mg",
            "dosage_form": "Tablet",
            "source": "commercial",
            "barcode_id": "8900000000029",
            "mrp": 27.5,
        }
    ]


def test_load_does_not_cache_failed_rows_until_successful_upsert(tmp_path):
    table_rows = {"medicines": []}
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Micro Labs",
                "strength": "500mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000012",
            },
            {
                "generic_name": "Cetirizine",
                "brand_name": "Cetzine",
                "manufacturer": "GSK",
                "strength": "10mg",
                "dosage_form": "Tablet",
                "source": "commercial",
                "barcode_id": "8900000000029",
            },
        ]
    )

    failing_client = FakeSupabaseClient(
        fail_batches=True,
        fail_generic_names={"Cetirizine"},
        table_rows=table_rows,
    )
    failing_loader = make_loader(failing_client, tmp_path)
    first_stats = failing_loader.load(df)

    retry_client = FakeSupabaseClient(table_rows=table_rows)
    retry_loader = make_loader(retry_client, tmp_path)
    retry_stats = retry_loader.load(df)

    assert first_stats["inserted"] == 1
    assert first_stats["failed"] == 1
    assert first_stats["skipped_unchanged"] == 0
    assert failing_client.transient_batch_attempts == 1

    assert retry_stats["inserted"] == 1
    assert retry_stats["failed"] == 0
    assert retry_stats["skipped_unchanged"] == 1
    assert len(retry_client.upsert_calls) == 1
    _, payload, _ = retry_client.upsert_calls[0]
    assert payload[0]["generic_name"] == "Cetirizine"


def test_load_does_not_skip_when_target_db_has_no_matching_rows(tmp_path):
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Micro Labs",
                "barcode_id": "8900000000012",
                "mrp": 18.5,
            }
        ]
    )

    client = FakeSupabaseClient(table_rows={"medicines": []})
    loader = make_loader(client, tmp_path)
    stats = loader.load(df)

    assert stats["inserted"] == 1
    assert stats["skipped_unchanged"] == 0
    assert len(client.upsert_calls) == 1


def test_load_treats_manufacturer_as_part_of_medicine_identity(tmp_path):
    table_rows = {
        "medicines": [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Micro Labs",
                "barcode_id": None,
                "mrp": 18.5,
            }
        ]
    }
    df = pd.DataFrame(
        [
            {
                "generic_name": "Paracetamol",
                "brand_name": "Dolo",
                "manufacturer": "Different Pharma",
                "barcode_id": None,
                "mrp": 18.5,
            }
        ]
    )

    client = FakeSupabaseClient(table_rows=table_rows)
    loader = make_loader(client, tmp_path)
    stats = loader.load(df)

    assert stats["inserted"] == 1
    assert stats["skipped_unchanged"] == 0
    assert len(client.upsert_calls) == 1
    _, _, on_conflict = client.upsert_calls[0]
    assert on_conflict == "generic_name,brand_name,manufacturer,barcode_id,source_product_code"


def _medicine_rows(count):
    return [
        {"generic_name": f"Medicine {i}", "brand_name": None, "manufacturer": None,
         "barcode_id": None, "source_product_code": str(i), "mrp": 10.0}
        for i in range(count)
    ]


def test_load_reads_the_existing_table_once_however_many_batches(tmp_path, monkeypatch):
    monkeypatch.setattr("src.loaders.supabase_loader.time.sleep", lambda _seconds: None)
    client = FakeSupabaseClient()
    loader = make_loader(client, tmp_path)

    stats = loader.load(pd.DataFrame(_medicine_rows(250)))

    assert stats["inserted"] == 250
    assert client.select_calls.count("medicines") == 1


def test_retrying_failed_rows_reads_the_existing_table_once(tmp_path):
    retry_rows = [
        {"id": f"retry-{i}", "pipeline_name": "janaushadhi", "status": "failed",
         "attempt_count": 1, "row_payload": row}
        for i, row in enumerate(_medicine_rows(3))
    ]
    client = FakeSupabaseClient(
        retry_rows=retry_rows,
        table_rows={"medicines": [], "etl_failed_rows": retry_rows},
    )
    loader = make_loader(client, tmp_path)

    stats = loader.retry_failed_rows()

    assert stats["inserted"] == 3
    assert client.select_calls.count("medicines") == 1
