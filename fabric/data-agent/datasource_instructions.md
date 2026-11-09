Lakehouse productiq_lakehouse, schema dbo – ProductIQ gold star schema (synthetic data for the fictional company Contoso Home Appliances). All dates are calendar dates between 2024-11-01 and 2026-10-31. year_month columns are text 'YYYY-MM' and are the easiest way to filter months.

Dimensions
- dim_product: product_id (e.g. CHA-RV-R7), product_name (CHA RoboClean R7), category (robot_vacuum, stick_vacuum, canister_vacuum, air_purifier, humidifier, rice_cooker, microwave_oven, washing_machine, refrigerator, dishwasher), subcategory, series, launch_date, discontinue_date, is_active, list_price_usd, target_segment, primary_plant_id, has_lidar, has_self_empty_dock, has_mop, is_pet_edition.
- dim_component: component_id (e.g. BLM-200), component_name, component_category (motor, battery, filter, sensor, brush, dock, ...), standard_cost_usd, is_critical, recyclable_pct, weight_g, primary_supplier_id.
- dim_supplier: supplier_id, supplier_name (e.g. Kitsune Motor Works), country, supplier_tier, supply_category, quality_rating (1-5), esg_score (0-100), status.
- dim_plant: plant_id (P-NGY, P-PEN, P-MTY, P-WRO), plant_name, country, city, monthly_capacity_units.
- dim_region: region_code (JP, KR, CN, SG, AU, US, CA, DE, FR, UK), region_name, market_cluster (APAC, AMER, EMEA), currency, fx_to_usd.
- dim_date: date_key (yyyymmdd), date, year, quarter, month, year_month, fiscal_year (April start, FY2025 = Apr 2025-Mar 2026), season_event (black_friday, singles_day, golden_week, year_end, summer, none).

Facts
- fact_feedback (one row per review or support ticket): source ('review'|'ticket'), feedback_date, year_month, product_id, region_code, channel (review platform or ticket contact channel), language ('en'|'ja'), rating (1-5, reviews only), is_pet_owner, pet_owner_source, topic, sentiment_score (-1..1), sentiment_label (positive|neutral|negative), is_negative, title, feedback_text, ticket_priority, ticket_status, csat_score. VoC questions about reviews should filter source = 'review'.
- fact_sales (product x region x channel x day): sales_date, year_month, product_id, region_code, channel (online|retail|b2b|unknown), plant_id, units_sold, gross_revenue_usd, discount_pct, net_revenue_usd. Revenue questions use net_revenue_usd unless gross is asked.
- fact_market_signal (month x region x category x metric): metric is one of market_size_usd_m (market value in USD millions), search_interest_index, avg_selling_price_usd. Never sum different metrics together. Growth = SUM(value) of last 12 months / previous 12 months - 1.
- fact_bom_cost (product x component x month): quantity_per_unit, unit_cost_usd, extended_cost_usd = quantity x unit cost. Product BOM cost for a month = SUM(extended_cost_usd).
- fact_supplier_capacity (supplier x component x month): capacity_units, committed_units, utilisation_pct, lead_time_days, alt_supplier_qualification_days (days needed to qualify an additional supplier), alt_supplier_candidate_id, supplier_count_for_component, is_single_source, risk_level (low|medium|high). For the latest month use year_month = '2026-10' or MAX(year_month).
- fact_logistics (one row per shipment): ship_date, year_month, origin_plant_id, destination_region_code, product_id, transport_mode (ocean|air|truck|rail), carrier_name, units, weight_kg, freight_cost_usd, freight_cost_per_kg_usd, co2e_kg, planned_transit_days, actual_transit_days, delay_days, is_on_time (null while in transit).
- fact_warranty (one row per claim): claim_date, year_month, product_id, region_code, is_pet_owner, component_id, failure_mode, repair_action, claim_status, claim_cost_usd, days_in_service.

Query tips: booleans can be compared portably with CAST(col AS INT) = 1. Weighted ratios (cost per kg, on-time rate) must be computed as SUM/SUM, not as an average of row ratios. customer_id is pseudonymous; never list it.
