import { extractExpiryDate } from "../lib/sync/medicineParser";

describe("extractExpiryDate — manufacturing and expiry printed together", () => {
    it("takes the later date from an MM/YYYY-MM/YYYY range (Mfg-Exp)", () => {
        expect(extractExpiryDate("Mfg. Date-Expiry,\n04/2025-03/2028\nRs.215.00")).toBe("03/2028");
        expect(extractExpiryDate("04/2025 - 03/2028")).toBe("03/2028");
    });

    it("takes the later of two month-name dates (Mfg then Exp)", () => {
        expect(extractExpiryDate("ENC26014\nFEB.2026\nJUL.2027\n666.48")).toBe("07/2027");
        expect(extractExpiryDate("JUL:2027 FEB:2026")).toBe("07/2027");
    });

    it("takes the later of two unlabeled MM/YYYY dates", () => {
        expect(extractExpiryDate("11/2025\n10/2027")).toBe("10/2027");
    });

    it("still prefers an explicitly labeled expiry over a later unlabeled date", () => {
        expect(extractExpiryDate("EXP 05/2027 MFG 06/2028")).toBe("05/2027");
    });
});
