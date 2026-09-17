"""
SahiDawa — Supabase Data Loader
=================================
Originally part of the ML service, which no longer exists.

Shared loader used by all ETL pipelines.
Accepts any normalized pd.DataFrame and upserts it into a Supabase table.

UPSERT STRATEGY:
    Conflict key: (generic_name, brand_name, manufacturer, barcode_id, source_product_code)
    On conflict → UPDATE (handles re-runs and MRP changes safely).

BATCH INSERTS:
    Rows are inserted in batches of 100 to reduce network round-trips.
    Transient batch failures are retried with exponential backoff.
    On final batch failure → falls back to row-by-row retry.
    Persistent failures are written to etl_failed_rows table + local CSV.
"""

import json
import os
import random
import re
import time
from collections.abc import Callable
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

from src.utils.logger import logger

# ── Environment ────────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

BATCH_SIZE = 100
DELAY_SEC = 0.5
BATCH_UPSERT_MAX_ATTEMPTS = 4
BATCH_UPSERT_INITIAL_BACKOFF_SEC = 2.0
BATCH_UPSERT_MAX_BACKOFF_SEC = 8.0
RETRY_TABLE = "etl_failed_rows"
SUCCESS_RATE_ALERT_THRESHOLD = 95.0
FAILED_ROWS_BASE_DIR = Path(__file__).resolve().parents[4] / "data" / "failed"

CONFLICT_COLUMNS = {
    "medicines": (
        "generic_name",
        "brand_name",
        "manufacturer",
        "barcode_id",
        # Jan Aushadhi rows have no brand or barcode, so without the source's own
        # product code every strength of one generic would share a key.
        "source_product_code",
    ),
    "pharmacies": (
        "name",
        "address",
    ),
}

ALLOWED_COLUMNS = {
    "medicines": {
        "id",
        "barcode_id",
        "brand_name",
        "generic_name",
        "manufacturer",
        "batch_number",
        "manufacturing_date",
        "expiry_date",
        "composition",
        "cdsco_approval_status",
        "is_counterfeit_alert",
        "is_cdsco_verified",
        "cdsco_match_score",
        "matched_cdsco_product",
        "matched_cdsco_manufacturer",
        "product_match_score",
        "manufacturer_match_score",
        "mrp",
        "jan_aushadhi_price",
        "strength",
        "dosage_form",
        "pack_size",
        "source_product_code",
        "schedule",
        "source",
        "created_at",
        "updated_at",
    },
    "pharmacies": {
        "name",
        "address",
        "district",
        "state",
        "pincode",
        "store_code",
        "phone_number",
        "is_active",
        "location",
    },
    "etl_failed_rows": {
        "id",
        "pipeline_name",
        "source_table",
        "row_fingerprint",
        "row_payload",
        "medicine_name",
        "unresolved_value",
        "error_category",
        "db_error_code",
        "error_message",
        "attempt_count",
        "status",
        "last_attempt_at",
        "created_at",
        "updated_at",
    },
}

TRANSIENT_UPSERT_ERROR_KEYWORDS = (
    "bad gateway",
    "connection aborted",
    "connection closed",
    "connection refused",
    "connection reset",
    "gateway timeout",
    "network",
    "remote protocol",
    "server disconnected",
    "service unavailable",
    "ssl",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "too many requests",
    "502",
    "503",
    "504",
)

TRANSIENT_UPSERT_EXCEPTION_NAME_KEYWORDS = (
    "connect",
    "connection",
    "network",
    "pooltimeout",
    "readerror",
    "remoteprotocol",
    "timeout",
    "writeerror",
)

PRESERVE_EXISTING_NULL_COLUMNS = {"jan_aushadhi_price"}


# ── Loader ─────────────────────────────────────────────────────────────────────


