"""
SahiDawa — Jan Aushadhi Scraper + Normalizer
=============================================
Originally part of the ML service, which no longer exists.


WHY PLAYWRIGHT (not BeautifulSoup):
    Jan Aushadhi's website is a React app. The server sends a blank HTML page,
    and JavaScript runs in the browser to fetch and render the medicine table.
    Playwright opens a real browser, waits for JS to run, then downloads the CSV
    that the site generates in-memory.

PIPELINE ROLE:
    scrape() → raw CSV path
    normalize(raw_csv_path) → clean pd.DataFrame ready for the loader
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.async_api import Download, Error, async_playwright

from src.utils.logger import logger


# ── Constants ──────────────────────────────────────────────────────────────────

TARGET_URL = "https://janaushadhi.gov.in/product-portfolio/product-mrp-list"
RAW_DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "raw" / "janaushadhi"
PROCESSED_DIR = Path(__file__).resolve().parents[4] / "data" / "processed"


# Dosage forms, recognised only where the list itself states them.
STATED_FORMS = [
    (r"\btablets?\b", "Tablet"),
    (r"\bcapsules?\b", "Capsule"),
    (r"\b(syrup|suspension|solution)\b", "Liquid"),
    (r"\binjections?\b", "Injectable"),
    (r"\bdrops?\b", "Drops"),
    (r"\bointment\b", "Ointment"),
    (r"\bcream\b", "Cream"),
    (r"\bgel\b", "Gel"),
    (r"\binhaler\b", "Inhaler"),
    (r"\bpatch(es)?\b", "Patch"),
    (r"\bsachets?\b", "Sachet"),
]

# A dose, optionally per a quantity: "100mg", "5 mg per 5 ml". Must match
# DOSE_PATTERN in commercial_medicine.py so the two sources' strengths line up.
STRENGTH_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|units?|%)"
    r"(?:\s*(?:/|\bper\b)\s*(\d+(?:\.\d+)?)?\s*(mg|mcg|g|ml|iu|units?|%))?",
    re.IGNORECASE,
)

COLUMN_RENAMES = {
    "sr no": "row_num",
    "sr.no": "row_num",
    "sr_no": "row_num",
    "drug code": "drug_code",
    "drug_code": "drug_code",
    "generic name": "raw_name",
    "generic_name": "raw_name",
    "unit size": "unit_size",
    "unit_size": "unit_size",
    "mrp": "mrp",
    "mrp_(rs.)": "mrp",
    "group name": "group_name",
    "group_name": "group_name",
}

FORM_WORDS = [
    r"\btablets?\b", r"\bcapsules?\b", r"\bsyrup\b", r"\binjection\b",
    r"\binfusion\b", r"\bointment\b", r"\bcream\b", r"\bdrops?\b",
    r"\binhaler\b", r"\bpatch\b", r"\bsolution\b", r"\bsuspension\b",
    r"\bpowder\b", r"\bsachet\b", r"\bip\b", r"\bbp\b", r"\busp\b",
    r"\bgel\b", r"\blotion\b", r"\bspray\b", r"\bpaste\b",
]


# ── Scraper ────────────────────────────────────────────────────────────────────

async def _fetch_free_proxy() -> str | None:
    """Return a public HTTPS proxy URL, or None when none can be found."""
    try:
        from fp.fp import FreeProxy

        # FreeProxy is synchronous and slow; keep it off the event loop.
        return await asyncio.to_thread(FreeProxy(https=True).get)
    except Exception as e:
        logger.warning(f"[JanAushadhi] Failed to fetch proxy: {e}. Proceeding without proxy.")
        return None


class JanAushadhiScraper:
    """
    Headless browser scraper for the Jan Aushadhi product list.
    Uses Playwright to load the JS-rendered React app and download the CSV.
    """

    def __init__(self):
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    async def scrape(self) -> Path:
        """
        Returns the Path to the downloaded raw CSV file.

        Raises:
            TimeoutError: If the page doesn't load or CSV button isn't found.
        """
        max_attempts = 4
        backoff_seconds = [2, 4, 8]

        for attempt in range(1, max_attempts + 1):
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    # Free proxies are slow and often dead: through one, the page
                    # timed out on every attempt while a direct load took 12s
                    # (2026-09-17). They stay as the retry path because the site
                    # may refuse connections from outside India, where CI runs.
                    proxy_url = None
                    if attempt > 1:
                        proxy_url = await _fetch_free_proxy()
                        if proxy_url:
                            logger.info(f"[JanAushadhi] Using Proxy: {proxy_url}")

                    context_options = {
                        "accept_downloads": True,
                        "user_agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        )
                    }
                    if proxy_url:
                        context_options["proxy"] = {"server": proxy_url}

                    context = await browser.new_context(**context_options)
                    page = await context.new_page()

                    logger.info(f"[JanAushadhi] Navigating to: {TARGET_URL} (Attempt {attempt}/{max_attempts})")
                    response = await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60_000)

                    if response is None:
                        raise RuntimeError("No response received from server")

                    if 400 <= response.status < 500:
                        raise ValueError(f"HTTP {response.status} Client Error")
                    elif response.status >= 500:
                        raise RuntimeError(f"HTTP {response.status} Server Error")

                    logger.info("[JanAushadhi] Waiting for medicine table...")
                    try:
                        await page.wait_for_selector(".rdt_TableRow", timeout=45_000)
                    except Exception:
                        await page.wait_for_selector("[role='row']", timeout=15_000)

                    row_count = await page.locator(".rdt_TableRow").count()
                    logger.info(f"[JanAushadhi] Visible rows: {row_count} (total ~2439 in memory)")

                    # Wait for React to hydrate full dataset before exporting
                    await page.wait_for_timeout(5000)

                    async with page.expect_download(timeout=30_000) as download_info:
                        await page.get_by_text("Download Files").click()
                        await page.get_by_text("Download CSV").click()

                    download: Download = await download_info.value

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = RAW_DATA_DIR / f"janaushadhi_raw_{timestamp}.csv"
                    await download.save_as(save_path)

                    logger.info(f"[JanAushadhi] CSV saved: {save_path} ({save_path.stat().st_size / 1024:.1f} KB)")
                    return save_path
                except (Error, TimeoutError, RuntimeError) as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"[JanAushadhi] All {max_attempts} attempts exhausted. Final failure reason: {e}"
                        )
                        raise

                    backoff_time = backoff_seconds[attempt - 1]
                    logger.warning(
                        f"[JanAushadhi] Attempt {attempt} failed: {e}. "
                        f"Retrying in {backoff_time}s... (Attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(backoff_time)
                finally:
                    await browser.close()


# ── Normalizer ─────────────────────────────────────────────────────────────────

class JanAushadhiNormalizer:
    """
    Transforms raw Jan Aushadhi CSV into a clean DataFrame matching
    the SahiDawa medicines table schema.
    """

    def normalize(self, raw_csv_path: Path) -> pd.DataFrame:
        logger.info(f"[Normalizer] Reading: {raw_csv_path}")
        # Read as text so Drug Code stays "239", not 239.0.
        df = pd.read_csv(raw_csv_path, encoding="utf-8-sig", dtype=str)
        logger.info(f"[Normalizer] Loaded {len(df)} raw records. Columns: {list(df.columns)}")

        if len(df) == 0:
            logger.warning("[Normalizer] Raw CSV is empty — skipping normalization.")
            return df

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        df = df.rename(columns={k: v for k, v in COLUMN_RENAMES.items() if k in df.columns})

        before = len(df)
        df = df.dropna(subset=["raw_name"])
        df["raw_name"] = df["raw_name"].str.strip()
        df = df[df["raw_name"] != ""]
        logger.info(f"[Normalizer] Dropped {before - len(df)} rows with empty names")

        df["strength"] = df["raw_name"].apply(self._extract_strength)
        df["generic_name"] = df["raw_name"].apply(self._clean_generic_name)
        df["composition"] = df["raw_name"].apply(self._strip_form_words)
        df["source_product_code"] = df.get("drug_code", pd.Series(dtype=str)).str.strip()

        unit_col = "unit_size" if "unit_size" in df.columns else None
        df["pack_size"] = df[unit_col].str.strip() if unit_col else None
        df["dosage_form"] = df.apply(
            lambda row: self._stated_form(f"{row['raw_name']} {row.get('unit_size') or ''}"),
            axis=1,
        )

        df["brand_name"] = None
        # The list names no maker. PMBI runs the scheme; it does not manufacture.
        df["manufacturer"] = None
        df["source"] = "janaushadhi"
        df["barcode_id"] = None
        # 344 products are listed at MRP 0 (2026-09-17): the price is unknown, not free.
        prices = pd.to_numeric(df["mrp"], errors="coerce")
        df["mrp"] = prices.where(prices > 0)
        df["jan_aushadhi_price"] = df["mrp"]

        output_cols = [
            "brand_name", "generic_name", "manufacturer", "composition", "strength",
            "dosage_form", "pack_size", "source_product_code", "source", "barcode_id",
            "mrp", "jan_aushadhi_price",
        ]
        result = df[output_cols].copy()

        # Drug Code is Jan Aushadhi's own product ID. The same generic name comes
        # in several strengths and pack sizes, each with its own code.
        has_codes = result["source_product_code"].notna().all()
        dedup_key = ["source_product_code"] if has_codes else ["generic_name", "strength", "dosage_form"]
        before = len(result)
        result = result.drop_duplicates(subset=dedup_key)
        logger.info(f"[Normalizer] Removed {before - len(result)} duplicates. Final: {len(result)} records")

        return result

    def _extract_strength(self, name: str) -> str | None:
        doses = [
            f"{val}{unit}" + (f"/{per_val}{per_unit}" if per_unit else "")
            for val, unit, per_val, per_unit in STRENGTH_PATTERN.findall(name)
        ]
        return " + ".join(doses) if doses else None

    def _clean_generic_name(self, name: str) -> str:
        return self._strip_form_words(STRENGTH_PATTERN.sub("", name)) or name

    def _strip_form_words(self, name: str) -> str:
        cleaned = name
        for word in FORM_WORDS:
            cleaned = re.sub(word, "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", cleaned).strip(" ,+&")

    def _stated_form(self, text: str) -> str | None:
        text_lower = text.lower()
        for pattern, form in STATED_FORMS:
            if re.search(pattern, text_lower):
                return form
        return None


# ── Convenience runner ─────────────────────────────────────────────────────────

async def scrape_and_normalize() -> pd.DataFrame:
    """Scrape Jan Aushadhi and return a normalized DataFrame."""
    scraper = JanAushadhiScraper()
    raw_path = await scraper.scrape()
    return JanAushadhiNormalizer().normalize(raw_path)


if __name__ == "__main__":
    asyncio.run(scrape_and_normalize())
