import { supabase } from "../db/client";

const PRODUCT_COLUMNS =
    "gtin, product_name, brand, manufacturer, marketed_by, category, regulator, is_medicine, pack_size, mrp, medicine_id, data_source, source_note";

const MEDICINE_COLUMNS =
    "id, barcode_id, brand_name, generic_name, manufacturer, batch_number, expiry_date, cdsco_approval_status, is_counterfeit_alert, is_cdsco_verified, cdsco_match_score, mrp";

export type ProductCategory =
    "allopathic" | "ayurvedic" | "homeopathic" | "nutraceutical" | "personal_care" | "other";

export interface ProductBarcodeRow {
    gtin: string;
    product_name: string;
    brand: string | null;
    manufacturer: string | null;
    marketed_by: string | null;
    category: ProductCategory;
    regulator: string | null;
    is_medicine: boolean;
    pack_size: string | null;
    mrp: string | number | null;
    medicine_id: string | null;
    data_source: string;
    source_note: string | null;
}

export interface BarcodeMedicineRow {
    id: string;
    barcode_id: string | null;
    brand_name: string | null;
    generic_name: string;
    manufacturer: string | null;
    batch_number: string | null;
    expiry_date: string | null;
    cdsco_approval_status: string | null;
    is_counterfeit_alert: boolean | null;
    is_cdsco_verified: boolean | null;
    cdsco_match_score: number | null;
    mrp: string | number | null;
}

/**
 * Repository for barcode (GTIN) product lookups.
 */
export const productBarcodeRepository = {
    async findByGtin(gtin: string): Promise<ProductBarcodeRow | null> {
        const { data, error } = await supabase
            .from("product_barcodes")
            .select(PRODUCT_COLUMNS)
            .eq("gtin", gtin)
            .maybeSingle();
        if (error) throw error;
        return data as ProductBarcodeRow | null;
    },

    async findMedicineById(id: string): Promise<BarcodeMedicineRow | null> {
        const { data, error } = await supabase
            .from("medicines")
            .select(MEDICINE_COLUMNS)
            .eq("id", id)
            .maybeSingle();
        if (error) throw error;
        return data as BarcodeMedicineRow | null;
    },

    async findMedicineByBarcode(gtin: string): Promise<BarcodeMedicineRow | null> {
        const { data, error } = await supabase
            .from("medicines")
            .select(MEDICINE_COLUMNS)
            .eq("barcode_id", gtin)
            .maybeSingle();
        if (error) throw error;
        return data as BarcodeMedicineRow | null;
    },

    async recordUnknown(gtin: string): Promise<void> {
        const { error } = await supabase.rpc("record_unknown_barcode", { p_gtin: gtin });
        if (error) throw error;
    },
};