class SupabaseLoader:
    """
    Shared Supabase loader for all SahiDawa ETL pipelines.

    Usage:
        loader = SupabaseLoader(pipeline_name="janaushadhi")
        stats  = loader.load(df)
    """

    def __init__(
        self,
        pipeline_name: str,
        client: Client | None = None,
        failed_rows_dir: Path | None = None,
    ):
        self.pipeline_name = pipeline_name
        self.failed_rows_dir = failed_rows_dir or (FAILED_ROWS_BASE_DIR / pipeline_name)

        if client is not None:
            self.client = client
            return

        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError(
                "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.\n"
                "Copy .env.example to .env and fill in your Supabase credentials."
            )

        self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info(f"[Loader] Connected to Supabase: {SUPABASE_URL[:40]}...")

    def load(self, df: pd.DataFrame, table: str = "medicines") -> dict:
        """
        Upsert all rows from df into the given Supabase table.

        Returns:
            dict with keys: total, inserted, failed, success_rate,
                            error_counts, failed_rows_csv
        """
        total = len(df)
        logger.info(f"[Loader] Loading {total} records into '{table}'...")

        raw_records = df.to_dict(orient="records")
        records = []
        for i, row in enumerate(raw_records):
            payload = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            records.append(
                {
                    "row_index": i,
                    "payload": payload,
                    "write_payload": self._prepare_payload(payload, table),
                }
            )

        inserted, failures = 0, []
        # Read the table once per load. Reading it again for every batch made a
        # full load cost one whole-table read per 100 rows.
        existing_by_key = self._load_existing_rows_by_key(records, table)
        records_to_write, skipped_unchanged = self._filter_unchanged_records(
            records,
            table,
            existing_by_key,
        )

        if skipped_unchanged:
            logger.info(
                f"[Loader] Skipping {skipped_unchanged} unchanged records for "
                f"'{table}' based on current Supabase state"
            )

        writable_total = len(records_to_write)
        for batch_start in range(0, writable_total, BATCH_SIZE):
            batch = records_to_write[batch_start : batch_start + BATCH_SIZE]
            batch_end = batch_start + len(batch)
            try:
                payloads = [item["write_payload"] for item in batch]
                self._run_upsert_with_transient_retries(
                    lambda: self._upsert_payloads(payloads, table, existing_by_key),
                    "Batch upsert",
                )
                inserted += len(batch)
                logger.info(
                    f"[Loader] Batch {batch_start}–{batch_end} ✅  "
                    f"({inserted}/{writable_total} writes, {inserted + skipped_unchanged}/{total} processed)"
                )
            except Exception as e:
                logger.warning(
                    f"[Loader] Batch {batch_start}–{batch_end} ❌ {e} — retrying row-by-row"
                )
                bi, bf = self._load_batch_row_by_row(batch, table, existing_by_key)
                inserted += bi
                failures.extend(bf)

            if batch_end < writable_total:
                time.sleep(DELAY_SEC)

        stats = self._build_stats(total, inserted, failures, skipped_unchanged)
        stats["failed_rows_csv"] = self._export_failed_rows(failures)
        self._print_summary(stats)
        return stats

    def retry_failed_rows(self, table: str = "medicines") -> dict:
        """Re-process rows previously captured in the etl_failed_rows table."""
        # Supabase PostgREST default page size is 1000. Paginate to collect all rows.
        retry_rows: list[dict] = []
        page_size = 1000
        offset = 0
        while True:
            response = (
                self.client.table(RETRY_TABLE)
                .select("*")
                .eq("pipeline_name", self.pipeline_name)
                .eq("status", "failed")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = getattr(response, "data", None) or []
            retry_rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

        total = len(retry_rows)
        logger.info(f"[Loader] Retrying {total} failed rows from '{RETRY_TABLE}'...")
        existing_by_key = self._load_existing_rows_by_key(retry_rows, table)

        inserted, failures = 0, []

        for index, retry_row in enumerate(retry_rows):
            row_payload = retry_row.get("row_payload") or {}
            row_index = retry_row.get("row_index", index)
            attempt_count = int(retry_row.get("attempt_count") or 0) + 1

            try:
                self._upsert_payloads([row_payload], table, existing_by_key)
                self._update_retry_row(
                    retry_row["id"],
                    {
                        "status": "retry_succeeded",
                        "attempt_count": attempt_count,
                        "last_attempt_at": self._utc_now(),
                        "updated_at": self._utc_now(),
                    },
                )
                inserted += 1
            except Exception as e:
                failure = self._build_failure(row_payload, row_index, e)
                failures.append(failure)
                self._log_failure(failure)
                self._safe_update_retry_row(
                    retry_row["id"],
                    {
                        "status": "failed",
                        "attempt_count": attempt_count,
                        "error_category": failure["error_category"],
                        "db_error_code": failure["db_error_code"],
                        "error_message": failure["error_message"],
                        "last_attempt_at": self._utc_now(),
                        "updated_at": self._utc_now(),
                    },
                )

        stats = self._build_stats(total, inserted, failures)
        stats["failed_rows_csv"] = self._export_failed_rows(failures)
        self._print_summary(stats)
        return stats

    # ── Private helpers ────────────────────────────────────────────────────────

    def _load_batch_row_by_row(
        self,
        batch: list[dict],
        table: str,
        existing_by_key: dict[str, dict],
    ) -> tuple[int, list[dict]]:
        inserted, failures = 0, []
        for item in batch:
            try:
                self._upsert_payloads([item["write_payload"]], table, existing_by_key)
                inserted += 1
            except Exception as e:
                failure = self._build_failure(item["payload"], item["row_index"], e)
                failures.append(failure)
                self._log_failure(failure)
                self._persist_failure(failure, table)
        return inserted, failures

    def _run_upsert_with_transient_retries(
        self,
        operation: Callable[[], object],
        context: str,
    ) -> None:
        for attempt in range(1, BATCH_UPSERT_MAX_ATTEMPTS + 1):
            try:
                operation()
                return
            except Exception as e:
                if (
                    attempt == BATCH_UPSERT_MAX_ATTEMPTS
                    or not self._is_transient_upsert_error(e)
                ):
                    raise
                base_wait = min(
                    BATCH_UPSERT_INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)),
                    BATCH_UPSERT_MAX_BACKOFF_SEC,
                )

                wait_seconds = base_wait + random.uniform(0.1, 1.0)

                logger.warning(
                    f"[Loader] {context} transient failure "
                    f"(attempt {attempt}/{BATCH_UPSERT_MAX_ATTEMPTS}): {e} — "
                    f"retrying in {wait_seconds:g}s"
                )
                time.sleep(wait_seconds)

    def _upsert_payloads(
        self, payloads: list[dict], table: str, existing_by_key: dict[str, dict]
    ) -> None:
        payloads = [self._prepare_payload(payload, table) for payload in payloads]
        if not payloads:
            return
        conflict_columns = CONFLICT_COLUMNS.get(table)
        payloads = [
            self._omit_null_updates(
                payload, existing_by_key.get(self._cache_key(payload, table))
            )
            for payload in payloads
        ]
        self.client.table(table).upsert(
            payloads,
            on_conflict=",".join(conflict_columns) if conflict_columns else None,
        ).execute()

    def _omit_null_updates(self, payload: dict, existing: dict | None) -> dict:
        if not existing:
            return payload

        cleaned_payload = dict(payload)
        for column in PRESERVE_EXISTING_NULL_COLUMNS:
            if cleaned_payload.get(column) is None and existing.get(column) is not None:
                cleaned_payload.pop(column, None)
        return cleaned_payload

    @staticmethod
    def _is_transient_upsert_error(error: Exception) -> bool:
        for current in SupabaseLoader._iter_exception_chain(error):
            if isinstance(current, (TimeoutError, ConnectionError)):
                return True

            class_name = current.__class__.__name__.lower()
            message = str(current).lower()

            if any(
                keyword in class_name
                for keyword in TRANSIENT_UPSERT_EXCEPTION_NAME_KEYWORDS
            ):
                return True

            if any(keyword in message for keyword in TRANSIENT_UPSERT_ERROR_KEYWORDS):
                return True

        return False

    @staticmethod
    def _iter_exception_chain(error: Exception):
        current = error
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            yield current
            current = current.__cause__ or current.__context__

    def _prepare_payload(self, payload: dict, table: str) -> dict:
        if table in ALLOWED_COLUMNS:
            allowed = ALLOWED_COLUMNS[table]
            return {k: v for k, v in payload.items() if k in allowed}
        return dict(payload)

    def _filter_unchanged_records(
        self,
        records: list[dict],
        table: str,
        existing_by_key: dict[str, dict],
    ) -> tuple[list[dict], int]:
        if not existing_by_key:
            return records, 0

        changed = []
        skipped = 0
        for item in records:
            cache_key = self._cache_key(item["write_payload"], table)
            existing = existing_by_key.get(cache_key)
            if existing and self._payload_matches_existing(
                item["write_payload"], existing
            ):
                skipped += 1
                continue
            changed.append(item)
        return changed, skipped

    def _load_existing_rows_by_key(
        self, records: list[dict], table: str
    ) -> dict[str, dict]:
        if not records or table not in CONFLICT_COLUMNS:
            return {}

        conflict_cols = CONFLICT_COLUMNS[table]
        allowed_columns = ALLOWED_COLUMNS.get(table, ())
        selected_columns = ",".join(sorted(set([*conflict_cols, *allowed_columns])))
        existing_by_key: dict[str, dict] = {}
        page_size = 1000
        offset = 0

        try:
            while True:
                response = (
                    self.client.table(table)
                    .select(selected_columns)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                rows = getattr(response, "data", None) or []
                for row in rows:
                    existing_by_key[self._cache_key(row, table)] = row
                if len(rows) < page_size:
                    break
                offset += page_size
        except Exception as e:
            logger.warning(
                f"[Loader] Could not read existing '{table}' rows for ETL change detection; "
                f"writing all incoming records instead: {e}"
            )
            return {}

        return existing_by_key

    def _cache_key(self, payload: dict, table: str) -> str:
        key_columns = CONFLICT_COLUMNS.get(table)
        if key_columns:
            key_payload = {column: payload.get(column) for column in key_columns}
        else:
            key_payload = payload
        encoded = json.dumps(
            key_payload, default=str, separators=(",", ":"), sort_keys=True
        )
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _payload_matches_existing(self, payload: dict, existing: dict) -> bool:
        existing_subset = {key: existing.get(key) for key in payload}
        if (
            payload.get("jan_aushadhi_price") is None
            and existing_subset.get("jan_aushadhi_price") is not None
        ):
            payload = {k: v for k, v in payload.items() if k != "jan_aushadhi_price"}
            existing_subset.pop("jan_aushadhi_price", None)
        return self._row_fingerprint(payload) == self._row_fingerprint(existing_subset)

    def _build_failure(self, payload: dict, row_index: int, error: Exception) -> dict:
        msg = str(error)
        db_code = self._extract_db_error_code(msg)
        return {
            "event": "etl_row_failure",
            "pipeline": self.pipeline_name,
            "row_index": row_index,
            "medicine_name": self._extract_medicine_name(payload),
            "unresolved_value": self._extract_unresolved_value(payload),
            "db_error_code": db_code,
            "error_category": self._categorize_error(msg, db_code),
            "error_message": msg,
            "row_fingerprint": self._row_fingerprint(payload),
            "row_payload": payload,
        }

    def _log_failure(self, failure: dict) -> None:
        log_payload = {k: v for k, v in failure.items() if k != "row_payload"}
        print(json.dumps(log_payload, sort_keys=True, default=str))

    def _persist_failure(self, failure: dict, source_table: str) -> None:
        try:
            existing = self._find_retry_row(failure, source_table)
            attempt_count = (
                int(existing.get("attempt_count") or 0) + 1 if existing else 1
            )
            payload = {
                "pipeline_name": self.pipeline_name,
                "source_table": source_table,
                "row_fingerprint": failure["row_fingerprint"],
                "row_payload": failure["row_payload"],
                "medicine_name": failure["medicine_name"],
                "unresolved_value": failure["unresolved_value"],
                "error_category": failure["error_category"],
                "db_error_code": failure["db_error_code"],
                "error_message": failure["error_message"],
                "attempt_count": attempt_count,
                "status": "failed",
                "last_attempt_at": self._utc_now(),
                "updated_at": self._utc_now(),
            }
            if existing:
                self._update_retry_row(existing["id"], payload)
            else:
                self.client.table(RETRY_TABLE).insert(payload).execute()
        except Exception as e:
            logger.warning(f"[Loader] Failed to persist retry row: {e}")

    def _find_retry_row(self, failure: dict, source_table: str) -> dict | None:
        response = (
            self.client.table(RETRY_TABLE)
            .select("id, attempt_count")
            .eq("pipeline_name", self.pipeline_name)
            .eq("source_table", source_table)
            .eq("row_fingerprint", failure["row_fingerprint"])
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return rows[0] if rows else None

    def _update_retry_row(self, row_id: str, payload: dict) -> None:
        payload = self._prepare_payload(payload, RETRY_TABLE)
        self.client.table(RETRY_TABLE).update(payload).eq("id", row_id).execute()

    def _safe_update_retry_row(self, row_id: str, payload: dict) -> None:
        try:
            self._update_retry_row(row_id, payload)
        except Exception as e:
            logger.warning(f"[Loader] Failed to update retry row {row_id}: {e}")

    def _export_failed_rows(self, failures: list[dict]) -> str | None:
        if not failures:
            return None
        self.failed_rows_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = self.failed_rows_dir / f"failed_rows_{timestamp}.csv"
        rows = []
        for f in failures:
            row = dict(f["row_payload"])
            row.update(
                {
                    "row_index": f["row_index"],
                    "medicine_name": f["medicine_name"],
                    "unresolved_value": f["unresolved_value"],
                    "db_error_code": f["db_error_code"],
                    "error_category": f["error_category"],
                    "error_message": f["error_message"],
                    "row_fingerprint": f["row_fingerprint"],
                }
            )
            rows.append(row)
        pd.DataFrame(rows).to_csv(output_path, index=False)
        return str(output_path)

    def _build_stats(
        self,
        total: int,
        inserted: int,
        failures: list[dict],
        skipped_unchanged: int = 0,
    ) -> dict:
        failed = len(failures)
        successful = inserted + skipped_unchanged
        success_rate = round((successful / total) * 100, 2) if total else 100.0
        return {
            "inserted": inserted,
            "failed": failed,
            "skipped_unchanged": skipped_unchanged,
            "total": total,
            "success_rate": success_rate,
            "error_counts": dict(Counter(f["error_category"] for f in failures)),
        }

    def _print_summary(self, stats: dict) -> None:
        logger.info(
            f"[Loader] Summary — total: {stats['total']}, "
            f"inserted: {stats['inserted']}, failed: {stats['failed']}, "
            f"skipped_unchanged: {stats.get('skipped_unchanged', 0)}, "
            f"success_rate: {stats['success_rate']}%"
        )
        if stats["error_counts"]:
            logger.info(f"[Loader] Error categories: {stats['error_counts']}")
        if stats.get("failed_rows_csv"):
            logger.info(f"[Loader] Failed rows CSV: {stats['failed_rows_csv']}")
        if stats["success_rate"] < SUCCESS_RATE_ALERT_THRESHOLD:
            logger.warning(
                f"[Loader] ALERT: Success rate below {int(SUCCESS_RATE_ALERT_THRESHOLD)}%. "
                "Review failed row logs before trusting this load."
            )

    def _extract_medicine_name(self, payload: dict) -> str | None:
        for key in ("medicine_name", "generic_name", "brand_name", "raw_name"):
            if payload.get(key):
                return str(payload[key])
        return None

    def _extract_unresolved_value(self, payload: dict) -> str | None:
        for key in (
            "strength",
            "mrp",
            "price",
            "dosage_form",
            "generic_name",
            "brand_name",
        ):
            if payload.get(key) is not None:
                return str(payload[key])
        return None

    def _extract_db_error_code(self, msg: str) -> str | None:
        match = re.search(r"\b([0-9A-Z]{5})\b", msg)
        return match.group(1) if match else None

    def _row_fingerprint(self, payload: dict) -> str:
        encoded = json.dumps(
            payload, default=str, separators=(",", ":"), sort_keys=True
        )
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _categorize_error(self, msg: str, db_code: str | None) -> str:
        lower = msg.lower()
        if db_code == "23505" or "duplicate key" in lower:
            return "duplicate_key"
        if db_code and db_code.startswith("23"):
            return "constraint_violation"
        if db_code and db_code.startswith("22"):
            return "data_type_mismatch"
        if "validation" in lower or "invalid" in lower:
            return "validation_error"
        return "unknown_error"

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
