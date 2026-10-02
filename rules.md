# Store rules for COA publishing (version 2)

Reference date for all date checks: 2026-09-30.
A COA is "current" if its test date is on or after 2025-09-30.

## Reading the COAs
1. Meridian Analytical Labs (MAL) reports: dates are YYYY-MM-DD, decimals use a point.
2. Novalab Services (NVL) reports: dates are DD/MM/YYYY and decimals use a comma. Net content may be in µg, mg or g.
3. Convert every size to mg (1000 µg = 1 mg, 1 g = 1000 mg) and every purity to a percentage with a decimal point.
4. A COA stamped VOID or SUPERSEDED is invalid. Ignore it completely, even if its test date is the newest.
5. A multi-batch COA lists several batches. Use only the row whose batch equals Batch_Listed in products.csv. If no row matches, that COA does not cover the product.

## Choosing the data for a product
6. Values on a COA (or the matching row of a multi-batch COA) override the sheet for batch, test date, purity and declared amount (size). For single-batch COAs, keep the batch exactly as printed on the COA.
7. If several valid COAs cover the same product, use the one with the newest test date.
8. If the COA leaves batch or test date blank and the sheet has a value, use the sheet value and record it as "from sheet" in the exceptions report. If both are blank, the field is missing.

## Status
9. A product gets status "publish" only if ALL are true:
   a. it has a usable COA;
   b. batch, test date, purity and size are all known (rule 8 allowed);
   c. the COA size equals Size_mg on the sheet (if not, the price may be wrong and the product is held until the price is confirmed);
   d. purity is 98.0 % or higher;
   e. identity passes: observed mass is within 1.0 Da of theoretical mass (a difference of exactly 1.0 passes);
   f. the test date is current (see top).
   Otherwise the status is "draft". Record the first failing reason from this list, in this order:
   "no COA" (no COA at all), "no COA for listed batch" (only multi-batch COAs and none matches), "missing field", "size conflict", "purity below 98.0", "identity failed", "COA older than 12 months".

## Outputs
10. COA page URL (published and draft alike, when a final batch is known): https://example-store.test/coa/<sku lowercase>-<batch lowercase>/ . If the batch is missing, or there is no usable COA, leave it blank.
11. COA library: published products only, newest test date first.
12. Homepage teaser: number of published COAs and mean purity of published products, 2 decimals.
13. Retest schedule: for each published product, retest due date = test date + 12 months (same day and month, next year). Days remaining = due date minus the reference date. A product is "due soon" if its due date is on or before 2026-12-29. Sort by due date, earliest first.
14. Featured products: choose 3 published products that are not "due soon", with the highest purity. Ties: newest test date first, then lower SKU.
15. Client email: for every draft product, in SKU order, state the reason and the action needed to unblock it:
    - no COA: send the COA PDF
    - no COA for listed batch: send the COA that covers the listed batch (name the batch)
    - missing field: send the missing field or a corrected COA
    - size conflict: confirm the price for the size printed on the COA
    - purity below 98.0: send a new COA or confirm the batch is withdrawn
    - identity failed: send a new identity (MS) result
    - COA older than 12 months: send a current COA
    Also state the total USD price of all draft products (sum of their Regular price) and the numbers of published and draft products.
