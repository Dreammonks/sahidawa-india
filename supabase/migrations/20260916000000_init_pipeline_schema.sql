-- =============================================================================
-- SahiDawa — complete schema for the scraping pipeline and the barcode API
-- =============================================================================
-- Replaces the 110 migrations that accumulated while SahiDawa was a full
-- product. Those could not build a working database: four columns the ETL
-- loader writes were never created by any migration, and local development ran
-- with migrations switched off entirely.
--
-- This file is the whole schema. It creates only what two things need — the
-- pipeline in apps/etl, and the barcode endpoint in apps/barcode-api.
--
-- Column definitions come from apps/api/src/db/schema.sql, kept alongside as
-- supabase/legacy-schema-from-api.sql, which was the real schema of record.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;   -- pharmacies.location
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy search and CDSCO matching

-- ─────────────────────────────────────────────────────────────────────────────
-- medicines — what the pipeline collects
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.medicines (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    barcode_id                  VARCHAR(100) UNIQUE,
    brand_name                  VARCHAR(255),
    generic_name                VARCHAR(500) NOT NULL,
    manufacturer                VARCHAR(255),   -- NULL where the source names no maker
    batch_number                VARCHAR(100),
    manufacturing_date          DATE,
    expiry_date                 DATE,
    composition                 TEXT,
    strength                    VARCHAR(100),
    dosage_form                 VARCHAR(100),
    pack_size                   VARCHAR(100),   -- as published: "10's", "strip of 10 tablets"
    source_product_code         VARCHAR(50),    -- the source's own product ID (Jan Aushadhi Drug Code)
    schedule                    VARCHAR(50),
    source                      VARCHAR(100),
    cdsco_approval_status       VARCHAR(50),
    is_counterfeit_alert        BOOLEAN,
    is_cdsco_verified           BOOLEAN,        -- NULL until CDSCO validation has run
    cdsco_match_score           DOUBLE PRECISION,
    matched_cdsco_product       TEXT,
    matched_cdsco_manufacturer  TEXT,
    product_match_score         DOUBLE PRECISION,
    manufacturer_match_score    DOUBLE PRECISION,
    mrp                         NUMERIC(10, 2),
    jan_aushadhi_price          NUMERIC(10, 2),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT medicines_mrp_non_negative
        CHECK (mrp IS NULL OR mrp >= 0),
    CONSTRAINT medicines_jan_aushadhi_price_non_negative
        CHECK (jan_aushadhi_price IS NULL OR jan_aushadhi_price >= 0)
);

-- The loader upserts on exactly these five columns. NULLS NOT DISTINCT matters:
-- Jan Aushadhi rows have no brand_name, and without it every run would insert
-- a fresh duplicate instead of updating the existing row. source_product_code
-- matters for the same rows: without it, the 250mg and 500mg of one generic
-- share a key and one overwrites the other (928 of 2,431 products, 2026-09-17).
ALTER TABLE public.medicines
    DROP CONSTRAINT IF EXISTS idx_medicines_unique_variant;
ALTER TABLE public.medicines
    ADD CONSTRAINT idx_medicines_unique_variant
    UNIQUE NULLS NOT DISTINCT (generic_name, brand_name, manufacturer, barcode_id, source_product_code);

