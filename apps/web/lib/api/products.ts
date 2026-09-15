import { API_BASE, ApiHttpError, fetchWithCsrf } from "../api";

export type ProductCategory =
    "allopathic" | "ayurvedic" | "homeopathic" | "nutraceutical" | "personal_care" | "other";

export interface ProductInfo {
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
    data_source: string;
    source_note: string | null;
}

export interface LinkedMedicine {
    id: string;
    brand_name: string;
    generic_name: string;
    manufacturer: string;
    batch_number: string | null;
    expiry_date: string | null;
    cdsco_approval_status: string | null;
    is_counterfeit_alert: boolean | null;
    is_cdsco_verified: boolean | null;
}

export interface VerificationApplicability {
    applicable: boolean;
    verified?: boolean;
    note: string;
}

export type ProductLookupResponse =
    | {
          status: "found";
          gtin: string;
          region: string | null;
          product: ProductInfo;
          medicine: LinkedMedicine | null;
          verification: VerificationApplicability;
      }
    | {
          status: "unknown";
          gtin: string;
          region: string | null;
          message: string;
      }
    | {
          status: "invalid";
          gtin: string;
          error: string;
      };

export async function lookupProductByBarcode(
    gtin: string,
    signal?: AbortSignal
): Promise<ProductLookupResponse> {
    try {
        return await fetchWithCsrf<ProductLookupResponse>(
            `${API_BASE}/api/v1/products/barcode/${encodeURIComponent(gtin)}`,
            { method: "GET", timeout: 10000, signal }
        );
    } catch (error) {
        // A 400 is an expected answer (wrong check digit), not a failure to surface as an error.
        if (error instanceof ApiHttpError && error.status === 400) {
            return { status: "invalid", gtin, error: error.message };
        }
        throw error;
    }
}
