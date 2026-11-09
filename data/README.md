# ProductIQ synthetic data

Synthetic data estate for the fictional company **Contoso Home Appliances (CHA)** – a home-appliance maker selling in
Japan/APAC, the US and Europe. Every company, supplier, carrier, platform, product and number is invented; there is no
personal data (customer ids are pseudonymous and there are no names, e-mails or addresses).

## Run the generator

Requirements: Python 3.11 with `numpy` and `pandas` (no other packages, no network).

```bash
python data/generator/generate_data.py --out data/output --seed 42            # default demo data set
python data/generator/generate_data.py --out data/output --seed 7 --scale 0.5 # other seed, half the volume
python eval/build_golden.py                                                   # regenerate eval/golden_qa.jsonl
```

| Option | Default | Effect |
|---|---|---|
| `--out` | `data/output` | output folder (bronze and knowledge folders are recreated) |
| `--seed` | `42` | random seed; the same seed always produces byte-identical files |
| `--scale` | `1.0` | multiplies transactional volumes (sales units, reviews, tickets, warranty claims, customers). Scenario signals are ratios and keep holding; very small scales (< 0.3) can make the share-based checks noisy |

Runtime is about 50 seconds at scale 1.0; output size is about 42 MB. The run ends with a **scenario-signal validation**
(PASS/FAIL table) computed from the cleaned gold model, and exits with code 1 if any check fails.

After changing seeds or scale, re-run `python eval/build_golden.py` so the evaluation answers match the data; it also
executes every data-agent example query and checks that the Fabric notebooks still embed the same rules.

## Outputs

```
data/output/
├── bronze/<source_table>/<source_table>.csv   16 raw source-system extracts (with dirty-data patterns)
├── knowledge/*.md                             15 unstructured documents for Foundry IQ
└── manifest.json                              row counts, sizes, scenario-signal values, validation results
```

Bronze tables (seed 42): erp_regions 10, erp_plants 4, erp_suppliers 15, erp_products 27, erp_product_aliases 30,
plm_components 46, plm_bom 226, crm_customer_segments 42,084, erp_sales_orders 214,644, ecommerce_reviews 50,303,
cs_tickets 25,125, warranty_claims 6,519, scm_supplier_capacity 1,416, scm_component_costs 1,104,
logistics_shipments 20,198, market_signals 6,566. Columns, cleaning rules and the gold star schema are described in
[docs/DATA-MODEL.md](../docs/DATA-MODEL.md).

Knowledge documents (400–1,200 words each, header block with title, type, owner, date and "Synthetic demo data"):
quarterly market reports (pet-care cleaning, smart home, APAC trends), design guidelines (robot-vacuum design standard,
repairability/right-to-repair, sustainability & materials), three past PRDs (RoboClean R9, AirPure AP-700, AirStick S8 Pet),
supplier briefs (Kitsune Motor Works BLM-200, Hoshizora Cell Energy batteries), floor-care technology radar, customer
insight summary (pet owners), logistics network brief and a competitive landscape. Figures in the documents are injected
from the generated tables, so the knowledge base and the Fabric data agent always agree (for example +12.0% pet-care
growth, 31.0% hair-tangling share, 84.9% BLM-200 utilisation, 42-day second-source qualification).

## How the data is used

1. **Fabric (structured data).** Upload `bronze/` to the lakehouse **productiq_lakehouse** under
   `Files/bronze/<table>/<table>.csv` (done by the deployment scripts in `scripts/fabric`), then run
   `fabric/notebooks/01_bronze_to_silver.ipynb` and `02_silver_to_gold.ipynb`. The gold tables feed the
   **ProductIQ Data Agent** (instructions and example queries in `fabric/data-agent/`, fallback creation notebook
   `03_create_data_agent.ipynb`), which the Foundry agents use through Fabric IQ.
2. **Foundry IQ (unstructured data).** Upload `knowledge/*.md` to the blob container `knowledge` of the storage account;
   the Azure AI Search knowledge base `productiq-kb` indexes it for the market-scout and future-tech agents.
3. **Evaluation.** `eval/golden_qa.jsonl` holds the expected answers computed from this data plus RAI/red-team prompts
   (three reviews, REV-9000001..3, contain planted prompt-injection text on purpose).

## Files in `data/generator/`

| File | Purpose |
|---|---|
| `generate_data.py` | CLI generator: master data, transactions, text, dirty data, validation, manifest |
| `reference_pipeline.py` | pandas mirror of the Fabric notebooks (bronze → silver → gold) and the shared text rules (topics, sentiment lexicon, pet keywords, region aliases) |
| `knowledge_docs.py` | templates of the knowledge documents (numbers injected from the computed metrics) |

To change the scenario, edit the constants at the top of `generate_data.py` (e.g. `PET_HAIR_MULT_*`, `PET_YOY_TARGET`,
`OCEAN_INDEX`, the BLM-200 utilisation path in `gen_capacity_and_costs`). If you change the text rules in
`reference_pipeline.py`, copy the `SHARED RULES` block into the corresponding cell of notebook 01 –
`eval/build_golden.py` reports any drift.

`data/output/` is git-ignored; regenerate it locally whenever needed.
