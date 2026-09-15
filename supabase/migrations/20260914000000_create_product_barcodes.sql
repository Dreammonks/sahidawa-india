-- =============================================================================
-- SahiDawa — Product barcode catalogue and unknown-barcode review queue
-- =============================================================================
-- WHY THIS EXISTS:
--   Real pack barcodes (EAN-13 / GTIN) scanned at a pharmacy counter are often
--   not allopathic medicines: Ayurvedic and homeopathic products (AYUSH),
--   nutraceuticals (FSSAI) and personal care (BIS). None of SahiDawa's sources
--   (CDSCO registry, Jan Aushadhi list, commercial dataset) carry barcodes, and
--   `medicines` requires CDSCO-shaped fields, so those products cannot live
--   there. This catalogue maps a GTIN to a product and its category, and the
--   review queue records barcodes nobody has catalogued yet.
-- =============================================================================

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

-- Service-role access only: the API reads and writes through its privileged client.
ALTER TABLE public.product_barcodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.unknown_barcode_scans ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON FUNCTION public.record_unknown_barcode(TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_unknown_barcode(TEXT) TO service_role;

COMMENT ON TABLE public.product_barcodes IS
  'GTIN to product catalogue, including non-allopathic and non-medicine products.';
COMMENT ON TABLE public.unknown_barcode_scans IS
  'Barcodes scanned by users that no catalogue or medicine row matched; review queue.';
