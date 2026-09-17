import { supabase } from "../db/client";
import { escapeLike } from "../utils/queryParams";

const ALERT_COLUMNS =
    "id, alert_type, product_name, batch_number, manufacturing_date, expiry_date, manufacturer, reason, remarks, firm_reply, reporting_source, reported_by, reporting_month";

export type DrugAlertType = "nsq" | "spurious";

export interface DrugAlertRow {
    id: string;
    alert_type: DrugAlertType;
    product_name: string;
    batch_number: string | null;
    manufacturing_date: string | null;
    expiry_date: string | null;
    manufacturer: string | null;
    reason: string | null;
    remarks: string | null;
    firm_reply: string | null;
    reporting_source: string | null;
    reported_by: string | null;
    reporting_month: string;
}

export interface DrugAlertQuery {
    search?: string;
    batch?: string;
    type?: DrugAlertType;
    /** "YYYY-MM" */
    month?: string;
    limit: number;
    offset: number;
}

export interface DrugAlertPage {
    total: number;
    alerts: DrugAlertRow[];
}

export const drugAlertRepository = {
    async search(query: DrugAlertQuery): Promise<DrugAlertPage> {
        let request = supabase.from("drug_alerts").select(ALERT_COLUMNS, { count: "exact" });

        if (query.search) request = request.ilike("product_name", `%${escapeLike(query.search)}%`);
        if (query.batch) request = request.ilike("batch_number", escapeLike(query.batch));
        if (query.type) request = request.eq("alert_type", query.type);
        if (query.month) request = request.eq("reporting_month", `${query.month}-01`);

        const { data, error, count } = await request
            .order("reporting_month", { ascending: false })
            .order("product_name", { ascending: true })
            .range(query.offset, query.offset + query.limit - 1);

        if (error) throw error;
        return { total: count ?? 0, alerts: (data ?? []) as DrugAlertRow[] };
    },
};
