-- ALL-IN-ONE: one row per scraped source
select n as "#", source, stored_in, rows_loaded, sample
from (
    select 1 as n, 'CDSCO brand registry' as source, 'cdsco_reference' as stored_in,
           (select count(*) from cdsco_reference) as rows_loaded,
           (select string_agg(brand_name || ' (' || firm_name || ')', '; ')
              from (select brand_name, firm_name from cdsco_reference
                    where firm_name !~ '[0-9]' order by id limit 2) s) as sample
    union all
    select 2, 'CDSCO recall alert PDFs', 'drug_alerts',
           (select count(*) from drug_alerts),
           'Not loaded yet: PDFs download, but extraction needs a Gemini/Groq key'
    union all
    select 3, 'Jan Aushadhi product & MRP list', 'medicines',
           (select count(*) from medicines where source = 'janaushadhi'),
           (select string_agg(generic_name || ' ' || coalesce(strength, '') || ' Rs.' || mrp, '; ')
              from (select generic_name, strength, mrp from medicines
                    where source = 'janaushadhi' order by generic_name limit 2) s)
    union all
    select 4, 'Jan Aushadhi Kendra locations', 'pharmacies',
           (select count(distinct split_part(name, ' - ', 1)) from pharmacies where name like 'PMBJK%'),
           (select string_agg(kendra_code || ' ' || district || ', ' || state, '; ')
              from (select distinct split_part(name, ' - ', 1) as kendra_code, district, state
                    from pharmacies where name like 'PMBJK%' order by kendra_code limit 2) s)
    union all
    select 5, 'Commercial medicine dataset', 'medicines',
           (select count(*) from medicines where source = 'commercial'),
           (select string_agg(brand_name || ' Rs.' || mrp, '; ')
              from (select brand_name, mrp from medicines
                    where source = 'commercial' order by brand_name limit 2) s)
) as summary
order by n;

-- SOURCE 1: CDSCO brand registry
select brand_name, firm_name from cdsco_reference where firm_name !~ '[0-9]' order by id limit 10;

-- SOURCE 2: CDSCO recall alert PDFs
select count(*) as alert_rows from drug_alerts;

-- SOURCE 3: Jan Aushadhi product & MRP list
select generic_name, strength, dosage_form, mrp from medicines where source = 'janaushadhi';

-- SOURCE 4: Jan Aushadhi Kendra locations
select distinct split_part(name, ' - ', 1) as kendra_code, district, state
from pharmacies where name like 'PMBJK%' order by kendra_code;

-- SOURCE 5: Commercial medicine dataset
select brand_name, manufacturer, mrp from medicines where source = 'commercial';
