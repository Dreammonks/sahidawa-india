-- =============================================================================
-- DEMO DATA — product catalogue rows transcribed by hand from pack photos
-- =============================================================================
-- Source: 7 photos of products bought at a pharmacy (2026-09-14). Only details
-- legible in the photos are recorded; anything not visible stays NULL.
-- data_source = 'demo_manual_from_photos' marks these as NOT from an official
-- registry. Barcode 4103040895493 is deliberately absent so the unknown-barcode
-- path can be demonstrated.
-- Re-runnable: ON CONFLICT updates the row.
-- =============================================================================

INSERT INTO public.product_barcodes
    (gtin, product_name, brand, manufacturer, marketed_by, category, regulator,
     is_medicine, pack_size, mrp, data_source, source_note)
VALUES
    ('8901138511975', 'Liv.52 (Himalaya)', 'Himalaya', NULL,
     'Himalaya Wellness Company', 'ayurvedic', 'AYUSH', TRUE, '100 tablets', 215.00,
     'demo_manual_from_photos',
     'Liver tonic tablets. Brand inferred from ingredient list (Himsra, Kasani); confirm from pack front. Label: Mfg 04/2025, Exp 03/2028.'),

    ('8906037151086', 'Karela (bitter gourd) Ayurvedic proprietary medicine', NULL, NULL,
     NULL, 'ayurvedic', 'AYUSH', TRUE, NULL, NULL,
     'demo_manual_from_photos',
     'Pack reads "Ayurvedic proprietary medicine" with bitter gourd artwork. Brand not visible in photo.'),

    ('8904188000864', 'Boericke & Tafel homeopathic product', 'Boericke & Tafel',
     'Anuspa Heritage Products Pvt. Ltd., Parwanoo, H.P.',
     'Dr. Willmar Schwabe India Pvt. Ltd.', 'homeopathic', 'AYUSH', TRUE, NULL, NULL,
     'demo_manual_from_photos',
     'Product name not visible in photo.'),

    ('4987176319432', 'Whisper sanitary pads', 'Whisper',
     'Procter & Gamble Hygiene and Health Care Limited', NULL,
     'personal_care', 'BIS', FALSE, NULL, NULL,
     'demo_manual_from_photos',
     'Pack variant not visible in photo.'),

    ('4987176319517', 'Whisper sanitary pads (XL)', 'Whisper',
     'Procter & Gamble Hygiene and Health Care Limited', NULL,
     'personal_care', 'BIS', FALSE, NULL, NULL,
     'demo_manual_from_photos',
     'XL variant per pack text.'),

    ('8904455004564', 'Chocolate nutrition powder (with sucralose)', NULL, NULL,
     NULL, 'nutraceutical', 'FSSAI', FALSE, '500 g', 666.48,
     'demo_manual_from_photos',
     'Contains non-caloric sweetener (sucralose). Brand not visible in photo. Label: batch ENC26014, FEB 2026, JUL 2027.')
ON CONFLICT (gtin) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    brand        = EXCLUDED.brand,
    manufacturer = EXCLUDED.manufacturer,
    marketed_by  = EXCLUDED.marketed_by,
    category     = EXCLUDED.category,
    regulator    = EXCLUDED.regulator,
    is_medicine  = EXCLUDED.is_medicine,
    pack_size    = EXCLUDED.pack_size,
    mrp          = EXCLUDED.mrp,
    data_source  = EXCLUDED.data_source,
    source_note  = EXCLUDED.source_note,
    updated_at   = now();
