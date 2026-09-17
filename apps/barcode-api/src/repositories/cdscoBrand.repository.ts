import { supabase } from "../db/client";
import { normalizeBrand, normalizeManufacturer } from "../utils/cdscoNormalize";

// Candidates below this name similarity are not worth returning.
const MIN_SIMILARITY = 0.2;

export interface CdscoBrandMatch {
    brand_name: string;
    manufacturer: string;
    product_score: number;
    manufacturer_score: number;
    match_score: number;
}

export interface CdscoBrandQuery {
    brand: string;
    manufacturer?: string;
    limit: number;
}

export const cdscoBrandRepository = {
    /** Closest entries in the CDSCO brand registry, best first. Scores are 0–100. */
    async match(query: CdscoBrandQuery): Promise<CdscoBrandMatch[]> {
        const { data, error } = await supabase.rpc("find_cdsco_fuzzy_match", {
            query_brand_name: normalizeBrand(query.brand),
            query_manufacturer: normalizeManufacturer(query.manufacturer ?? ""),
            match_count: query.limit,
            min_similarity: MIN_SIMILARITY,
        });
        if (error) throw error;
        return (data ?? []) as CdscoBrandMatch[];
    },
};
