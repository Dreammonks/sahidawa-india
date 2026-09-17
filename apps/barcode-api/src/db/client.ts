import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. See .env.example.");
}

/**
 * Service-role client.
 *
 * Every table has row level security enabled and grants nothing to anon, so
 * reads need the service role. This key must never leave the server; that is
 * why apps and other services call this API instead of the database.
 */
export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseKey, {
    auth: { persistSession: false, autoRefreshToken: false },
});
