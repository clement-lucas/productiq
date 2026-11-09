"""Synthetic unstructured documents for the Foundry IQ knowledge base (Azure AI Search).

Every document is fictional and written for the Contoso Home Appliances (CHA) demo.
Figures are injected from the metrics computed on the generated tables
(``generate_data.compute_metrics``) so that the documents and the Fabric data
agent always tell the same story.
"""
from __future__ import annotations


def header(title: str, doc_type: str, owner: str, date: str, doc_id: str) -> str:
    return (
        f"# {title}\n\n"
        f"| Field | Value |\n|---|---|\n"
        f"| Document ID | {doc_id} |\n"
        f"| Document type | {doc_type} |\n"
        f"| Owner | {owner} |\n"
        f"| Company | Contoso Home Appliances (CHA) – fictional |\n"
        f"| Date | {date} |\n"
        f"| Confidentiality | Synthetic demo data – not real company information |\n\n"
    )


def pct(v: float) -> str:
    return f"{v:.1f}%"


def build_docs(m: dict) -> dict[str, str]:
    docs: dict[str, str] = {}
    reg = m["pet_care_yoy_by_region_pct"]
    reg_rows = "\n".join(f"| {k} | {v:+.1f}% |" for k, v in reg.items())
    top_reg = list(reg.items())
    shares = m["pet_neg_topic_shares_pct"]
    share_rows = "\n".join(f"| {k} | {v:.1f}% |" for k, v in shares.items())
    mk = m["market_yoy_pct"]
    co2_modes = m["co2e_share_by_mode_last12m_pct"]
    wfm = m["robot_warranty_failure_mode_shares_pct"]

    # ------------------------------------------------------------------------------
    docs["mr-2026-q3-pet-care-cleaning-market.md"] = header(
        "Quarterly Market Report – Pet-Care Cleaning Appliances (Q3 2026 edition)", "Market report",
        "Market Intelligence Lead, Global Strategy", "2026-11-04", "MR-2026-Q3-PET") + f"""
## Executive summary

The pet-care cleaning segment (vacuums, accessories and docks positioned for households with dogs and cats)
remains the fastest-growing floor-care niche in the markets CHA serves. According to the Synthetic Market Panel,
segment value across our ten sales regions reached **USD {m['pet_care_market_last12m_usd_m']:,.0f} million** in the
twelve months November 2025 – October 2026, up **{pct(m['pet_care_yoy_pct'])} year over year** from
USD {m['pet_care_market_prev12m_usd_m']:,.0f} million in the previous twelve months (November 2024 – October 2025).
For comparison, the overall robot-vacuum category grew {pct(mk['robot_vacuum'])} and stick vacuums {pct(mk['stick_vacuum'])}
over the same period.

The growth is broad-based. Every region grew, with the strongest momentum in {top_reg[0][0]} ({top_reg[0][1]:+.1f}%),
{top_reg[1][0]} ({top_reg[1][1]:+.1f}%) and {top_reg[2][0]} ({top_reg[2][1]:+.1f}%). Japan, CHA's home market, grew
{reg.get('JP', 0):+.1f}% – slower than average but from a large base of small-dog households in apartments.

## Regional growth (market value, last 12 months vs previous 12 months)

| Region | YoY growth |
|---|---|
{reg_rows}

Source: `fact_market_signal`, category `pet_care_cleaning`, metric `market_size_usd_m`.

## Demand drivers

1. **Pet ownership keeps rising.** Panel households report more multi-pet homes and more long-haired and double-coated
   breeds. Shedding peaks in spring and autumn, which shows up as seasonal lifts in search interest.
2. **Hair management is the purchase trigger.** Consumers increasingly search for "anti-tangle", "no hair wrap" and
   "self-emptying" features. Search interest for the pet-care cleaning category rose faster than for robot vacuums overall.
3. **Hygiene and allergies.** Sealed systems and HEPA filtration are expected by pet owners with allergic family members.
4. **Convenience.** Self-emptying docks reduce exposure to dander and are now considered standard above the mid-price tier.

## Competitive landscape (fictional competitors)

- **Brightwell Home** launched a pet edition stick vacuum with a comb-type de-tangler; strong in the US and Canada.
- **Kawase Living** dominates premium robot vacuums in Japan and Korea and markets a "zero-tangle" roller.
- **Nordhaus Clean** competes on price in Europe with bagged canister models and pet accessories.

No competitor yet combines a proven anti-tangle brush roll, a self-emptying dock and a mid-market price point in a
robot form factor. This is the white space highlighted by the strategy team.

## Implications for CHA

- CHA's own Voice-of-Customer data confirms the opportunity: hair tangling on the brush roll is the number-one complaint
  of pet owners (about {m['pet_hair_tangling_share_pct']:.0f}% of their negative reviews in the last 18 months – see the
  Customer Insight Summary CI-2026-11).
- A pet-care robot vacuum would address the largest unmet need, but depends on the BLM-200 brushless motor, which is
  single-sourced and already running at roughly {m['blm200_utilisation_latest_pct']:.0f}% of allocated capacity.
- Market entry before the 2027 Golden Week and Black Friday peaks would capture the seasonal demand spikes.

## Methodology

Market sizes are modelled monthly per region and category from retail panel sell-out, marketplace scraping and
importer statistics (all synthetic for this demo). Values are in USD millions at constant exchange rates. Preliminary
monthly estimates are revised once; analyses must use the latest published value.
"""

    # ------------------------------------------------------------------------------
    docs["mr-2026-q3-smart-home-connected-appliances.md"] = header(
        "Quarterly Market Report – Smart Home & Connected Appliances (Q3 2026 edition)", "Market report",
        "Market Intelligence Lead, Global Strategy", "2026-11-04", "MR-2026-Q3-SMH") + f"""
## Headline

The smart-home appliance segment grew **{pct(mk['smart_home'])}** year over year (November 2025 – October 2026 vs the
prior twelve months), the strongest growth of any category tracked by the Synthetic Market Panel. Connected floor care is
the gateway product: robot vacuums are often the first appliance a household connects to an app.

| Category | YoY growth (market value) |
|---|---|
| Smart home (connected appliances) | {pct(mk['smart_home'])} |
| Pet-care cleaning | {pct(mk['pet_care_cleaning'])} |
| Robot vacuums | {pct(mk['robot_vacuum'])} |
| Air care (purifiers, humidifiers) | {pct(mk['air_care'])} |
| Dishwashing | {pct(mk['dishwashing'])} |
| Stick vacuums | {pct(mk['stick_vacuum'])} |
| Refrigeration | {pct(mk['refrigeration'])} |
| Kitchen small appliances | {pct(mk['kitchen_small_appliances'])} |
| Laundry | {pct(mk['laundry'])} |

## What consumers expect from connected appliances

1. **Reliable connectivity first.** App connectivity problems are a recurring complaint in CHA's own reviews for
   robot vacuums and air purifiers. Consumers judge the whole brand on whether schedules run reliably.
2. **Interoperability.** Buyers expect devices to work with the main voice assistants and with the emerging open
   interoperability standard for home devices. Proprietary-only ecosystems are losing share.
3. **Useful automation, not gimmicks.** The most valued features are scheduling, room-by-room cleaning, maintenance
   reminders (filter, brush roll, dust bag) and energy reporting.
4. **Privacy and security.** Camera-equipped robots raise privacy questions. Local processing of images and clear data
   retention policies are becoming purchase criteria in the EU and Japan.

## Over-the-air (OTA) updates as a product lever

Brands that ship meaningful OTA improvements (better maps, new no-go zones, improved obstacle recognition) see higher
review scores six months after launch. Firmware quality matters: a failed update that breaks pairing is a frequent
cause of one-star reviews.

## Regional notes

- **Japan / Korea:** compact homes favour slim robots and quiet night modes; app UX must be fully localised.
- **China:** super-app integration and live-commerce launches; Singles Day (11 November) drives the annual peak.
- **US / Canada:** Black Friday and Cyber Monday concentrate up to a third of Q4 volume; voice-assistant support is expected.
- **Europe:** energy labels, repairability information and data protection are increasingly regulated.

## Implications for CHA product planning

- Every new floor-care concept should include Wi-Fi/BLE connectivity (component WIF-M2) and a maintenance-reminder
  feature for brush roll and filter.
- Anti-tangle performance can be monitored in the field via motor-current telemetry on the brush roll, enabling
  proactive "clean your brush" notifications and evidence for marketing claims.
- Camera-based obstacle avoidance (as in the RoboClean R9) needs on-device processing to meet privacy expectations.
"""

    # ------------------------------------------------------------------------------
    docs["mr-2026-q2-apac-appliance-trends.md"] = header(
        "APAC Home Appliance Trends – Mid-Year Review 2026", "Market report",
        "Regional Marketing Director, APAC", "2026-07-20", "MR-2026-Q2-APAC") + f"""
## Overview

Asia-Pacific remains CHA's largest region, led by Japan. The first half of 2026 showed solid demand for floor care and
air care, flat demand for large kitchen and laundry appliances, and continued premiumisation in rice cookers.

## Key trends by market

**Japan.** Golden Week (late April to early May) and the summer and winter bonus seasons remain the key retail peaks.
Compact living drives demand for slim robot vacuums that fit under sofas and beds. Pet-care cleaning grew
{reg.get('JP', 0):+.1f}% (latest twelve months), driven by small-dog owners in apartments. Premium IH and pressure rice
cookers keep growing, and humidifiers peak from October to February.

**Greater China.** Singles Day (11 November) and the mid-year 618 festival dominate online sales. Consumers move quickly to
robots with mopping and self-emptying docks. Pet-care cleaning grew {reg.get('CN', 0):+.1f}%.

**South Korea.** High expectations for app quality and air-purification performance; yellow-dust seasons lift purifier
demand in spring. Pet-care cleaning grew {reg.get('KR', 0):+.1f}%.

**Singapore & SEA.** Smallest of the APAC regions but the fastest growing for pet-care cleaning
({reg.get('SG', 0):+.1f}%). Humidity makes mould-resistant docks and dust bags important.

**Australia & NZ.** Large homes with mixed flooring and a high share of pet households
({reg.get('AU', 0):+.1f}% pet-care growth). Long-runtime batteries and large dust bins matter.

## Category observations

| Category | Observation |
|---|---|
| Robot vacuums | Mid-tier LiDAR models now mainstream; self-emptying docks expected above USD 600 |
| Stick vacuums | Battery life and weight are the main buying criteria; pet editions growing |
| Air purifiers | Pollen season (February–April) peak in Japan, Korea and China |
| Humidifiers | Strongly seasonal; hygiene (no white dust, easy cleaning) is a differentiator |
| Rice cookers | Premiumisation continues; app-connected models are a niche |
| Washing machines | Heat-pump washer-dryers grow in Japan; top-loaders stable elsewhere |

## Channel dynamics

Online share keeps rising: about three quarters of CHA's China volume and roughly two thirds in Korea are sold online,
compared with under half in Japan where electronics retail chains remain strong. Marketplace reviews increasingly
influence retail purchasing too, so review sentiment is a leading indicator for sell-out.

## Risks

- Price competition from domestic brands in China.
- Currency volatility affecting imported components.
- Supply constraints for brushless motors and battery cells (see supplier briefs SB-KMW-2026 and SB-HCE-2026).

## Recommendations

1. Prioritise a pet-focused robot vacuum for Japan, Australia and Singapore in the 2027 line-up.
2. Localise app content and voice prompts fully for Japanese and Korean.
3. Plan launch timing around Golden Week (Japan) and Singles Day (China).
"""

    # ------------------------------------------------------------------------------
    docs["dg-robot-vacuum-design-standards.md"] = header(
        "Design Standard DS-RV-04 – Robot Vacuum Design Standards", "Design guideline",
        "Chief Engineer, Floor Care", "2026-03-31", "DS-RV-04 rev. C") + """
## Purpose and scope

This standard defines minimum requirements for all CHA robot vacuums (RoboClean series) from concept to mass
production. Deviations require approval from the Floor Care Design Authority.

## 1. Cleaning performance

| Requirement | Minimum | Target (premium) |
|---|---|---|
| Suction at inlet | 4,000 Pa | 7,000 Pa |
| Pick-up on carpet (test DS-T-11) | 85% | 95% |
| Edge cleaning (side brush) | 70% | 85% |
| Hair pick-up (test DS-T-14) | 80% | 95% |

## 2. Brush roll and hair management

Hair tangling is the most frequent pet-owner complaint for CHA floor care. New designs **must** pass the hair-wrap test
DS-T-17: 5 g of mixed 15–20 cm hair and dog fur on medium-pile carpet; after 10 passes no more than **10% of the hair
mass** may remain wrapped on the brush roll (anti-tangle designs target below 2%).

Design guidance:
- Prefer rubber-fin or hybrid rollers with an integrated comb or blade (de-tangler) over pure bristle rollers.
- Conical or tapered rollers that move hair towards the suction inlet are recommended.
- Brush roll removal must be tool-less and take less than 10 seconds (see repairability guideline RG-01).
- Bearings must be sealed against hair ingress; end caps must be removable for cleaning.
- Brush-roll motor current must be monitored to detect wrap and to trigger an app notification.

## 3. Motor and drive

- Suction motor: brushless DC (BLM family). The BLM-200 is the standard for mid and premium tiers.
- Motors must be derated so that continuous operation stays below 80% of rated thermal load.
- Before selecting a single-sourced motor, Procurement must confirm capacity headroom of at least 15% for the forecast
  volume plus launch build (see supplier brief SB-KMW-2026).

## 4. Battery and runtime

- Minimum runtime 120 minutes at standard power for mid-tier, 180 minutes for premium.
- Battery packs must be user-replaceable with standard tools and meet transport regulations for lithium-ion cells.
- 80% capacity retention after 500 cycles.

## 5. Navigation

- LiDAR (LDR-360) is mandatory for mid and premium tiers; AI camera obstacle avoidance (AIC-CAM) for premium.
- Cliff sensors, bumper and wheel-drop sensors on all models.
- Maps must persist across firmware updates; no-go zones configurable in the app.

## 6. Docking and emptying

- Self-emptying dock (DCK-SE) standard above USD 600 retail.
- Dust bag capacity of at least 45 days of typical use; sealed bag to protect allergy sufferers.
- Dock airflow path designed to avoid clogging with long hair (minimum duct diameter 32 mm, no sharp bends).

## 7. Acoustics

- Standard mode at most 62 dB(A); quiet mode at most 55 dB(A); dock evacuation at most 78 dB(A) for under 12 seconds.

## 8. Connectivity and software

- Wi-Fi/BLE module WIF-M2; OTA updates signed and staged with roll-back.
- Maintenance reminders for brush roll, filter and dust bag.

## 9. Cost and BOM targets

| Tier | Retail price (USD) | BOM target (share of list price) |
|---|---|---|
| Entry | 299–399 | ≤ 45% |
| Mid | 549–799 | ≤ 35% |
| Premium | 999+ | ≤ 28% |

## 10. Validation gates

Concept → Feasibility → Design freeze → EVT → DVT → PVT → Mass production. Hair-wrap test DS-T-17 is mandatory at EVT and DVT.
"""

    # ------------------------------------------------------------------------------
    docs["dg-repairability-right-to-repair.md"] = header(
        "Guideline RG-01 – Repairability and Right-to-Repair", "Design guideline",
        "Head of Product Compliance", "2026-02-15", "RG-01 rev. B") + f"""
## Why this matters

Repairability is moving from a nice-to-have to a legal requirement. Several jurisdictions where CHA sells require spare
parts availability, repair information and repairability scoring. Repairable products also reduce warranty cost: in the
last twelve months the most common robot-vacuum warranty failure mode was **{m['robot_warranty_top_failure_mode'].replace('_', ' ')}**
({wfm.get(m['robot_warranty_top_failure_mode'], 0):.1f}% of robot-vacuum claims), followed by battery degradation
({wfm.get('battery_degradation', 0):.1f}%) – both of which are user-serviceable if the design allows it.

## Principles

1. **Modularity.** Wear parts (brush rolls, side brushes, filters, batteries, wheels, dust bins, dock bags) must be
   modules that the user can replace without tools or with a standard screwdriver.
2. **Spare parts availability.** Critical spare parts stay available for at least 7 years after the end of production,
   delivered within 10 working days.
3. **Repair information.** Exploded views, part numbers and step-by-step guides published on the CHA support site.
4. **Fasteners.** Use standard screws (no glue, no single-use clips) for housings that need to be opened for repair.
5. **Software support.** Security and functional updates for at least 5 years; firmware must not block third-party
   compatible consumables.
6. **Diagnostics.** Self-diagnostics accessible via app with error codes linked to repair guides.

## Repairability score (internal)

| Criterion | Weight | Scoring guidance |
|---|---|---|
| Disassembly depth for battery | 20% | ≤ 2 steps = full points |
| Tools required | 15% | none or standard screwdriver |
| Spare parts availability | 20% | 7+ years |
| Spare parts price | 15% | ≤ 20% of product price for main modules |
| Repair documentation | 15% | public guides and exploded views |
| Software support | 15% | 5+ years |

Target internal score: **8.0 / 10** for all new products from FY2027.

## Design checklist for floor care

- Brush roll removable in under 10 seconds without tools; bearings and end caps replaceable.
- Battery pack accessible behind a single screwed cover; connector, not soldered.
- Motor module (BLM family) replaceable as a unit by service centres.
- Wheel modules clip-in with a single screw.
- Dock electronics separated from the airflow path to avoid dust damage.

## Business case

Modular design increases BOM cost by an estimated 2–4% (extra connectors, fasteners) but reduces warranty cost per claim
because parts rather than units are shipped. It is also a marketing differentiator in Europe, where repairability
information must be shown at the point of sale.

## Relationship to other standards

This guideline complements DS-RV-04 (Robot Vacuum Design Standards) and SM-03 (Sustainability & Materials Policy).
"""

    # ------------------------------------------------------------------------------
    docs["dg-sustainability-materials-policy.md"] = header(
        "Policy SM-03 – Sustainability and Materials Policy", "Policy / design guideline",
        "Director of Sustainability", "2026-01-10", "SM-03 rev. D") + f"""
## Commitments

CHA commits to (fictional targets for the demo):
- **-40% product-related CO2e intensity by 2030** versus 2022 (manufacturing, materials and logistics).
- **30% recycled plastics** on average in housings by 2027 and 50% by 2030.
- **100% recyclable packaging** with no expanded polystyrene by end of FY2026.
- **No PFAS** in coatings or treatments from 2027 model year onwards.

## Materials rules

| Material | Rule |
|---|---|
| Housings (ABS/PP) | ≥ 30% post-consumer recycled content (component HSG-ABS meets this) |
| Inner pots / coatings | PFAS-free coatings for all new rice cookers from 2027 |
| Batteries | Supplier must disclose cell origin; recycled cobalt/nickel content reported annually |
| Magnets | Rare-earth content reported; magnet-free motor designs assessed |
| Packaging | Moulded pulp or corrugated; printed with water-based inks |

## Logistics emissions

Logistics is the fastest-growing part of our product footprint. In the last twelve months (November 2025 – October 2026)
outbound shipments from CHA plants emitted **{m['co2e_last12m_t']:,.0f} t CO2e**, compared with
{m['co2e_prev12m_t']:,.0f} t in the previous twelve months. Air freight accounts for
**{co2_modes.get('air', 0):.1f}%** of these emissions despite carrying less than 2% of the shipped weight; its share rose
further with expedited robot-vacuum shipments during the battery shortage in early 2026. Ocean accounts for {co2_modes.get('ocean', 0):.1f}%
and road for {co2_modes.get('truck', 0):.1f}%.

Rules:
1. Air freight requires VP approval and a documented root cause.
2. New products should be produced in the region of sale where volumes allow (regionalisation reduces ocean miles).
3. Rail is preferred over truck for lanes above 1,000 km where available.

## Product design rules

- Energy efficiency: brushless motors (BLM family) and inverter compressors are mandatory in new designs.
- Durability: design life of at least 7 years for small appliances and 10 years for large appliances.
- Repairability: see RG-01; modular wear parts reduce lifetime footprint.
- End of life: take-back programme in EU, UK, Japan and Australia; design for disassembly.

## Sustainability scoring in the concept scorecard

The ProductIQ concept scorecard includes a **sustainability** criterion (weight 5%). Scoring guidance:
5 = recycled content ≥ 50%, modular wear parts, regional production, no air freight in launch plan;
3 = meets SM-03 minimums; 1 = below minimums.

## Reporting

Sustainability KPIs are reported quarterly to the Executive Committee. Product teams must provide an estimated
cradle-to-gate CO2e and a logistics plan at the Feasibility gate.
"""

    # ------------------------------------------------------------------------------
    docs["prd-roboclean-r9.md"] = header(
        "Product Requirements Document – CHA RoboClean R9", "Product requirements document (past PRD)",
        "Senior Product Manager, Robot Vacuums", "2024-11-20", "PRD-RV-R9 v1.4") + f"""
## Status

Launched **15 September 2025** in Japan, US, China, Korea, Germany and the UK. This PRD is kept as a reference for
future robot-vacuum programmes. Post-launch: {m['r9_units_since_launch']:,} units sold up to 31 October 2026.

## Problem statement

Premium robot-vacuum buyers want a "hands-off" experience: vacuum and mop in one run, avoid obstacles such as socks and
cables, and empty itself. Our mid-tier R7 Plus received strong reviews for its dock but lost premium deals to
competitors with mopping and camera obstacle avoidance.

## Target customer

Premium households (USD 1,000+ budget) in urban apartments and family houses; tech-savvy, value time-saving.

## Key requirements

| ID | Requirement | Priority |
|---|---|---|
| R9-01 | LiDAR navigation (LDR-360) with multi-floor maps | Must |
| R9-02 | AI camera obstacle avoidance (AIC-CAM), on-device processing | Must |
| R9-03 | Self-emptying dock (DCK-SE), 60-day bag | Must |
| R9-04 | Mopping module with auto-lift on carpet (MOP-MOD) | Must |
| R9-05 | BLM-200 suction motor, 7,000 Pa | Must |
| R9-06 | 5,200 mAh battery (BAT-5200), 180 min runtime | Must |
| R9-07 | Anti-tangle brush roll | Could (deferred) |
| R9-08 | Quiet mode ≤ 55 dB(A) | Should |

**Decision log:** R9-07 (anti-tangle brush roll) was deferred to keep the launch date and BOM target. The standard
rubber/bristle brush roll (BRR-STD) was re-used. Post-launch reviews show that pet owners still report hair wrapping on
the brush roll, so this decision should be revisited in the next programme.

## Commercials

- Retail price: USD 1,099 (premium tier).
- BOM target: ≤ USD 300; actual BOM in October 2026: USD {m['r9_bom_cost_latest_usd']:,.2f}.
- Production: Nagoya (Japan market) and Penang (other regions).

## Risks identified at the time

1. BLM-200 supply: Kitsune Motor Works was the only qualified source; the R9 adds volume on top of R7, R7 Plus and
   AirStick S8. Mitigation (not executed): qualify Nordwind Components as a second source.
2. Camera privacy concerns in the EU – mitigated by on-device processing.
3. Mop module leakage – mitigated by a seal redesign at DVT.

## Lessons learned (added October 2026)

- Launch timing before Black Friday worked well in the US and UK.
- Deferring anti-tangle was the most-cited trade-off in reviews from pet owners.
- BLM-200 utilisation at Kitsune climbed from about {m['blm200_utilisation_first_month_pct']:.0f}% to
  {m['blm200_utilisation_latest_pct']:.0f}% over two years, partly due to the R9; any new BLM-200 product needs a
  capacity plan.
"""

    # ------------------------------------------------------------------------------
    docs["prd-airpure-ap700.md"] = header(
        "Product Requirements Document – CHA AirPure AP-700", "Product requirements document (past PRD)",
        "Product Manager, Air Care", "2025-05-12", "PRD-AP-700 v1.2") + """
## Status

Launched **1 March 2026** in Japan, US, China, Korea, Germany and the UK, timed for the spring pollen season in Japan,
Korea and China.

## Problem statement

The AP-500 is well reviewed but undersized for open-plan living rooms. Customers with pets and allergies asked for faster
air changes, quieter night operation and smarter filter-life prediction.

## Target customers

Families and pet owners in larger homes (up to 70 m²), allergy sufferers, and small offices (B2B channel).

## Requirements

| ID | Requirement | Priority |
|---|---|---|
| AP7-01 | Clean air delivery rate suitable for 70 m² rooms | Must |
| AP7-02 | Dual HEPA H13 filters (HEPA-H13 × 2) plus activated carbon (CFL-ACT) | Must |
| AP7-03 | Pet mode: pre-filter for hair and dander, odour boost | Must |
| AP7-04 | Night mode ≤ 24 dB(A) | Must |
| AP7-05 | Wi-Fi app with filter-life prediction based on usage | Should |
| AP7-06 | Recycled-content housing ≥ 30% | Must (SM-03) |
| AP7-07 | Filter replacement in under 30 seconds | Must (RG-01) |

## Out of scope

Humidification (covered by MistCare H4) and ionisers (policy decision: no ozone-generating features).

## Commercials

- Retail price USD 449; target BOM ≤ 35% of list price.
- Plants: Nagoya and Penang.
- Replacement filter revenue is part of the business case (filter attach rate target 60% in year one).

## Launch plan

1. Japan and Korea first-wave retail launch on 1 March, aligned with pollen forecasts.
2. China launch with a live-commerce event.
3. US, Germany and UK online first, retail from April.

## Lessons learned (October 2026)

- Pre-launch hair and dander testing with pet-owner panels was valuable; reviews mention pet mode positively.
- Filter-life prediction reduced "filter clogged" complaints compared with AP-500.
- Supply of the fan assembly (Nordwind Components) was stable; Nordwind proved to be a reliable partner – relevant
  when considering them as a second source for brushless motors.
- Launch volume ramp was smoother than planned; regional production avoided air freight.

## Metrics to monitor

Average rating, share of negative reviews by topic (noise, filter, app connectivity), filter attach rate, warranty
claims for fan failure.
"""

    # ------------------------------------------------------------------------------
    docs["prd-airstick-s8-pet.md"] = header(
        "Product Requirements Document – CHA AirStick S8 Pet", "Product requirements document (past PRD)",
        "Product Manager, Stick Vacuums", "2023-12-05", "PRD-SV-S8PET v2.0") + f"""
## Status

Launched **1 June 2024** in Japan, US, Germany, UK, Australia and Canada. First CHA product explicitly positioned for pet
households.

## Problem statement

Pet owners told us that stick vacuums lose suction quickly when picking up fur and that hair wraps around the brush.
The S8 platform (BLM-200 motor, 25.2 V battery) had the power, but the floor head was not optimised for hair.

## Requirements

| ID | Requirement | Priority |
|---|---|---|
| S8P-01 | Pet turbo brush roll (BRR-PET) with stiffer bristles for upholstery | Must |
| S8P-02 | Mini motorised tool for pet beds and sofas | Must |
| S8P-03 | Washable HEPA H12 filter, sealed system | Must |
| S8P-04 | Hair-wrap performance better than standard S8 (DS-T-17) | Should |
| S8P-05 | Tool-less brush roll removal | Must |
| S8P-06 | Same BLM-200 motor as S8 (platform commonality) | Must |

## Target customer

Households with one or more shedding dogs or cats, living in apartments or small houses with mixed hard floors and
rugs. Secondary target: allergy-sensitive households that want a sealed system and washable HEPA filtration.

## Commercials and launch plan

- Retail price USD 499 (USD 50 premium over the standard S8), positioned against Brightwell Home's pet stick.
- Production in Penang on the shared S8 line; ocean freight to all regions.
- Launch in June 2024 with pet-influencer reviews in the US, UK and Australia; Japan launch with a compact pet tool kit.
- Accessory attach target: 25% for the spare pet turbo brush roll.

## Test results at DVT

| Test | Standard S8 | S8 Pet | Target |
|---|---|---|---|
| Hair pick-up (DS-T-14) | 86% | 93% | ≥ 90% |
| Residual hair wrap (DS-T-17) | 18% | 9% | ≤ 2% (stretch) / ≤ 10% (minimum) |
| Runtime, eco mode | 55 min | 52 min | ≥ 50 min |

## Results and lessons learned (updated October 2026)

- Sales grew strongly (pet editions are the fastest-growing stick vacuum line).
- The pet turbo brush improved pick-up, but it **did not pass the 2% anti-tangle target** in test DS-T-17; it achieved
  about 9% residual wrap. Reviews from pet owners still mention hair wrapping around the brush roll.
- Across all CHA products, hair tangling accounts for {m['pet_hair_tangling_share_pct']:.1f}% of negative reviews from
  pet owners in the last 18 months, versus {m['nonpet_hair_tangling_share_pct']:.1f}% for non-pet owners.
- Platform commonality on the BLM-200 reduced development cost but increased dependence on a single motor supplier.

## Recommendations for the next pet-focused product

1. Adopt a true anti-tangle design (comb/blade de-tangler or conical roller) and make DS-T-17 at ≤ 2% a must.
2. Combine with a self-emptying dock to reduce contact with hair and dander.
3. Validate motor supply capacity before committing launch volumes.
"""

    # ------------------------------------------------------------------------------
    docs["sb-kitsune-motor-works-blm200.md"] = header(
        "Supplier Brief – Kitsune Motor Works (BLM-200 brushless motor)", "Supplier brief",
        "Category Manager, Motors & Electromechanical", "2026-11-02", "SB-KMW-2026") + f"""
## Summary

Kitsune Motor Works (Japan, supplier ID SUP-KMW) is CHA's tier-1 supplier of brushless DC motors. It is the **only
qualified source** for the **BLM-200 brushless motor**, which powers the RoboClean R7, R7 Plus and R9 and the AirStick S8
and S8 Pet. Any new mid or premium floor-care concept (including a pet-care robot vacuum) would add BLM-200 volume.

## Capacity and utilisation

| Metric | Value (source: fact_supplier_capacity) |
|---|---|
| Suppliers qualified for BLM-200 | {m['blm200_supplier_count_latest']} (Kitsune Motor Works) |
| Utilisation of capacity allocated to CHA, {m['blm200_latest_month']} | **{m['blm200_utilisation_latest_pct']:.1f}%** |
| Average utilisation, last 3 months | {m['blm200_utilisation_last3m_avg_pct']:.1f}% |
| Utilisation, November 2024 | {m['blm200_utilisation_first_month_pct']:.1f}% |
| Committed units, {m['blm200_latest_month']} | {m['blm200_committed_units_latest']:,} |
| Allocated capacity, {m['blm200_latest_month']} | {m['blm200_capacity_units_latest']:,} |
| Current lead time | {m['blm200_lead_time_latest_days']} days |
| Unit cost, latest month | USD {m['blm200_unit_cost_latest_usd']:.2f} ({m['blm200_unit_cost_change_12m_pct']:+.1f}% over 12 months) |

Utilisation has climbed steadily from roughly two thirds to about **85%** as R9 and S8 Pet volumes grew. Kitsune's
policy is to treat allocations above 90% as "tight", which triggers longer lead times and allocation rules during
seasonal peaks (Black Friday, Singles Day and year-end). Headroom for a new product launch is therefore limited to
approximately 15% of the current allocation without an expansion.

## Second-source option

**Nordwind Components** (Germany, SUP-NWC) already supplies CHA with the BLM-150 motor, wheel modules, fan assemblies
and part of the self-emptying docks. Nordwind has a BLM-200-compatible design and has been identified as the candidate
second source (`alt_supplier_candidate_id` = SUP-NWC).

- **Qualification lead time: 42 days (about 6 weeks)** – covering sample build, design verification, EMC and thermal
  testing, PPAP documentation and a pilot run. This adds roughly six weeks to any programme that depends on dual
  sourcing before launch.
- Expected unit cost at volume: within ±3% of Kitsune pricing.
- Tooling investment: moderate (shared with BLM-150 lines).

## Risks

1. **Single-source risk** (high): any disruption at Kitsune would stop five products.
2. **Capacity risk** (high): a pet-care robot vacuum at planned volumes would push utilisation above 95% in peak months.
3. **Cost risk** (medium): BLM-200 unit cost increased {m['blm200_unit_cost_change_12m_pct']:.1f}% in 12 months due to
   tight capacity and copper prices.

## Recommended actions

1. Start Nordwind qualification immediately if a new BLM-200 product is approved (42-day lead time).
2. Negotiate a capacity expansion with Kitsune (+20% from Q2 FY2027).
3. Consider a BLM-150 variant for entry-tier concepts to spread motor demand.
4. Add BLM-200 utilisation to the monthly S&OP risk dashboard (alert at 85%).
"""

    # ------------------------------------------------------------------------------
    docs["sb-hoshizora-cell-energy-batteries.md"] = header(
        "Supplier Brief – Hoshizora Cell Energy (Li-ion battery packs)", "Supplier brief",
        "Category Manager, Batteries & Energy Storage", "2026-06-15", "SB-HCE-2026") + f"""
## Summary

Hoshizora Cell Energy (Japan, SUP-HCE) is CHA's primary supplier of lithium-ion battery packs: BAT-2600, BAT-3200,
BAT-5200 (robot vacuums) and BAT-STK (stick vacuums). Volta Ridge Energy (South Korea, SUP-VRE) is the qualified second
source for all four packs, with a typical 20–50% share depending on the pack.

## Disruption February – April 2026

In February 2026 a fire at a third-party cell-coating line serving Hoshizora reduced available capacity for about three
months (force majeure declared). Effects observed in CHA's data:

| Metric | Value |
|---|---|
| Peak utilisation of Hoshizora capacity allocated to CHA | {m['battery_disruption_max_utilisation_pct']:.1f}% |
| Peak lead time | {m['battery_disruption_max_lead_time_days']} days (normal: about 35 days) |
| Battery unit cost increase (peak month, March 2026) | about +12% |
| Volume shifted to Volta Ridge Energy | about 15% of Hoshizora's share |
| Expedited air freight of robot vacuums | increased during February–April 2026 |

Because battery packs were dual-sourced, CHA avoided stock-outs, but at a cost: air freight and premium pricing.
This is the contrast with the BLM-200 motor, where no second source exists (see SB-KMW-2026).

## Supplier profile

- Quality rating 4.4/5; ESG score 71/100.
- Cell chemistry: NMC for robot packs, with an LFP option under evaluation for docks and long-life packs.
- Pack assembly in Japan and Malaysia; cells from two cell makers.

## Technology roadmap

1. **Higher energy density packs** (+15% Wh/kg) available from 2027 – enables longer runtime for the same weight.
2. **Battery passport** data (origin, recycled content, carbon footprint) for EU compliance.
3. **Replaceable pack format** aligned with repairability guideline RG-01 (single-screw cover, connector).

## Commercial terms

- Annual volume agreement with quarterly price review indexed to lithium carbonate and nickel prices.
- Allocation clause: during force majeure, capacity is allocated pro rata to the last six months of orders.
- Safety stock held by the supplier: two weeks for BAT-3200 and BAT-STK, one week for BAT-5200.
- Quality: incoming inspection with cell-level traceability; field-failure analysis within 15 working days.

## Recommendations

1. Keep dual sourcing for all packs; raise Volta Ridge share to at least 30% for BAT-5200.
2. Concept A ("Battery & filter upgrade") should use BAT-5200 or the next-generation pack and plan for the dual source.
3. Include battery lead time and cost volatility in the cost/supplier score of every concept.
4. Hold four weeks of safety stock for battery packs ahead of Golden Week and Black Friday.
"""

    # ------------------------------------------------------------------------------
    docs["tr-technology-radar-floor-care-2026.md"] = header(
        "Technology Radar – Floor Care 2026", "Technology radar",
        "Head of Advanced Engineering", "2026-09-30", "TR-FC-2026") + """
## How to read this radar

Rings: **Adopt** (use in new products now), **Trial** (use in a lead product with fallback), **Assess** (prototype and
evaluate), **Hold** (do not use in new products).

## 1. Anti-tangle brush rolls – ADOPT

Hair wrap is the dominant pet-owner pain point. Mature solutions now exist:
- **Comb / blade de-tanglers** – a fixed comb cuts or lifts hair off the roller during rotation. Proven in competitor
  products; adds around USD 1.50–2.50 to brush roll cost.
- **Conical / tapered rollers** – geometry moves hair to one end where it is sucked away. Excellent results in lab tests
  (below 2% residual wrap in DS-T-17), slightly lower carpet pick-up.
- **Dual rubber rollers** – counter-rotating rubber rollers, very low wrap, higher cost and noise.
Recommendation: adopt comb or conical designs for all new floor-care products targeting pet owners. Estimated
development time 4–6 months including tooling with Tanuki Precision Plastics.

## 2. Self-emptying docks – ADOPT

Standard above USD 600. Next steps: larger sealed bags, anti-clog duct design for long hair, quieter evacuation
(< 75 dB(A)), and bagless cyclonic docks (Assess).

## 3. LiDAR navigation – ADOPT

LiDAR modules (LDR-360) continue to fall in cost (about 8% per year). Solid-state LiDAR is in Assess.

## 4. AI obstacle avoidance (camera) – TRIAL

Used in the RoboClean R9. Works well for socks, cables and pet waste ("pet accident avoidance" is a key pet-owner
feature). Requires on-device processing for privacy. Cost of AIC-CAM is falling about 10% per year.

## 5. Mopping – TRIAL

Rotating pads with auto-lift on carpet are now expected in premium robots. Hot-water pad washing in the dock is in
Assess. Mopping modules add complexity and water-leak risk – validate seals carefully.

## 6. Brushless motors – ADOPT

BLM family remains the standard. Note supply concentration: BLM-200 has one qualified supplier. A motor-agnostic
mounting design would allow quicker second-sourcing.

## 7. Battery technology – TRIAL / ASSESS

Higher-density NMC packs (Trial) from 2027; LFP for docks and long-life packs (Assess); swappable packs for stick
vacuums (Adopt, supports repairability).

## 8. Modular architecture – TRIAL

Common modules (brush roll, wheel, battery, dust bin) across robot tiers reduce spare part variety and support
right-to-repair regulation. Expect a 2–4% BOM premium and a 20–30% reduction in warranty handling cost.

## 9. Brush-roll telemetry – TRIAL

Monitoring brush motor current detects hair wrap and triggers maintenance notifications; also provides field evidence
for anti-tangle marketing claims.

## 10. Hold

- Ozone-generating air-care features (health and regulatory risk).
- Proprietary consumables with DRM chips (conflicts with RG-01).
- Single-sourced critical components without a qualification plan for a second source.

## Mapping to the FY2027 concept options

| Concept | Key technologies | Radar status |
|---|---|---|
| A – Battery & filter upgrade | Higher-density packs, HEPA H13 | Trial / Adopt |
| B – Modular & repairable | Modular architecture, swappable packs | Trial |
| C – Pet-care robot vacuum with anti-tangle brush and self-emptying dock | Anti-tangle roller, self-emptying dock, LiDAR, AI camera | Adopt / Trial |
"""

    # ------------------------------------------------------------------------------
    docs["ci-customer-insight-summary-pet-owners.md"] = header(
        "Customer Insight Summary – Voice of the Customer, Pet Owners", "Customer insight summary",
        "Customer Insights Manager", "2026-11-03", "CI-2026-11") + f"""
## Scope and data

Analysis of {m['reviews_total']:,} product reviews from marketplaces and the CHA online store and of customer service
tickets across all CHA product lines, November 2024 – October 2026. Topics were assigned with the keyword rules
of the ProductIQ silver layer (English and Japanese), and sentiment combines star rating and a sentiment lexicon.
Pet ownership is derived from the customer profile flag, mentions of pets in the text and the CRM segment.
Pet owners write {m['pet_owner_review_share_pct']:.1f}% of reviews; {m['ja_review_share_pct']:.1f}% of reviews are in Japanese.

## Key finding 1 – Hair tangling is the number-one pet-owner complaint

Among **{m['pet_neg_reviews_last18m']:,} negative reviews from pet owners in the last 18 months (May 2025 – October 2026)**,
the topic distribution is:

| Topic | Share of negative pet-owner reviews |
|---|---|
{share_rows}

Hair tangling on the brush roll accounts for **{m['pet_hair_tangling_share_pct']:.1f}%** – more than three times the
next topic ({m['pet_second_topic'].replace('_', ' ')}, {m['pet_second_topic_share_pct']:.1f}%). For vacuum products alone the share is
{m['pet_vacuum_hair_tangling_share_pct']:.1f}%. Among non-pet owners hair tangling is only {m['nonpet_hair_tangling_share_pct']:.1f}%
of negative reviews.

Typical verbatims (paraphrased): "I have to cut dog hair off the brush roll every few days", "cat fur wraps around the
ends and jams the bearings", "the brush stops with an error after one run".

## Key finding 2 – Tickets and warranty confirm the pattern

- In customer service tickets from pet owners (last 18 months) the top topic is also
  **{m['pet_ticket_top_topic'].replace('_', ' ')}** ({m['pet_ticket_hair_share_pct']:.1f}% of tickets).
- In robot-vacuum warranty claims (last 12 months), **brush roll jam** represents {m['robot_warranty_brush_roll_jam_share_pet_pct']:.1f}%
  of claims from pet owners versus {m['robot_warranty_brush_roll_jam_share_nonpet_pct']:.1f}% for non-pet owners.

## Key finding 3 – Other pain points

- Battery life and suction are the main complaints for stick vacuums.
- Navigation and app connectivity dominate robot-vacuum complaints from non-pet owners.
- Self-emptying docks are praised; complaints focus on clogging with long hair and on dust-bag availability.

## Customer segments

| Segment | Needs |
|---|---|
| Multi-pet households (dogs and cats) | Anti-tangle brush, large dust capacity, sealed dock, pet-waste avoidance |
| Allergy-sensitive households | HEPA H13, sealed system, low dust exposure when emptying |
| Small apartments (Japan, Korea, Singapore) | Slim robot, quiet mode, compact dock |

## Implications

1. The strongest customer-value case is a product that eliminates hair wrap (concept C) – it addresses about a third of
   pet-owner negative feedback.
2. A modular brush roll (concept B) partially addresses the problem by making cleaning easier, but not the root cause.
3. Battery and filter upgrades (concept A) address the second-tier complaints for stick vacuums.

## Caveats

Text-based topic classification uses one primary topic per review. Pet-owner identification misses customers who
neither set the profile flag, mention pets, nor appear in CRM (estimated recall about 90%).
"""

    # ------------------------------------------------------------------------------
    docs["lb-logistics-network-brief.md"] = header(
        "Logistics Network Brief – Outbound Distribution FY2026", "Logistics brief",
        "Director Global Logistics", "2026-11-05", "LB-2026-11") + f"""
## Network

CHA produces in four plants and ships finished goods to ten sales regions:

| Plant | Country | Main products | Key lanes |
|---|---|---|---|
| P-NGY Nagoya Works | Japan | RoboClean R9 (Japan), air care, rice cookers | Truck to Japan; ocean to APAC/US |
| P-PEN Penang Assembly | Malaysia | Robot and stick vacuums, washers, fridges, microwaves | Ocean to all regions; truck to Singapore |
| P-MTY Monterrey Plant | Mexico | Canister vacuums, microwaves, dishwashers | Truck/rail to US and Canada |
| P-WRO Wroclaw Plant | Poland | Canisters, washers, fridges, dishwashers | Truck/rail to Germany, France, UK |

Robot and stick vacuums for Europe and North America are shipped by ocean from Penang – the longest and most
carbon-intensive part of the floor-care supply chain.

## 2025 ocean freight spike

From June to September 2025 congestion and rerouting on Asia–Europe lanes drove a sharp increase in ocean rates.
Average ocean freight cost per kg peaked in **{m['ocean_cost_per_kg_peak_month']}** at USD {m['ocean_cost_per_kg_peak_usd']:.3f}/kg,
**{m['ocean_freight_spike_pct']:.0f}% above** the November 2024 – April 2025 baseline of USD {m['ocean_cost_per_kg_baseline_usd']:.3f}/kg.
Rerouted Asia–Europe sailings added about 3,500 km and 7–10 days of transit.

## Key figures (source: fact_logistics)

| KPI | Previous 12 months (Nov 24 – Oct 25) | Last 12 months (Nov 25 – Oct 26) |
|---|---|---|
| Freight cost (USD) | {m['freight_cost_prev12m_usd']:,.0f} | {m['freight_cost_last12m_usd']:,.0f} |
| CO2e (t) | {m['co2e_prev12m_t']:,.0f} | {m['co2e_last12m_t']:,.0f} |
| On-time delivery rate | {m['on_time_rate_prev12m_pct']:.1f}% | {m['on_time_rate_last12m_pct']:.1f}% |

CO2e by mode, last 12 months: {', '.join(f'{k} {v:.1f}%' for k, v in co2_modes.items())}.
The increase in CO2e is mainly due to air freight used to expedite robot vacuums during the battery shortage
(February–April 2026) and to volume growth.

## Implications for new products

1. **Regional production.** A new robot vacuum for Europe and North America should consider final assembly in Wroclaw or
   Monterrey to cut ocean lead time (5–6 weeks) and CO2e. Penang remains best for APAC.
2. **Dock size matters.** Self-emptying docks roughly double the shipping volume of a robot vacuum; packaging should be
   optimised (nested dock, smaller carton) to keep freight cost per unit under control.
3. **Avoid air freight in launch plans.** Build launch inventory early; air freight costs roughly 15–30 times ocean per kg.
4. **Peak planning.** Ocean bookings for Black Friday must be confirmed by mid-September; for Golden Week by early March.

## Logistics score guidance for the concept scorecard (weight 10%)

5 = regional production, standard carton, no air freight; 3 = ocean from Asia with standard packaging;
1 = oversized packaging or dependence on air freight.
"""

    # ------------------------------------------------------------------------------
    docs["cl-competitive-landscape-floor-care-2026.md"] = header(
        "Competitive Landscape – Floor Care 2026", "Competitive analysis",
        "Competitive Intelligence Analyst", "2026-10-20", "CL-FC-2026") + f"""
## Note

All competitors in this document are fictional companies created for the ProductIQ demo.

## Market context

Floor care is CHA's largest business. The robot-vacuum category grew {pct(mk['robot_vacuum'])} and pet-care cleaning
{pct(mk['pet_care_cleaning'])} over the last twelve months (Synthetic Market Panel). CHA's own robot-vacuum unit sales
grew {m['cha_robot_vacuum_units_yoy_pct']:.1f}% in the same period, driven by the R9 launch and the R7 Plus.

## Competitor profiles

**Brightwell Home (US).** Strong in North American retail. Products: pet edition stick vacuums with comb de-tangler,
mid-tier robots without LiDAR. Strengths: brand recognition with pet owners, aggressive Black Friday pricing. Weakness:
app reliability.

**Kawase Living (Japan).** Premium robots in Japan and Korea. Products: slim LiDAR robots, "zero-tangle" conical roller,
compact docks for apartments. Strengths: quality, quiet operation. Weakness: high prices, limited presence in Europe.

**Nordhaus Clean (Germany).** Value canister and stick vacuums in Europe. Strengths: distribution and repair network.
Weakness: limited robot portfolio.

**Lianhe Smart Appliances (China).** Fast follower with feature-rich robots (mopping, self-washing docks) at low prices.
Strengths: speed and cost. Weakness: perceived durability, data-privacy concerns in Europe.

## Feature comparison – robot vacuums (mid/premium)

| Feature | CHA R7 Plus | CHA R9 | Kawase premium | Lianhe flagship | Brightwell mid |
|---|---|---|---|---|---|
| LiDAR | Yes | Yes | Yes | Yes | No |
| AI camera | No | Yes | Yes | Yes | No |
| Self-emptying dock | Yes | Yes | Yes | Yes | Optional |
| Anti-tangle brush roll | No | No | Yes | Yes | n/a |
| Mopping | No | Yes | No | Yes | No |
| Replaceable battery (no special tools) | Yes | Yes | No | No | Yes |

## Insights

1. **Anti-tangle is becoming table stakes.** Two of four competitors already claim it; CHA has none in robots.
2. **Pet positioning is unoccupied in mid-tier robots.** Brightwell owns pet sticks; nobody owns a pet-focused robot
   with a self-emptying dock around USD 700–850.
3. **Repairability is a European differentiator** where CHA's battery design already scores well.
4. **Price pressure from Lianhe** in China and Southeast Asia limits pure feature-race strategies.

## Implications for FY2027 concept options

- Concept C (pet-care robot vacuum with anti-tangle brush and self-emptying dock) targets the unoccupied mid-tier pet
  position and closes the anti-tangle gap.
- Concept B (modular & repairable) leverages CHA's repairability lead in Europe.
- Concept A (battery & filter upgrade) is a low-risk refresh that defends stick-vacuum share against Brightwell.
"""
    return docs
