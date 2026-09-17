import {
    productBarcodeRepository,
    type BarcodeMedicineRow,
    type ProductBarcodeRow,
} from "../repositories/productBarcode.repository";
import { redisClient } from "../utils/redis";
import { gs1PrefixRegion, isValidGtin } from "../utils/gtin";
import { computeVerifiedStatus } from "../utils/verification";
import logger from "../utils/logger";

const CACHE_PREFIX = "product_barcode:";
const CACHE_TTL_SECONDS = 3600;

export interface VerificationApplicability {
    applicable: boolean;
    verified?: boolean;
    note: string;
}

export type ProductLookupResult =
    | {
          status: "found";
          gtin: string;
          region: string | null;
          product: Omit<ProductBarcodeRow, "medicine_id">;
          medicine: BarcodeMedicineRow | null;
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

/**
 * A medicine carrying a counterfeit alert is not verified, but it is not
 * unchecked either: the alert is the reason, and it is what a client shows.
 */
function medicineNote(medicine: BarcodeMedicineRow, verified: boolean): string {
    if (verified) return "Matched against the CDSCO brand registry with no counterfeit alert.";
    if (medicine.is_counterfeit_alert === true)
        return "This medicine carries a counterfeit or recall alert.";
    return "Not yet matched against the CDSCO brand registry.";
}

function describeVerification(
    product: Pick<ProductBarcodeRow, "category" | "regulator">,
    medicine: BarcodeMedicineRow | null
): VerificationApplicability {
    if (medicine) {
        const verified = computeVerifiedStatus(medicine);
        return { applicable: true, verified, note: medicineNote(medicine, verified) };
    }

    switch (product.category) {
        case "ayurvedic":
        case "homeopathic":
            return {
                applicable: false,
                note: "Licensed under AYUSH. The CDSCO brand registry does not cover it, so SahiDawa cannot check its authenticity yet.",
            };
        case "personal_care":
        case "nutraceutical":
            return {
                applicable: false,
                note: `Not a medicine (${product.regulator ?? "non-drug"} product). Medicine verification does not apply.`,
            };
        default:
            return {
                applicable: false,
                note: "No CDSCO medicine record is linked to this product yet.",
            };
    }
}

function productFromMedicine(gtin: string, medicine: BarcodeMedicineRow): ProductLookupResult {
    return {
        status: "found",
        gtin,
        region: gs1PrefixRegion(gtin),
        product: {
            gtin,
            product_name: medicine.brand_name ?? medicine.generic_name,
            brand: medicine.brand_name,
            manufacturer: medicine.manufacturer,
            marketed_by: null,
            category: "allopathic",
            regulator: "CDSCO",
            is_medicine: true,
            pack_size: null,
            mrp: medicine.mrp,
            data_source: "medicines",
            source_note: medicine.generic_name,
        },
        medicine,
        verification: describeVerification(
            { category: "allopathic", regulator: "CDSCO" },
            medicine
        ),
    };
}

async function readCache(gtin: string): Promise<ProductLookupResult | null> {
    if (!redisClient.isOpen) return null;
    try {
        const cached = await redisClient.get(`${CACHE_PREFIX}${gtin}`);
        return cached ? (JSON.parse(cached) as ProductLookupResult) : null;
    } catch (err) {
        logger.warn({ message: "Product barcode cache read failed", error: String(err) });
        return null;
    }
}

async function writeCache(result: ProductLookupResult): Promise<void> {
    if (!redisClient.isOpen) return;
    try {
        await redisClient.set(`${CACHE_PREFIX}${result.gtin}`, JSON.stringify(result), {
            EX: CACHE_TTL_SECONDS,
        });
    } catch (err) {
        logger.warn({ message: "Product barcode cache write failed", error: String(err) });
    }
}

export const productLookupService = {
    /**
     * Resolve a digits-only barcode: product catalogue first, then medicines.barcode_id,
     * otherwise record it in the unknown-barcode review queue.
     *
     * A code failing the GS1 check digit is a mistyped or misread barcode: it is
     * rejected without a lookup, and not logged as a new product.
     */
    async lookupByBarcode(gtin: string): Promise<ProductLookupResult> {
        const cached = await readCache(gtin);
        if (cached) return cached;

        if (!isValidGtin(gtin)) {
            return {
                status: "invalid",
                gtin,
                error: "The barcode check digit is wrong. Please re-scan or check the number.",
            };
        }

        const row = await productBarcodeRepository.findByGtin(gtin);
        if (row) {
            const { medicine_id, ...product } = row;
            const medicine = medicine_id
                ? await productBarcodeRepository.findMedicineById(medicine_id)
                : null;
            const result: ProductLookupResult = {
                status: "found",
                gtin,
                region: gs1PrefixRegion(gtin),
                product,
                medicine,
                verification: describeVerification(product, medicine),
            };
            await writeCache(result);
            return result;
        }

        const medicine = await productBarcodeRepository.findMedicineByBarcode(gtin);
        if (medicine) {
            const result = productFromMedicine(gtin, medicine);
            await writeCache(result);
            return result;
        }

        try {
            await productBarcodeRepository.recordUnknown(gtin);
        } catch (err) {
            logger.warn({ message: "Failed to record unknown barcode", error: String(err) });
        }

        return {
            status: "unknown",
            gtin,
            region: gs1PrefixRegion(gtin),
            message:
                "This barcode is not in SahiDawa's database yet. It has been logged for review.",
        };
    },
};
