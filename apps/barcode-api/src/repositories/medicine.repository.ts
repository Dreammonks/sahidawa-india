import { supabase } from "../db/client";

// Columns the sources actually fill. batch, dates, barcode, schedule and the
// approval/alert flags are always empty for scraped medicines, so they are not served.
const MEDICINE_COLUMNS =
    "id, source, source_product_code, brand_name, generic_name, manufacturer, composition, strength, dosage_form, pack_size, mrp, jan_aushadhi_price, is_cdsco_verified, cdsco_match_score, matched_cdsco_product, matched_cdsco_manufacturer, updated_at";

export type MedicineSource = "janaushadhi" | "commercial";

export interface MedicineRow {
    id: string;
    source: MedicineSource;
    source_product_code: string | null;
    brand_name: string | null;
    generic_name: string;
    manufacturer: string | null;
    composition: string | null;
    strength: string | null;
    dosage_form: string | null;
    pack_size: string | null;
    mrp: number | null;
    jan_aushadhi_price: number | null;
    is_cdsco_verified: boolean | null;
    cdsco_match_score: number | null;
    matched_cdsco_product: string | null;
    matched_cdsco_manufacturer: string | null;
    updated_at: string;
}

export interface MedicineListQuery {
    source?: MedicineSource;
    limit: number;
    offset: number;
}

export interface MedicineSearchQuery extends MedicineListQuery {
    search: string;
}

export interface MedicinePage<T> {
    total: number;
    medicines: T[];
}

interface SearchHit {
    id: string;
    match_score: number;
    total_count: number;
}

// PostgREST answers a range starting past the last row with 416. Paging to the
// end of a list is ordinary, so it is reported as an empty page, not an error.
const RANGE_PAST_LAST_ROW = "PGRST103";

function selectMedicines(source: MedicineSource | undefined, head = false) {
    const request = supabase.from("medicines").select(MEDICINE_COLUMNS, { count: "exact", head });
    return source ? request.eq("source", source) : request;
}

export const medicineRepository = {
    async list(query: MedicineListQuery): Promise<MedicinePage<MedicineRow>> {
        const { data, error, count } = await selectMedicines(query.source)
            .order("generic_name", { ascending: true })
            .order("brand_name", { ascending: true, nullsFirst: true })
            .order("id", { ascending: true })
            .range(query.offset, query.offset + query.limit - 1);

        if (error) {
            if (error.code !== RANGE_PAST_LAST_ROW) throw error;
            const total = await selectMedicines(query.source, true);
            if (total.error) throw total.error;
            return { total: total.count ?? 0, medicines: [] };
        }

        return { total: count ?? 0, medicines: (data ?? []) as MedicineRow[] };
    },

    /** Best matches first. The database ranks and pages; full rows are read in one more query. */
    async search(
        query: MedicineSearchQuery
    ): Promise<MedicinePage<MedicineRow & { match_score: number }>> {
        const { data, error } = await supabase.rpc("search_medicines", {
            p_query: query.search,
            p_source: query.source ?? null,
            p_limit: query.limit,
            p_offset: query.offset,
        });
        if (error) throw error;

        const hits = (data ?? []) as SearchHit[];
        if (hits.length === 0) return { total: 0, medicines: [] };

        const rows = await supabase
            .from("medicines")
            .select(MEDICINE_COLUMNS)
            .in(
                "id",
                hits.map((hit) => hit.id)
            );
        if (rows.error) throw rows.error;

        const byId = new Map((rows.data as MedicineRow[]).map((row) => [row.id, row]));
        const medicines = hits.flatMap((hit) => {
            const row = byId.get(hit.id);
            return row ? [{ ...row, match_score: hit.match_score }] : [];
        });
        return { total: Number(hits[0].total_count), medicines };
    },

    async findById(id: string): Promise<MedicineRow | null> {
        const { data, error } = await supabase
            .from("medicines")
            .select(MEDICINE_COLUMNS)
            .eq("id", id)
            .maybeSingle();
        if (error) throw error;
        return data as MedicineRow | null;
    },
};
