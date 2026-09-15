"use client";

import { useState } from "react";
import { Barcode, Info, PackageSearch, ShieldAlert, ShieldCheck } from "lucide-react";

import { ExpiryBadge } from "@/components/scanner/ExpiryBadge";
import { ResultActions } from "@/components/scanner/results/ResultActions";
import type { ProductCategory, ProductLookupResponse } from "@/lib/api/products";

type DisplayableResult = Exclude<ProductLookupResponse, { status: "invalid" }>;

export interface LabelInfo {
    batch?: string;
    expiry?: string;
}

interface ProductLookupResultProps {
    result: DisplayableResult;
    labelInfo?: LabelInfo;
    onScanAgain: () => void;
    onShare: () => void;
    shareLabel: string;
}

const CATEGORY_LABELS: Record<ProductCategory, string> = {
    allopathic: "Allopathic medicine",
    ayurvedic: "Ayurvedic",
    homeopathic: "Homeopathic",
    nutraceutical: "Nutraceutical",
    personal_care: "Personal care",
    other: "Other product",
};

const MANUAL_EXPIRY_PATTERN = /^(0[1-9]|1[0-2])\/20\d{2}$/;

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
    if (value === null || value === undefined || value === "") return null;
    return (
        <div className="flex justify-between gap-4 py-1.5 text-sm">
            <span className="text-(--color-text-muted)">{label}</span>
            <span className="text-right font-semibold text-(--color-text-primary)">{value}</span>
        </div>
    );
}

function UnknownBarcode({ result }: { result: Extract<DisplayableResult, { status: "unknown" }> }) {
    return (
        <div className="flex flex-col items-center gap-3 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                <PackageSearch size={28} aria-hidden="true" />
            </div>
            <h3 className="text-lg font-bold">Not in SahiDawa&apos;s database yet</h3>
            <p className="font-mono text-sm text-(--color-text-muted)">{result.gtin}</p>
            {result.region && (
                <p className="text-xs text-(--color-text-muted)">
                    Barcode number issued via GS1 {result.region} (not necessarily where it was
                    made)
                </p>
            )}
            <p className="text-sm text-(--color-text-muted)">
                We can&apos;t identify this product, so we can&apos;t say whether it is genuine. The
                barcode has been logged for review.
            </p>
        </div>
    );
}

export function ProductLookupResult({
    result,
    labelInfo,
    onScanAgain,
    onShare,
    shareLabel,
}: ProductLookupResultProps) {
    const [manualExpiry, setManualExpiry] = useState("");
    const manualExpiryValid = MANUAL_EXPIRY_PATTERN.test(manualExpiry);
    const expiryToShow = labelInfo?.expiry ?? (manualExpiryValid ? manualExpiry : undefined);

    return (
        <section
            aria-label="Product barcode result"
            className="flex w-full flex-col gap-4 rounded-3xl border border-(--color-border-muted) bg-(--color-surface-page) p-5 shadow-sm"
        >
            {result.status === "unknown" ? (
                <UnknownBarcode result={result} />
            ) : (
                <FoundProduct result={result} />
            )}

            {(labelInfo?.batch || labelInfo?.expiry) && (
                <p className="text-xs font-semibold text-(--color-text-muted)">
                    Read from the photo label{labelInfo.batch ? ` · Batch ${labelInfo.batch}` : ""}
                </p>
            )}

            <ExpiryBadge expiryDate={expiryToShow} />

            {!labelInfo?.expiry && (
                <label className="flex flex-col gap-1 text-xs font-semibold text-(--color-text-muted)">
                    Check expiry — type the date printed on the pack (MM/YYYY)
                    <input
                        type="text"
                        inputMode="numeric"
                        value={manualExpiry}
                        onChange={(e) => setManualExpiry(e.target.value.trim())}
                        placeholder="03/2028"
                        maxLength={7}
                        aria-invalid={manualExpiry !== "" && !manualExpiryValid}
                        className="rounded-xl border border-(--color-border-muted) bg-(--color-surface-muted) px-3 py-2 text-sm font-medium text-(--color-text-primary) focus:border-emerald-500 focus:outline-none"
                    />
                </label>
            )}

            <ResultActions onScanAgain={onScanAgain} onShare={onShare} shareLabel={shareLabel} />
        </section>
    );
}

function FoundProduct({ result }: { result: Extract<DisplayableResult, { status: "found" }> }) {
    const { product, verification } = result;
    const isDemoEntry = product.data_source.startsWith("demo_");

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
                    <Barcode size={22} aria-hidden="true" />
                </div>
                <div className="min-w-0">
                    <h3 className="text-lg leading-tight font-bold">{product.product_name}</h3>
                    <p className="font-mono text-xs text-(--color-text-muted)">{result.gtin}</p>
                </div>
            </div>

            <div className="flex flex-wrap gap-2 text-xs font-bold">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                    {CATEGORY_LABELS[product.category]}
                </span>
                {product.regulator && (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                        Regulator: {product.regulator}
                    </span>
                )}
                <span
                    className={`rounded-full px-3 py-1 ${product.is_medicine ? "bg-sky-50 text-sky-700" : "bg-amber-50 text-amber-800"}`}
                >
                    {product.is_medicine ? "Medicine" : "Not a medicine"}
                </span>
            </div>

            <VerificationVerdict
                applicable={verification.applicable}
                verified={verification.verified}
                note={verification.note}
            />

            <div className="divide-y divide-(--color-border-muted)">
                <DetailRow label="Brand" value={product.brand} />
                <DetailRow label="Manufactured by" value={product.manufacturer} />
                <DetailRow label="Marketed by" value={product.marketed_by} />
                <DetailRow label="Pack size" value={product.pack_size} />
                <DetailRow label="MRP (₹)" value={product.mrp} />
                <DetailRow
                    label="Barcode issued via"
                    value={result.region ? `GS1 ${result.region}` : null}
                />
            </div>

            {isDemoEntry && (
                <p className="flex items-start gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-3 text-xs text-slate-600">
                    <Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                    <span>
                        Demo catalogue entry — transcribed from a photo of the pack, not from an
                        official source.{product.source_note ? ` ${product.source_note}` : ""}
                    </span>
                </p>
            )}
        </div>
    );
}

function VerificationVerdict({
    applicable,
    verified,
    note,
}: {
    applicable: boolean;
    verified?: boolean;
    note: string;
}) {
    if (!applicable) {
        return (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
                <p className="text-sm font-bold">Verification not applicable</p>
                <p className="mt-1 text-xs">{note}</p>
            </div>
        );
    }

    return verified ? (
        <div className="flex gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-emerald-900">
            <ShieldCheck size={18} className="shrink-0" aria-hidden="true" />
            <div>
                <p className="text-sm font-bold">CDSCO verified</p>
                <p className="mt-1 text-xs">{note}</p>
            </div>
        </div>
    ) : (
        <div className="flex gap-2 rounded-2xl border border-red-200 bg-red-50 p-3 text-red-900">
            <ShieldAlert size={18} className="shrink-0" aria-hidden="true" />
            <div>
                <p className="text-sm font-bold">Not verified</p>
                <p className="mt-1 text-xs">{note}</p>
            </div>
        </div>
    );
}