CREATE INDEX IF NOT EXISTS idx_medicines_batch_number ON public.medicines (batch_number);
CREATE INDEX IF NOT EXISTS idx_medicines_mrp ON public.medicines (mrp);
CREATE INDEX IF NOT EXISTS idx_medicines_jan_aushadhi_price ON public.medicines (jan_aushadhi_price);
CREATE INDEX IF NOT EXISTS idx_medicines_brand_name_trgm
    ON public.medicines USING gin (brand_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_medicines_generic_name_trgm
    ON public.medicines USING gin (generic_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_medicines_composition_trgm
    ON public.medicines USING gin (composition gin_trgm_ops);

-- ─────────────────────────────────────────────────────────────────────────────
-- pharmacies — Jan Aushadhi store locations, scraped weekly
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.pharmacies (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,
    license_id    VARCHAR(100) UNIQUE,
    address       TEXT NOT NULL,
    district      VARCHAR(100) NOT NULL,
    state         VARCHAR(100) NOT NULL,
    pincode       VARCHAR(10),
    store_code    VARCHAR(20),              -- Jan Aushadhi Kendra code, e.g. PMBJK00012
    phone_number  VARCHAR(20),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    location      geography(POINT, 4326),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The store loader upserts on (name, address), but no constraint ever matched
-- it, so Postgres could not deduplicate and every weekly run re-inserted every
-- shop. This is the fix for that.
CREATE UNIQUE INDEX IF NOT EXISTS idx_pharmacies_name_address
    ON public.pharmacies (name, address);

CREATE INDEX IF NOT EXISTS idx_pharmacies_is_active ON public.pharmacies (is_active);
CREATE INDEX IF NOT EXISTS idx_pharmacies_location
    ON public.pharmacies USING GIST (location);

-- ─────────────────────────────────────────────────────────────────────────────
-- cdsco_reference — the brand registry the pipeline checks medicines against
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.cdsco_reference (
    id                     BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    brand_name             TEXT NOT NULL,
    firm_name              TEXT NOT NULL DEFAULT '',
    brand_name_normalized  TEXT NOT NULL,
    firm_name_normalized   TEXT NOT NULL DEFAULT '',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cdsco_reference_normalized_unique
    ON public.cdsco_reference (brand_name_normalized, firm_name_normalized);
CREATE INDEX IF NOT EXISTS idx_cdsco_reference_brand_name_trgm
    ON public.cdsco_reference USING gin (brand_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_cdsco_reference_brand_name_normalized_trgm
    ON public.cdsco_reference USING gin (brand_name_normalized gin_trgm_ops);

-- ─────────────────────────────────────────────────────────────────────────────
-- etl_failed_rows — rows the loader could not write, kept for retry
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.etl_failed_rows (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_name    VARCHAR(100) NOT NULL,
    source_table     VARCHAR(100) NOT NULL,
    row_fingerprint  VARCHAR(64) NOT NULL,
    row_payload      JSONB NOT NULL,
    medicine_name    VARCHAR(500),
    unresolved_value TEXT,
    error_category   VARCHAR(100),
    db_error_code    VARCHAR(20),
    error_message    TEXT,
    attempt_count    INTEGER DEFAULT 1,
    status           VARCHAR(50) DEFAULT 'failed',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_etl_failed_rows_status
    ON public.etl_failed_rows (status);
CREATE INDEX IF NOT EXISTS idx_etl_failed_rows_pipeline_name
    ON public.etl_failed_rows (pipeline_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_etl_failed_rows_unique_logical_row
    ON public.etl_failed_rows (pipeline_name, source_table, row_fingerprint);

-- ─────────────────────────────────────────────────────────────────────────────
-- Barcode catalogue and review queue
-- ─────────────────────────────────────────────────────────────────────────────
-- Real pack barcodes are often not allopathic medicines: Ayurvedic and
-- homeopathic products (AYUSH), nutraceuticals (FSSAI) and personal care (BIS).
-- None of the pipeline's sources carry barcodes, and medicines requires
-- CDSCO-shaped fields, so those products cannot live there.
CREATE TABLE IF NOT EXISTS public.product_barcodes (
    gtin          TEXT PRIMARY KEY
                  CHECK (gtin ~ '^[0-9]+$' AND length(gtin) IN (8, 12, 13, 14)),
    product_name  TEXT NOT NULL,
    brand         TEXT,
    manufacturer  TEXT,
    marketed_by   TEXT,
    category      TEXT NOT NULL
                  CHECK (category IN ('allopathic', 'ayurvedic', 'homeopathic',
                                      'nutraceutical', 'personal_care', 'other')),
    regulator     TEXT CHECK (regulator IN ('CDSCO', 'AYUSH', 'FSSAI', 'BIS', 'OTHER')),
    is_medicine   BOOLEAN NOT NULL,
    pack_size     TEXT,
    mrp           NUMERIC(10, 2) CHECK (mrp IS NULL OR mrp >= 0),
    medicine_id   UUID REFERENCES public.medicines(id) ON DELETE SET NULL,
    data_source   TEXT NOT NULL,
    source_note   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_barcodes_medicine_id
    ON public.product_barcodes (medicine_id);

CREATE TABLE IF NOT EXISTS public.unknown_barcode_scans (
    gtin           TEXT PRIMARY KEY
                   CHECK (gtin ~ '^[0-9]+$' AND length(gtin) IN (8, 12, 13, 14)),
    scan_count     INTEGER NOT NULL DEFAULT 1 CHECK (scan_count > 0),
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_unknown_barcode_scans_last_seen
    ON public.unknown_barcode_scans (last_seen_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- drug_alerts — CDSCO's monthly lists of batches that failed a quality test
-- (nsq) or were found to be fake (spurious). Stored as published; not linked
-- to medicines, because an alert names a product, not one of our rows.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.drug_alerts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type          TEXT NOT NULL CHECK (alert_type IN ('nsq', 'spurious')),
    product_name        TEXT NOT NULL,
    batch_number        TEXT,
    manufacturing_date  TEXT,              -- as published, e.g. "Feb-2025"
    expiry_date         TEXT,
    manufacturer        TEXT,              -- as published, usually name and address
    reason              TEXT,              -- the test the batch failed
    remarks             TEXT,
    firm_reply          TEXT,
    reporting_source    TEXT,
    reported_by         TEXT,
    reporting_month     DATE NOT NULL,     -- first day of the month CDSCO reported it
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT drug_alerts_unique_alert
        UNIQUE NULLS NOT DISTINCT (alert_type, product_name, batch_number, manufacturer, reporting_month)
);

CREATE INDEX IF NOT EXISTS idx_drug_alerts_batch_number
    ON public.drug_alerts (lower(batch_number));
CREATE INDEX IF NOT EXISTS idx_drug_alerts_reporting_month
    ON public.drug_alerts (reporting_month DESC);
CREATE INDEX IF NOT EXISTS idx_drug_alerts_product_name_trgm
    ON public.drug_alerts USING gin (product_name gin_trgm_ops);

-- ─────────────────────────────────────────────────────────────────────────────
-- Access: service role only
-- ─────────────────────────────────────────────────────────────────────────────
-- Supabase grants the anon and authenticated roles full table access by
-- default, and the anon key is public by design. Without this, anyone holding
-- it could rewrite prices, insert pharmacies or read failed rows (checked
-- 2026-09-17). The pipeline and the barcode API both use the service role,
-- which bypasses RLS. A future read-only consumer gets its own role and policy.
-- pharmacies holds contact names and phone numbers, so it must not be public.
ALTER TABLE public.medicines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pharmacies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cdsco_reference ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.etl_failed_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_barcodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.unknown_barcode_scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.drug_alerts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.medicines, public.pharmacies, public.cdsco_reference,
    public.etl_failed_rows, public.product_barcodes, public.unknown_barcode_scans,
    public.drug_alerts
    FROM anon, authenticated;

-- ─────────────────────────────────────────────────────────────────────────────
-- Functions
-- ─────────────────────────────────────────────────────────────────────────────

-- Atomic upsert so concurrent scans of the same unknown barcode never lose a count.
CREATE OR REPLACE FUNCTION public.record_unknown_barcode(p_gtin TEXT)
RETURNS VOID AS $$
BEGIN
    INSERT INTO public.unknown_barcode_scans (gtin)
    VALUES (p_gtin)
    ON CONFLICT (gtin) DO UPDATE
        SET scan_count   = public.unknown_barcode_scans.scan_count + 1,
            last_seen_at = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

REVOKE ALL ON FUNCTION public.record_unknown_barcode(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_unknown_barcode(TEXT) TO service_role;

-- Trigram search over brand, generic name and composition. Lives in the
-- database so any service can call it without going through an API.
CREATE OR REPLACE FUNCTION public.search_medicines_text(
    query_text TEXT,
    match_count INTEGER DEFAULT 5
)
RETURNS TABLE (
    id                 UUID,
    brand_name         VARCHAR(255),
    generic_name       VARCHAR(500),
    manufacturer       VARCHAR(255),
    composition        TEXT,
    mrp                NUMERIC(10, 2),
    jan_aushadhi_price NUMERIC(10, 2),
    similarity         DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id, m.brand_name, m.generic_name, m.manufacturer, m.composition,
        m.mrp, m.jan_aushadhi_price,
        GREATEST(
            similarity(COALESCE(m.generic_name, ''), query_text),
            similarity(COALESCE(m.brand_name, ''), query_text),
            similarity(COALESCE(m.composition, ''), query_text)
        )::double precision AS similarity
    FROM public.medicines m
    WHERE COALESCE(m.generic_name, '') % query_text
       OR COALESCE(m.brand_name, '') % query_text
       OR COALESCE(m.composition, '') % query_text
    ORDER BY similarity DESC
    LIMIT GREATEST(match_count, 1);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

ALTER FUNCTION public.search_medicines_text(TEXT, INTEGER)
    SET pg_trgm.similarity_threshold = 0.2;

-- SECURITY DEFINER reads past RLS, so callers are limited like the tables are.
REVOKE ALL ON FUNCTION public.search_medicines_text(TEXT, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.search_medicines_text(TEXT, INTEGER) TO service_role;

-- Fuzzy match a scraped brand against the CDSCO registry. Scores blend product
-- name similarity (70%) with manufacturer similarity (30%).
CREATE OR REPLACE FUNCTION public.find_cdsco_fuzzy_match(
    query_brand_name TEXT,
    query_manufacturer TEXT DEFAULT '',
    match_count INTEGER DEFAULT 1,
    min_similarity DOUBLE PRECISION DEFAULT 0.2
)
RETURNS TABLE (
    brand_name          TEXT,
    manufacturer        TEXT,
    product_score       DOUBLE PRECISION,
    manufacturer_score  DOUBLE PRECISION,
    match_score         DOUBLE PRECISION
) AS $$
DECLARE
    normalized_query_brand_name TEXT;
    normalized_query_manufacturer TEXT;
    effective_min_similarity DOUBLE PRECISION;
BEGIN
    normalized_query_brand_name := lower(btrim(COALESCE(query_brand_name, '')));
    normalized_query_manufacturer := lower(btrim(COALESCE(query_manufacturer, '')));

    IF normalized_query_brand_name = '' THEN
        RETURN;
    END IF;

    effective_min_similarity := LEAST(GREATEST(COALESCE(min_similarity, 0.2), 0.0), 1.0);
    PERFORM set_config('pg_trgm.similarity_threshold', effective_min_similarity::TEXT, TRUE);

    RETURN QUERY
    WITH ranked_brand_matches AS (
        SELECT
            r.brand_name AS candidate_brand_name,
            r.firm_name AS candidate_firm_name,
            (similarity(r.brand_name_normalized, normalized_query_brand_name) * 100.0)
                ::DOUBLE PRECISION AS candidate_product_score,
            (similarity(r.firm_name_normalized, normalized_query_manufacturer) * 100.0)
                ::DOUBLE PRECISION AS candidate_manufacturer_score
        FROM public.cdsco_reference AS r
        WHERE r.brand_name_normalized % normalized_query_brand_name
        ORDER BY r.brand_name_normalized <-> normalized_query_brand_name
        LIMIT GREATEST(match_count, 1) * 10
    ),
    scored_matches AS (
        SELECT
            candidate_brand_name, candidate_firm_name,
            candidate_product_score, candidate_manufacturer_score,
            (0.7 * candidate_product_score + 0.3 * candidate_manufacturer_score)
                ::DOUBLE PRECISION AS candidate_match_score
        FROM ranked_brand_matches
    )
    SELECT
        candidate_brand_name, candidate_firm_name,
        candidate_product_score, candidate_manufacturer_score, candidate_match_score
    FROM scored_matches
    ORDER BY candidate_match_score DESC, candidate_product_score DESC
    LIMIT GREATEST(match_count, 1);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

REVOKE ALL ON FUNCTION public.find_cdsco_fuzzy_match(TEXT, TEXT, INTEGER, DOUBLE PRECISION)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.find_cdsco_fuzzy_match(TEXT, TEXT, INTEGER, DOUBLE PRECISION)
    TO service_role;
