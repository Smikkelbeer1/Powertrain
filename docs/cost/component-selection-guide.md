# Albatross component selection and costing guide

29 October 2026 • full-size powertrain • motors excluded

## What this deliverable establishes

This is a research-backed shortlist and runnable preliminary budget, not a released aircraft purchasing list. There are **130 candidate products, families or custom offerings across 26 researched categories**, with five entries per category. Some are prototype comparison hardware or custom manufacturing routes rather than flight-ready products. **33 further custom, assembly, optional and project lines remain explicit allowances without five verified priced alternatives.** No claim is made that the request for five applicable, publicly priced products for every component has been fully satisfied.

Only eight candidate prices were found as explicit public EUR listings (three cells and five standard cold plates). All other numbers are **author-entered estimates**, not supplier prices. URLs in those rows substantiate the product or technology, not the number. There are no manufacturer quotations in this package. Stock, minimum order quantities, aviation use restrictions, exact suffixes and lead times must still be confirmed.

The numeric allowances exist so the optimizer can explore budget sensitivity without silently treating missing hardware as free. An engineering design can have a cost estimate while being infeasible. In particular, the supplied example has rotor-tip-speed and radiator-envelope issues.

## Design basis and important selection decisions

The actual uploaded code sizes a 190S25P pack in the default 750 kg run: 4,750 cells and 798 V fully charged. It represents one series string split into four battery sections, with four propulsion loops and four battery loops. This is not a validated two-independent-wing-bus architecture. The physical nacelle contains propulsion equipment; the passenger cabin is not a motor pod.

The older 800–850 V discussion must not be treated as a constant battery voltage: calculate full-charge voltage, sag, transient overvoltage and minimum usable bus voltage. Orion BMS 2's published system limit is 800 V, so it is deliberately absent from the 850 V shortlist. Cascadia CM200DZ's published operating ceiling is 840 V, and PM250DZ's is 820 V; neither is a full 850 V candidate. Their non-operating ratings are not substitutes for operating ratings.

Sources: [Orion BMS 2](https://www.orionbms.com/products/orion-bms-standard/), [CM200](https://www.cascadiamotion.com/cm-200), [PM250 datasheet](https://cascadiamotion.com/images/catalog/DataSheets/PM250.pdf).

A 30-second inverter peak does not establish capability for a 120-second hover. Use the maximum phase RMS current and electrical frequency from `drive_requirements`, including contingency cases, and obtain duration/temperature derating curves. Integrated motor/inverter prices require special treatment: with motors excluded, removing a separate inverter does not prove the integrated architecture is cheaper overall.

Cylindrical-cell cooling requires an actual side-contact or other validated thermal design. The battery-plate list includes custom manufacturing technologies; standard flat inverter plates are a separate list. A factory-bonded motor jacket is included in the excluded motor purchase and is not purchased again. An inverter's included cold plate is likewise not counted twice.

For the default example, propulsion loops require roughly 105–109 kPa pump head at 6.7–13.4 L/min; battery loops require roughly 45 kPa at 29–30 L/min. These are simultaneous operating points. The listed automotive pumps are investigation candidates, not verified matches. Fan free-air flow is also insufficient: a radiator's air resistance shifts its operating point. Nacelle fit must be checked in addition to flow.

The five-entry lists sometimes include different sizes in the same product family. This is intentional for comparing possible loop/circuit sizes; it does not mean all five are interchangeable in one fixed design.

## How to read the prices

**PUBLISHED** means a public single-unit EUR price excluding VAT. **ESTIMATE** means an author budget assumption requiring an RFQ or a distributor quotation. All tables show low/base/high sensitivity in EUR per stated unit. Estimate limits are 0.5–2× base; published-price limits are 0.8–1.25× base. These factors are transparent scenario assumptions, not market measurements. No production discounts are assumed. Standalone software, harnesses, connectors and accessories can materially change a quotation.

A custom plate's EUR/m² value is a modelling normalisation, not a supplier sales unit. The complete plate drawings determine its actual price. Similarly, custom radiator pricing is normalised to a 1000 W/K reference UA and scaled in the Python engine; it is not a vendor performance or price guarantee.


## Example budget — not a validated aircraft cost

| Scope | Low EUR | Base EUR | High EUR |
|---|---:|---:|---:|
| airborne | 100,216 | 189,270 | 364,528 |
| ground | 3,000 | 6,000 | 12,000 |
| labour | 5,200 | 10,400 | 20,800 |
| nre | 7,500 | 15,000 | 30,000 |

Including 20% contingency: **EUR 139,100 / 264,805 / 512,794**. Only **8.5%** of the base subtotal is backed by a public price listing. Therefore the headline number is not sufficiently evidenced for a procurement commitment or a final cost optimum. Motors, formal certification, full flight avionics and airframe costs are outside this total.

## 1. Battery cells

Rerun the electrical/thermal model for a changed cell; identical cell count is not an equivalent pack.

Quantity basis: `cells`. Price unit: **cell**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `cells_1` — [Molicel INR-21700-P45B](https://www.molicel.com/product/) | 3.14 / **3.93** / 4.91 | [PUBLISHED](https://www.nkon.nl/rechargeable/li-ion.html?buttontop=Flat+top&protected=Zonder&stock_availability=Op+voorraad) | Closest to inherited P45B-like model; validate the assumed resistance map. |
| `cells_2` — [Molicel INR-21700-P50B](https://www.molicel.com/product/) | 4.46 / **5.58** / 6.97 | [PUBLISHED](https://www.nkon.nl/rechargeable/li-ion.html?buttontop=Flat+top&protected=Zonder&stock_availability=Op+voorraad) | Higher nominal capacity in the same format; new heat and ageing data needed. |
| `cells_3` — [Molicel INR-21700-P42A](https://www.molicel.com/product/) | 1.98 / **2.47** / 3.09 | [PUBLISHED](https://www.nkon.nl/rechargeable/li-ion.html?brand%5B0%5D=Xtar&brand%5B1%5D=Molicel&ratings_summary=0) | Lower initial purchase cost; lower energy per cell may increase parallel count. |
| `cells_4` — [Molicel INR-21700-P60C](https://www.molicel.com/product/) | 5.00 / **10.00** / 20.00 | ESTIMATE; request quote | Candidate for energy-sensitive wing packaging; obtain production availability and full data. |
| `cells_5` — [Molicel INR-18650-P30B](https://www.molicel.com/product/) | 2.50 / **5.00** / 10.00 | ESTIMATE; request quote | Smaller cell can aid packaging; requires new holders, cooling geometry and cell count. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 2. BMS controller

Controller-only prices; matching monitor boards, harness and current sensing are separate. Passive balancing included; no separate balancing board charge. Default one series string, not two independent packs.

Quantity basis: `packs`. Price unit: **controller**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `bms_master_1` — [Sensata LiTHIUM BALANCE n-BMS master](https://lithiumbalance.com/products/n-bms/) | 700.00 / **1,400.00** / 2,800.00 | ESTIMATE; request quote | Distributed architecture supports wing modules; check installed channel count, isolation and failure response. |
| `bms_master_2` — [Sensata LiTHIUM BALANCE n3-BMS master](https://lithiumbalance.com/products/n3-bms-battery-management-system-bms/) | 1,100.00 / **2,200.00** / 4,400.00 | ESTIMATE; request quote | Distributed architecture supports wing modules; check installed channel count, isolation and failure response. |
| `bms_master_3` — [Prohelion D1000 Gen2 master](https://docs.prohelion.com/Battery_Management_Systems/Prohelion_BMS_D1000_Gen2/index.html) | 600.00 / **1,200.00** / 2,400.00 | ESTIMATE; request quote | Distributed architecture supports wing modules; check installed channel count, isolation and failure response. |
| `bms_master_4` — [Prohelion D1000 Gen1 master](https://docs.prohelion.com/Battery_Management_Systems/Prohelion_BMS_D1000_Gen1/index.html) | 250.00 / **500.00** / 1,000.00 | ESTIMATE; request quote | Distributed architecture supports wing modules; check installed channel count, isolation and failure response. |
| `bms_master_5` — [EMUS G1 CCGM master](https://emusbms.com/helpie_faq_page/) | 300.00 / **600.00** / 1,200.00 | ESTIMATE; request quote | Distributed architecture supports wing modules; check installed channel count, isolation and failure response. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 3. BMS cell-monitor / balancing boards

Round up channels separately for every physically separate battery section. Boards must match the selected master.

Quantity basis: `bms_boards`. Price unit: **board**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `bms_monitor_1` — [Sensata LiTHIUM BALANCE n-BMS cell-monitor board](https://lithiumbalance.com/products/n-bms/) | 90.00 / **180.00** / 360.00 | ESTIMATE; request quote | 12 channels per board for costing; check exact revision, temperature channels and balancing duty. |
| `bms_monitor_2` — [Sensata LiTHIUM BALANCE n3-BMS cell-monitor board](https://lithiumbalance.com/products/n3-bms-battery-management-system-bms/) | 120.00 / **240.00** / 480.00 | ESTIMATE; request quote | 12 channels per board for costing; check exact revision, temperature channels and balancing duty. |
| `bms_monitor_3` — [Prohelion D1000 Gen2 cell-monitor board](https://docs.prohelion.com/Battery_Management_Systems/Prohelion_BMS_D1000_Gen2/index.html) | 130.00 / **260.00** / 520.00 | ESTIMATE; request quote | 14 channels per board for costing; check exact revision, temperature channels and balancing duty. |
| `bms_monitor_4` — [Prohelion D1000 Gen1 cell-monitor board](https://docs.prohelion.com/Battery_Management_Systems/Prohelion_BMS_D1000_Gen1/index.html) | 110.00 / **220.00** / 440.00 | ESTIMATE; request quote | 8 channels per board for costing; check exact revision, temperature channels and balancing duty. |
| `bms_monitor_5` — [EMUS G1 CCGM cell-monitor board](https://emusbms.com/helpie_faq_page/) | 90.00 / **180.00** / 360.00 | ESTIMATE; request quote | 16 channels per board for costing; check exact revision, temperature channels and balancing duty. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 4. Separate propulsion inverter

Zero quantity if integrated into motor purchase. Inverter cold plate assumed integrated unless overridden. Peak power is not a 120-second hover rating. Exact motor compatibility remains open.

Quantity basis: `inverters`. Price unit: **inverter**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `inverter_1` — [Cascadia Motion CM350SiC](https://www.cascadiamotion.com/cm-350sic) | 6,000.00 / **12,000.00** / 24,000.00 | ESTIMATE; request quote | Published 850 V operating ceiling; phase-current and thermal duration must be matched. |
| `inverter_2` — [Motion Applied MCU-400](https://www.motionapplied.com/products) | 8,000.00 / **16,000.00** / 32,000.00 | ESTIMATE; request quote | Compact SiC option; obtain operating voltage range and continuous-current map. |
| `inverter_3` — [Motion Applied MCU-600](https://www.motionapplied.com/products) | 10,000.00 / **20,000.00** / 40,000.00 | ESTIMATE; request quote | Higher peak current in compact housing; obtain full thermal envelope. |
| `inverter_4` — [Motion Applied MCU-800](https://www.motionapplied.com/products) | 12,000.00 / **24,000.00** / 48,000.00 | ESTIMATE; request quote | Higher peak-current headroom; verify continuous rating and control support. |
| `inverter_5` — [Motion Applied MCU-X platform](https://www.motionapplied.com/products) | 11,000.00 / **22,000.00** / 44,000.00 | ESTIMATE; request quote | Configurable platform route for integrating the drive; engineering/NRE quote required. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 5. Battery cold-plate assemblies

Custom products, not stocked SKUs. Cost per layout area is an AUTHOR normalisation. Design cylindrical side-contact geometry, manifolds and electrical barriers together; a flat plate alone is not a validated replacement.

Quantity basis: `battery_plate_area`. Price unit: **m2 wetted/contact layout allowance**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `battery_plate_1` — [Boyd aluminium vacuum-brazed custom plate](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 900.00 / **1,800.00** / 3,600.00 | ESTIMATE; request quote | Lightweight custom flow passages; specify ribbed or ribbon contact for cylindrical cells. |
| `battery_plate_2` — [Boyd copper tube-in custom plate](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 750.00 / **1,500.00** / 3,000.00 | ESTIMATE; request quote | Prototyping route using continuous tubing; copper adds mass and mixed-metal concerns. |
| `battery_plate_3` — [Boyd stainless-steel tube-in custom plate](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 1,050.00 / **2,100.00** / 4,200.00 | ESTIMATE; request quote | Corrosion-resistant fluid path; heat spreading and mass need checking. |
| `battery_plate_4` — [Boyd copper-nickel tube-in custom plate](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 1,100.00 / **2,200.00** / 4,400.00 | ESTIMATE; request quote | Alternative wetted-metal choice; evaluate thermal penalty and material compatibility. |
| `battery_plate_5` — [Dana custom battery cold plate](https://www.dana.com/product/battery-cold-plate) | 900.00 / **1,800.00** / 3,600.00 | ESTIMATE; request quote | Lightweight aluminium battery-specific manufacturing route; cylindrical contact adaptation required. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 6. Additional inverter cold plates

Only for an inverter without an included cooler. Listed standard plates are prototype candidates, not proven at inverter loss. Set mounting and pressure-drop requirements.

Quantity basis: `external_inverter_plates`. Price unit: **plate**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `inverter_plate_1` — [Boyd 416101U00000G](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 68.79 / **85.99** / 107.49 | [PUBLISHED](https://www.digikey.be/en/videos/a/aavid-thermalloy/hi-contact-liquid-cold-plates) | Compact six-pass plate for bench fit checks. |
| `inverter_plate_2` — [Boyd 416201U00000G](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 116.78 / **145.97** / 182.46 | [PUBLISHED](https://www.digikey.be/en/videos/a/aavid-thermalloy/hi-contact-liquid-cold-plates) | Longer six-pass footprint can suit a long nacelle. |
| `inverter_plate_3` — [Boyd 416301U00000G](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 198.71 / **248.39** / 310.49 | [PUBLISHED](https://www.digikey.be/en/videos/a/aavid-thermalloy/hi-contact-liquid-cold-plates) | Long six-pass footprint spreads heat over greater length. |
| `inverter_plate_4` — [Boyd 416401U00000G](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 80.50 / **100.62** / 125.78 | [PUBLISHED](https://www.digikey.be/en/videos/a/aavid-thermalloy/hi-contact-liquid-cold-plates) | Alternative standard footprint; higher thermal resistance limits load. |
| `inverter_plate_5` — [Boyd 416501U00000G](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Legacy-Liquid-Cooled-Cold-Plates-Technical-Datasheet.pdf) | 67.47 / **84.34** / 105.43 | [PUBLISHED](https://www.digikey.be/en/videos/a/aavid-thermalloy/hi-contact-liquid-cold-plates) | Alternative compact plate for lower-loss electronics. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 7. Liquid-to-air radiator cores

Core-only allowance. Match UA at actual coolant/air temperatures, air and liquid pressure drops, and nacelle dimensions. No generic kW rating establishes fit.

Quantity basis: `loops`. Price unit: **core**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `radiator_1` — [PWR custom aerospace liquid-air core](https://www.pwr.com.au/app/uploads/2025/08/PWR-2025-Annual-Report.pdf) | 1,750.00 / **3,500.00** / 7,000.00 | ESTIMATE; request quote | Supplier reports eVTOL thermal-system projects; custom long/narrow core route. |
| `radiator_2` — [Conflux aviation air-liquid heat exchanger](https://www.confluxtechnology.com/industry/aviation/) | 3,000.00 / **6,000.00** / 12,000.00 | ESTIMATE; request quote | Additive manufacture offers nacelle packaging flexibility; obtain pressure-loss and mass quote. |
| `radiator_3` — [Boyd 4220G10](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Stainless-Steel-Tube-Fin-Heat-Exchangers.pdf) | 600.00 / **1,200.00** / 2,400.00 | ESTIMATE; request quote | Documented stainless tube-fin core; prototype candidate if UA and envelope match. |
| `radiator_4` — [Boyd 4310G10](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Stainless-Steel-Tube-Fin-Heat-Exchangers.pdf) | 750.00 / **1,500.00** / 3,000.00 | ESTIMATE; request quote | Larger stock core route for experimental loop validation; mass may be unattractive. |
| `radiator_5` — [Boyd 4320G10](https://info.boydcorp.com/hubfs/Thermal/Liquid-Cooling/Boyd-Stainless-Steel-Tube-Fin-Heat-Exchangers.pdf) | 1,000.00 / **2,000.00** / 4,000.00 | ESTIMATE; request quote | Larger two-fan layout; test envelope and thermal performance before selection. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 8. Electric coolant pumps

Automotive prototype candidates. Published free-flow litres/minute is NOT flow at required pump head. Default model head may exceed these pumps; strict selection requires a measured curve.

Quantity basis: `loops`. Price unit: **pump**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `pump_1` — [Davies Craig EWP80 kit #8009 12V](https://daviescraig.com/electric-water-pumps) | 90.00 / **180.00** / 360.00 | ESTIMATE; request quote | Small-loop prototype route; check head and continuous service. |
| `pump_2` — [Davies Craig EWP115 nylon kit #8025 12V](https://daviescraig.com/electric-water-pumps) | 105.00 / **210.00** / 420.00 | ESTIMATE; request quote | Lower-mass housing candidate; coolant and temperature limits need checking. |
| `pump_3` — [Davies Craig EWP115 alloy kit #8040 12V](https://daviescraig.com/electric-water-pumps) | 115.00 / **230.00** / 460.00 | ESTIMATE; request quote | Metal housing for integration studies; check electrical protection. |
| `pump_4` — [Davies Craig EWP150 kit #8060 12V](https://daviescraig.com/electric-water-pumps) | 130.00 / **260.00** / 520.00 | ESTIMATE; request quote | Higher free-flow capability; does not establish sufficient pressure head. |
| `pump_5` — [Davies Craig EWP150 kit #8061 24V](https://daviescraig.com/electric-water-pumps) | 140.00 / **280.00** / 560.00 | ESTIMATE; request quote | Fits a 24 V auxiliary architecture if hydraulic curve meets the loop. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 9. Radiator fan / blower

One fan per loop is only a budget count. Confirm pressure-flow curve at hover; axial fans may fail the 500–1000 Pa requirement. Custom blower could replace the entire choice.

Quantity basis: `fans`. Price unit: **fan**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `fan_1` — [SPAL VA117-ABL506P-103A](https://test.spalautomotive.com/documents/20182/94723/brushless_catalogue.pdf/011138a9-0a3f-4ada-9dc6-31560ef69104) | 175.00 / **350.00** / 700.00 | ESTIMATE; request quote | Brushless 12 V fan family; larger face area may conflict with nacelle. |
| `fan_2` — [SPAL VA97-ABL322P/N-103A](https://test.spalautomotive.com/documents/20182/94723/brushless_catalogue.pdf/011138a9-0a3f-4ada-9dc6-31560ef69104) | 150.00 / **300.00** / 600.00 | ESTIMATE; request quote | Lower-power brushless candidate for lower-resistance core. |
| `fan_3` — [SPAL VA97-BBL339P/N-103A](https://test.spalautomotive.com/documents/20182/94723/brushless_catalogue.pdf/011138a9-0a3f-4ada-9dc6-31560ef69104) | 160.00 / **320.00** / 640.00 | ESTIMATE; request quote | 24 V brushless candidate; useful with a 24 V auxiliary bus. |
| `fan_4` — [SPAL VA164-ABL806HT/R-116A](https://test.spalautomotive.com/documents/20182/94723/brushless_catalogue.pdf/011138a9-0a3f-4ada-9dc6-31560ef69104) | 250.00 / **500.00** / 1,000.00 | ESTIMATE; request quote | Higher-power fan route; likely large for the nacelle. |
| `fan_5` — [SPAL VA164A-ABL1002HT/R-124A](https://test.spalautomotive.com/documents/20182/94723/brushless_catalogue.pdf/011138a9-0a3f-4ada-9dc6-31560ef69104) | 325.00 / **650.00** / 1,300.00 | ESTIMATE; request quote | High-power fan route for forced-air trials; packaging and pressure-flow verification essential. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 10. Coolant hose / tubing

Lengths include supply and return. Choose ID from hydraulic model; suffix, pressure, bend radius, permeation and vibration qualification still required.

Quantity basis: `hose_m`. Price unit: **m**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `hose_1` — [Parker 7395 E-Z Form](https://discover.parker.com/Coolant-Distribution-System) | 12.50 / **25.00** / 50.00 | ESTIMATE; request quote | Formable hose suits curved nacelle routing. |
| `hose_2` — [Parker 7181](https://discover.parker.com/Coolant-Distribution-System) | 7.00 / **14.00** / 28.00 | ESTIMATE; request quote | Heater/coolant hose option for short flexible routes. |
| `hose_3` — [Parker 801 Push-Lok](https://discover.parker.com/Coolant-Distribution-System) | 9.00 / **18.00** / 36.00 | ESTIMATE; request quote | Assembly-friendly hose route with matching approved fittings. |
| `hose_4` — [Parker 804 Push-Lok](https://discover.parker.com/Coolant-Distribution-System) | 10.00 / **20.00** / 40.00 | ESTIMATE; request quote | Alternative coolant distribution hose; check temperature and coolant compatibility. |
| `hose_5` — [Parker ECH](https://discover.parker.com/Coolant-Distribution-System) | 14.00 / **28.00** / 56.00 | ESTIMATE; request quote | Electronic cooling hose family targets battery thermal distribution. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 11. Coolant dry-break couplings

Prices cover both halves as an allowance. Connection diameter, coolant seals and actual pressure drop must be specified.

Quantity basis: `qd_pairs`. Price unit: **mated pair**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `quick_disconnect_1` — [CPC Everis LQ2](https://www.cpcworldwide.com/Portals/0/Downloadable-Content/TRM/Literature/Catalogs/CPC-Liquid-Cooling-Catalog.pdf) | 45.00 / **90.00** / 180.00 | ESTIMATE; request quote | Small branches; likely restrictive for the main loop. |
| `quick_disconnect_2` — [CPC Everis LQ4](https://www.cpcworldwide.com/Portals/0/Downloadable-Content/TRM/Literature/Catalogs/CPC-Liquid-Cooling-Catalog.pdf) | 60.00 / **120.00** / 240.00 | ESTIMATE; request quote | Intermediate bore for modest flows. |
| `quick_disconnect_3` — [CPC Everis LQ4S](https://www.cpcworldwide.com/Portals/0/Downloadable-Content/TRM/Literature/Catalogs/CPC-Liquid-Cooling-Catalog.pdf) | 70.00 / **140.00** / 280.00 | ESTIMATE; request quote | Alternative liquid-cooling connection geometry. |
| `quick_disconnect_4` — [CPC Everis LQ6](https://www.cpcworldwide.com/Portals/0/Downloadable-Content/TRM/Literature/Catalogs/CPC-Liquid-Cooling-Catalog.pdf) | 90.00 / **180.00** / 360.00 | ESTIMATE; request quote | Larger flow route for reducing coupling losses. |
| `quick_disconnect_5` — [CPC Everis LQ8](https://www.cpcworldwide.com/Portals/0/Downloadable-Content/TRM/Literature/Catalogs/CPC-Liquid-Cooling-Catalog.pdf) | 110.00 / **220.00** / 440.00 | ESTIMATE; request quote | Largest shortlisted route; increased mass and envelope. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 12. Thermal interface / dielectric pads

Price normalised to 0.5 mm nominal sheet. Exact thickness and compression change both thermal resistance and price. Breakdown voltage is not the allowable continuous working voltage.

Quantity basis: `tim_area`. Price unit: **m2**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `tim_1` — [BERGQUIST GAP PAD HC3.0](https://dm.henkel-dam.com/is/content/henkel/lt-8305-materials-for-power-storage-systems-electric-and-hybrid-vehicle-solutions-24-pages) | 100.00 / **200.00** / 400.00 | ESTIMATE; request quote | Compliant interface to accommodate cell/plate variation. |
| `tim_2` — [BERGQUIST GAP PAD HC5.0](https://dm.henkel-dam.com/is/content/henkel/lt-8305-materials-for-power-storage-systems-electric-and-hybrid-vehicle-solutions-24-pages) | 150.00 / **300.00** / 600.00 | ESTIMATE; request quote | Higher conductivity reduces interface drop at extra cost. |
| `tim_3` — [BERGQUIST GAP PAD 1450](https://dm.henkel-dam.com/is/content/henkel/lt-8305-materials-for-power-storage-systems-electric-and-hybrid-vehicle-solutions-24-pages) | 75.00 / **150.00** / 300.00 | ESTIMATE; request quote | Compliant economical interface for lower heat flux. |
| `tim_4` — [BERGQUIST GAP PAD 1000HD](https://dm.henkel-dam.com/is/content/henkel/lt-8305-materials-for-power-storage-systems-electric-and-hybrid-vehicle-solutions-24-pages) | 90.00 / **180.00** / 360.00 | ESTIMATE; request quote | Reinforced option where handling and puncture resistance matter. |
| `tim_5` — [BERGQUIST GAP PAD 2200SF](https://dm.henkel-dam.com/is/content/henkel/lt-8305-materials-for-power-storage-systems-electric-and-hybrid-vehicle-solutions-24-pages) | 120.00 / **240.00** / 480.00 | ESTIMATE; request quote | Silicone-free option if silicone contamination is a constraint. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 13. Main / branch / cross-tie contactors

Topology must determine count. Check continuous carry, make/break at actual V and L/R, fault current, coil power and bidirectionality; voltage alone is insufficient.

Quantity basis: `main_contactors`. Price unit: **contactor**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `contactor_1` — [Sensata Gigavac HX200](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 175.00 / **350.00** / 700.00 | ESTIMATE; request quote | HV contactor route for a compact branch. |
| `contactor_2` — [Sensata Gigavac HX21](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 225.00 / **450.00** / 900.00 | ESTIMATE; request quote | HV switching family; select exact current/coil suffix. |
| `contactor_3` — [Sensata Gigavac HX22](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 250.00 / **500.00** / 1,000.00 | ESTIMATE; request quote | Alternative HV package; compare loss and interruption requirements. |
| `contactor_4` — [Sensata GTM400](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 175.00 / **350.00** / 700.00 | ESTIMATE; request quote | Bidirectional switching candidate for distribution and cross-tie. |
| `contactor_5` — [Sensata GTM500](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 225.00 / **450.00** / 900.00 | ESTIMATE; request quote | Higher-current bidirectional alternative. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 14. Precharge / discharge relay

Do not use a low-voltage relay merely because precharge current is low. Normally-closed PNC113 is a discharge architecture option, not a drop-in precharge substitute.

Quantity basis: `precharge_relays`. Price unit: **relay**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `precharge_relay_1` — [Sensata P105](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 50.00 / **100.00** / 200.00 | ESTIMATE; request quote | Normally-open precharge candidate. |
| `precharge_relay_2` — [Sensata P115](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 60.00 / **120.00** / 240.00 | ESTIMATE; request quote | Normally-open HV precharge candidate. |
| `precharge_relay_3` — [Sensata P125](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 50.00 / **100.00** / 200.00 | ESTIMATE; request quote | PCB/threaded mounting alternative. |
| `precharge_relay_4` — [Sensata P195](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 75.00 / **150.00** / 300.00 | ESTIMATE; request quote | Higher current miniature contactor route. |
| `precharge_relay_5` — [Sensata PNC113](https://www.sensata.com/sites/default/files/a/sensata-gigavac-contactors-selection-guide.pdf) | 65.00 / **130.00** / 260.00 | ESTIMATE; request quote | Normally-closed discharge option only. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 15. Precharge / discharge resistor networks

Values are a cost allowance for a SERIES NETWORK of selected family resistors, not a single resistor across 850 V. Engineer resistance, insulation, pulse energy 0.5*C*V^2 and repetition.

Quantity basis: `resistor_networks`. Price unit: **network**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `resistor_1` — [Vishay Dale RH025 series network](https://www.vishay.com/docs/30201/rhnh.pdf) | 22.50 / **45.00** / 90.00 | ESTIMATE; request quote | Small elements for distributed heat. |
| `resistor_2` — [Vishay Dale RH050 series network](https://www.vishay.com/docs/30201/rhnh.pdf) | 30.00 / **60.00** / 120.00 | ESTIMATE; request quote | Common chassis-mounted prototype network. |
| `resistor_3` — [Vishay Dale RH100 series network](https://www.vishay.com/docs/30201/rhnh.pdf) | 45.00 / **90.00** / 180.00 | ESTIMATE; request quote | Greater heat dissipation per element. |
| `resistor_4` — [Vishay Dale RH250 series network](https://www.vishay.com/docs/30201/rhnh.pdf) | 90.00 / **180.00** / 360.00 | ESTIMATE; request quote | Higher thermal capacity, greater mass. |
| `resistor_5` — [Vishay Dale NH050 series network](https://www.vishay.com/docs/30201/rhnh.pdf) | 32.50 / **65.00** / 130.00 | ESTIMATE; request quote | Non-inductive network when inductance is problematic. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 16. HV branch fuses

Only branch protection candidates. Main-pack and auxiliary fuse lines have separate allowances. Coordinate DC breaking rating, I2t, minimum breaking current and thermal cycling.

Quantity basis: `branch_fuses`. Price unit: **fuse**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `fuse_1` — [Mersen MEV100A125-4](https://www.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse) | 40.00 / **80.00** / 160.00 | ESTIMATE; request quote | 125 A nominal option; cannot substitute for required circuit-current sizing. |
| `fuse_2` — [Mersen MEV100A150-4](https://www.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse) | 42.50 / **85.00** / 170.00 | ESTIMATE; request quote | 150 A nominal option; cannot substitute for required circuit-current sizing. |
| `fuse_3` — [Mersen MEV100A200-4](https://www.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse) | 47.50 / **95.00** / 190.00 | ESTIMATE; request quote | 200 A nominal option; cannot substitute for required circuit-current sizing. |
| `fuse_4` — [Mersen MEV100A250-4](https://www.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse) | 55.00 / **110.00** / 220.00 | ESTIMATE; request quote | 250 A nominal option; cannot substitute for required circuit-current sizing. |
| `fuse_5` — [Mersen MEV100A300-4](https://www.mersen.com/en/products/evpack-fuse-mev100a-1000-vdc-max-l-r-less-or-equal-1ms-50-300a-round-body-fuse) | 65.00 / **130.00** / 260.00 | ESTIMATE; request quote | 300 A nominal option; cannot substitute for required circuit-current sizing. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 17. Insulation monitoring devices

Only one active measurement scheme per interconnected island unless explicitly coordinated. Industrial options are heavier prototype alternatives; qualification and system leakage capacitance require review.

Quantity basis: `electrical_islands`. Price unit: **device**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `imd_1` — [Bender iso175](https://www.bender.de/produkte/insulation-monitoring/) | 325.00 / **650.00** / 1,300.00 | ESTIMATE; request quote | Vehicle traction focus; preferred family to investigate. |
| `imd_2` — [Bender iso685](https://www.bender.de/produkte/insulation-monitoring/) | 800.00 / **1,600.00** / 3,200.00 | ESTIMATE; request quote | Industrial comparison for lab integration; mass penalty. |
| `imd_3` — [Bender iso685-B](https://www.bender.de/produkte/insulation-monitoring/) | 950.00 / **1,900.00** / 3,800.00 | ESTIMATE; request quote | Coupled-network variant; investigate bus cross-tie coordination. |
| `imd_4` — [Bender isoHV425 + AGH422](https://www.bender.de/produkte/insulation-monitoring/) | 600.00 / **1,200.00** / 2,400.00 | ESTIMATE; request quote | Coupled HV monitoring assembly; include both devices. |
| `imd_5` — [Bender IR155-4204](https://www.bender.de/produkte/insulation-monitoring/) | 225.00 / **450.00** / 900.00 | ESTIMATE; request quote | Compact traction-monitoring route; verify voltage and interface revision. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 18. HV power connectors

Select exact 1000/1500 V variant. One pair is one pole, not a complete positive/negative cable. Shield/HVIL are not present on every variant.

Quantity basis: `hv_connector_pairs`. Price unit: **mated single-pole pair**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `hv_connector_1` — [Amphenol SurLok Plus 8.0 mm EMI](https://amphenol-industrial.com/products/surlok-plus/) | 45.00 / **90.00** / 180.00 | ESTIMATE; request quote | Shielded route for smaller branches; verify ampacity. |
| `hv_connector_2` — [Amphenol SurLok Plus 10.3 mm](https://amphenol-industrial.com/products/surlok-plus/) | 50.00 / **100.00** / 200.00 | ESTIMATE; request quote | Intermediate current/size tradeoff. |
| `hv_connector_3` — [Amphenol SurLok Plus 12.0 mm](https://amphenol-industrial.com/products/surlok-plus/) | 65.00 / **130.00** / 260.00 | ESTIMATE; request quote | Larger current connection; external HVIL may be needed. |
| `hv_connector_4` — [Amphenol SurLok Plus 14.0 mm EMI](https://amphenol-industrial.com/products/surlok-plus/) | 80.00 / **160.00** / 320.00 | ESTIMATE; request quote | High-current shielded option; larger envelope. |
| `hv_connector_5` — [Amphenol SurLok Plus 8.0 mm non-EMI](https://amphenol-industrial.com/products/surlok-plus/) | 32.50 / **65.00** / 130.00 | ESTIMATE; request quote | Unshielded option for appropriate internal DC connections only. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 19. HV cable assemblies

EV-C2 is a terminated connection system. Price here is AUTHOR per-metre budgeting, excluding connector line to prevent double count; request a BOM split. Sum DC plus/minus and all three AC phases. 35mm2 is 850 V, larger variants 1000 V.

Quantity basis: `hv_cable_m`. Price unit: **m conductor allowance**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `hv_cable_1` — [HUBER+SUHNER RADOX EV-C2 35 mm2 assembly cable portion](https://www.hubersuhner.com/en/shop/product/cable-assemblies-systems/electric-vehicles/85257333/radox-ev-c-2-single-core-gl1) | 10.00 / **20.00** / 40.00 | ESTIMATE; request quote | Screened EV cable route; select gauge from current, losses and mass, not price. |
| `hv_cable_2` — [HUBER+SUHNER RADOX EV-C2 50 mm2 assembly cable portion](https://www.hubersuhner.com/en/shop/product/cable-assemblies-systems/electric-vehicles/85257333/radox-ev-c-2-single-core-gl1) | 13.50 / **27.00** / 54.00 | ESTIMATE; request quote | Screened EV cable route; select gauge from current, losses and mass, not price. |
| `hv_cable_3` — [HUBER+SUHNER RADOX EV-C2 70 mm2 assembly cable portion](https://www.hubersuhner.com/en/shop/product/cable-assemblies-systems/electric-vehicles/85257333/radox-ev-c-2-single-core-gl1) | 17.50 / **35.00** / 70.00 | ESTIMATE; request quote | Screened EV cable route; select gauge from current, losses and mass, not price. |
| `hv_cable_4` — [HUBER+SUHNER RADOX EV-C2 95 mm2 assembly cable portion](https://www.hubersuhner.com/en/shop/product/cable-assemblies-systems/electric-vehicles/85257333/radox-ev-c-2-single-core-gl1) | 22.50 / **45.00** / 90.00 | ESTIMATE; request quote | Screened EV cable route; select gauge from current, losses and mass, not price. |
| `hv_cable_5` — [HUBER+SUHNER RADOX EV-C2 120 mm2 assembly cable portion](https://www.hubersuhner.com/en/shop/product/cable-assemblies-systems/electric-vehicles/85257333/radox-ev-c-2-single-core-gl1) | 27.50 / **55.00** / 110.00 | ESTIMATE; request quote | Screened EV cable route; select gauge from current, losses and mass, not price. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 20. Independent pack current sensors

Check isolation/creepage at bus voltage, external conductor aperture, offset and BMS input. Not needed twice if supplied in a BJU.

Quantity basis: `current_sensors`. Price unit: **sensor**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `current_sensor_1` — [LEM HASS 200-S](https://www.lem.com/en/hass) | 25.00 / **50.00** / 100.00 | ESTIMATE; request quote | 200 A nominal range; choose headroom versus resolution for pack current. |
| `current_sensor_2` — [LEM HASS 300-S](https://www.lem.com/en/hass) | 27.50 / **55.00** / 110.00 | ESTIMATE; request quote | 300 A nominal range; choose headroom versus resolution for pack current. |
| `current_sensor_3` — [LEM HASS 400-S](https://www.lem.com/en/hass) | 30.00 / **60.00** / 120.00 | ESTIMATE; request quote | 400 A nominal range; choose headroom versus resolution for pack current. |
| `current_sensor_4` — [LEM HASS 500-S](https://www.lem.com/en/hass) | 32.50 / **65.00** / 130.00 | ESTIMATE; request quote | 500 A nominal range; choose headroom versus resolution for pack current. |
| `current_sensor_5` — [LEM HASS 600-S](https://www.lem.com/en/hass) | 35.00 / **70.00** / 140.00 | ESTIMATE; request quote | 600 A nominal range; choose headroom versus resolution for pack current. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 21. Independent HV bus voltage sensing

Redundant bus/precharge sensing; remove if included in BJU and no independent channel required. Family variant insulation and measurement range need confirmation.

Quantity basis: `voltage_sensors`. Price unit: **sensor**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `voltage_sensor_1` — [LEM DVL 1000](https://www.lem.com/en/dvl) | 100.00 / **200.00** / 400.00 | ESTIMATE; request quote | Measurement range centred on an approximately 850 V bus. |
| `voltage_sensor_2` — [LEM DVL 1500](https://www.lem.com/en/dvl) | 120.00 / **240.00** / 480.00 | ESTIMATE; request quote | Additional measuring headroom with reduced relative resolution. |
| `voltage_sensor_3` — [LEM DVL 2000](https://www.lem.com/en/dvl) | 140.00 / **280.00** / 560.00 | ESTIMATE; request quote | Higher-range alternative for test infrastructure. |
| `voltage_sensor_4` — [LEM DVL 1000-UI](https://www.lem.com/en/dvl) | 115.00 / **230.00** / 460.00 | ESTIMATE; request quote | 4–20 mA interface option; requires correct receiver. |
| `voltage_sensor_5` — [LEM DVL 1500-UI](https://www.lem.com/en/dvl) | 130.00 / **260.00** / 520.00 | ESTIMATE; request quote | Higher-range current-loop output option. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 22. Coolant / structure temperature probes

RTD coolant probes are separate from battery NTC harness allowance. Choose signal conditioning, thread and immersion length.

Quantity basis: `temperature_probes`. Price unit: **probe**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `temperature_1` — [OMEGA PR-21](https://www.omegaengineering.cn/subsection_eng/general-purpose-rtd-probes.html) | 40.00 / **80.00** / 160.00 | ESTIMATE; request quote | Vibration-resistant threaded coolant probe. |
| `temperature_2` — [OMEGA PR-26](https://www.omegaengineering.cn/subsection_eng/general-purpose-rtd-probes.html) | 50.00 / **100.00** / 200.00 | ESTIMATE; request quote | Vibration-tested bendable probe for constrained routing. |
| `temperature_3` — [OMEGA PR-31](https://www.omegaengineering.cn/subsection_eng/general-purpose-rtd-probes.html) | 60.00 / **120.00** / 240.00 | ESTIMATE; request quote | Higher-temperature connector option near propulsion electronics. |
| `temperature_4` — [OMEGA PR-22](https://www.omegaengineering.cn/subsection_eng/general-purpose-rtd-probes.html) | 37.50 / **75.00** / 150.00 | ESTIMATE; request quote | M12 connector option for removable harnesses. |
| `temperature_5` — [OMEGA PR-23](https://www.omegaengineering.cn/subsection_eng/general-purpose-rtd-probes.html) | 37.50 / **75.00** / 150.00 | ESTIMATE; request quote | M8 connector option for smaller packaging. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 23. Coolant pressure sensors

Select low-range variant spanning normal pressure and faults; no assumption that a generic 700 bar part has useful resolution for this loop.

Quantity basis: `pressure_sensors`. Price unit: **sensor**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `pressure_1` — [TE M3200](https://www.te.com.cn/content/dam/te-com/documents/sensors/global/te-sensor-solutions-catalog-pressure-sensors.pdf) | 50.00 / **100.00** / 200.00 | ESTIMATE; request quote | Analogue/digital configuration options for loop monitoring. |
| `pressure_2` — [TE M5600](https://www.te.com.cn/content/dam/te-com/documents/sensors/global/te-sensor-solutions-catalog-pressure-sensors.pdf) | 70.00 / **140.00** / 280.00 | ESTIMATE; request quote | Digital pressure/temperature sensing route. |
| `pressure_3` — [TE U5600](https://www.te.com.cn/content/dam/te-com/documents/sensors/global/te-sensor-solutions-catalog-pressure-sensors.pdf) | 75.00 / **150.00** / 300.00 | ESTIMATE; request quote | Lower-pressure variant family to investigate. |
| `pressure_4` — [TE MSP300](https://www.te.com.cn/content/dam/te-com/documents/sensors/global/te-sensor-solutions-catalog-pressure-sensors.pdf) | 45.00 / **90.00** / 180.00 | ESTIMATE; request quote | Compact isolated transducer route. |
| `pressure_5` — [TE MSP340](https://www.te.com.cn/content/dam/te-com/documents/sensors/global/te-sensor-solutions-catalog-pressure-sensors.pdf) | 50.00 / **100.00** / 200.00 | ESTIMATE; request quote | Alternative microfused pressure transducer family. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 24. Flow meters (prototype instrumentation)

Optional onboard; valuable in development. Industrial mass can be excessive. Conductivity, glycol calibration, 70C medium limit in referenced guide and flow range must be checked.

Quantity basis: `flow_meters`. Price unit: **meter**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `flow_1` — [ifm SM6000](https://www.ifm.com/ifmweb/downcont.nsf/files/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk/%24file/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk.pdf) | 175.00 / **350.00** / 700.00 | ESTIMATE; request quote | 0.1–25 L/min range for smaller loops. |
| `flow_2` — [ifm SM7000](https://www.ifm.com/ifmweb/downcont.nsf/files/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk/%24file/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk.pdf) | 210.00 / **420.00** / 840.00 | ESTIMATE; request quote | 0.2–50 L/min range for intermediate loops. |
| `flow_3` — [ifm SM8000](https://www.ifm.com/ifmweb/downcont.nsf/files/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk/%24file/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk.pdf) | 250.00 / **500.00** / 1,000.00 | ESTIMATE; request quote | 0.2–100 L/min range for larger loops. |
| `flow_4` — [ifm SM6100](https://www.ifm.com/ifmweb/downcont.nsf/files/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk/%24file/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk.pdf) | 180.00 / **360.00** / 720.00 | ESTIMATE; request quote | EPDM seal option in the smaller flow range. |
| `flow_5` — [ifm SM7100](https://www.ifm.com/ifmweb/downcont.nsf/files/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk/%24file/ifm-the-right-choice-flow-sensors-flow-meters-from-ifm-dk.pdf) | 215.00 / **430.00** / 860.00 | ESTIMATE; request quote | EPDM seal option in the intermediate flow range. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 25. HV-to-LV auxiliary converters

Cost installed redundant units; size from simultaneous pumps, fans, BMS and controllers including loss. These do not regulate the propulsion DC bus.

Quantity basis: `dc_dc_units`. Price unit: **converter**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `dc_dc_1` — [BrightLoop DCDC SP](https://brightloop.fr/support/downloads/) | 1,100.00 / **2,200.00** / 4,400.00 | ESTIMATE; request quote | 1.9 kW family; verify minimum input, output voltage, cooling and startup current. |
| `dc_dc_2` — [BrightLoop DCDC MP](https://brightloop.fr/support/downloads/) | 1,750.00 / **3,500.00** / 7,000.00 | ESTIMATE; request quote | 4.8 kW family; verify minimum input, output voltage, cooling and startup current. |
| `dc_dc_3` — [BrightLoop DCDC LP](https://brightloop.fr/support/downloads/) | 2,750.00 / **5,500.00** / 11,000.00 | ESTIMATE; request quote | 9.6 kW family; verify minimum input, output voltage, cooling and startup current. |
| `dc_dc_4` — [BrightLoop DCDC MO](https://brightloop.fr/support/downloads/) | 2,100.00 / **4,200.00** / 8,400.00 | ESTIMATE; request quote | 6 kW family; verify minimum input, output voltage, cooling and startup current. |
| `dc_dc_5` — [BrightLoop DCDC LO](https://brightloop.fr/support/downloads/) | 3,250.00 / **6,500.00** / 13,000.00 | ESTIMATE; request quote | 12 kW family; verify minimum input, output voltage, cooling and startup current. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## 26. Inhibited propylene-glycol coolant

Budget includes concentrate dilution water. Recompute density/cp/viscosity for selected mix and temperature; 30% may not meet the coldest storage requirement. Never mix inhibitor packages.

Quantity basis: `coolant_L`. Price unit: **L final mixture**.

| ID / product | Low / base / high EUR | Evidence | Why consider it / fit constraint |
|---|---:|---|---|
| `coolant_1` — [Dow DOWFROST / water mix](https://www.dow.com/en-us/brand/dowfrost.html) | 2.50 / **5.00** / 10.00 | ESTIMATE; request quote | PG coolant candidate with engineering property data. |
| `coolant_2` — [Dow DOWFROST HD / water mix](https://www.dow.com/documents/180/180-01315-01-dowfrost-hd-tds.pdf?iframe=true) | 3.00 / **6.00** / 12.00 | ESTIMATE; request quote | Inhibited PG formulation; verify all wetted metals. |
| `coolant_3` — [TYFOCOR L / water mix](https://tyfo.de/en/product-overview/) | 2.50 / **5.00** / 10.00 | ESTIMATE; request quote | European PG concentrate option; concentration controls frost protection. |
| `coolant_4` — [TYFOCOR L-eco / water mix](https://tyfo.de/en/product-overview/) | 3.00 / **6.00** / 12.00 | ESTIMATE; request quote | Alternative cooling/heating formulation; compare property curves. |
| `coolant_5` — [Glysofor L / water mix](https://www.glysofor.de/en/glysofor-l/) | 2.00 / **4.00** / 8.00 | ESTIMATE; request quote | PG coolant with published concentration/freeze relationship. |

All entries: flight suitability unverified. Exact specification and system-level approval remain required.

## Remaining bill of materials and research gaps

These entries are included in the engine, including zero-count optional items. They are **not five-product comparisons**. For custom hardware, the right next procurement input is an interface drawing or performance requirement, followed by comparable supplier quotations. Labour and NRE are not purchasable components.

| Line | Quantity rule | Base EUR per unit | Scope / missing definition |
|---|---|---:|---|
| Cell tabs, fusible links, welds and series interconnects | `cells` | 0.60 | Exclude main distribution busbars; manufacturing labour separate. |
| Cell holders, spacers and cell insulation rings | `cells` | 0.35 | Material, spacing, retention and tolerances require drawings. |
| Cell voltage leads, tap protection, NTCs, connectors and BMS harness | `series` | 3.00 | NTC density requires thermal review; separate coolant RTDs are not included. |
| Pack section enclosure, lid, seals and retention | `battery_sections` | 750.00 | Custom wing-specific structure; crash/vent design not established. |
| Cell/module fire and propagation barriers | `battery_sections` | 500.00 | Material and thickness selected after propagation testing. |
| Pack emergency vent, duct, drainage and normal pressure equalisation | `battery_sections` | 400.00 | Both normal breathing and runaway discharge paths must be engineered. |
| HV distribution busbars, insulation and junction enclosure | `electrical_islands` | 700.00 | Separate from cell interconnects. |
| Pack main fuse and insulated mount | `electrical_islands` | 220.00 | Voltage/current and fault interruption not yet specified. |
| HV/LV auxiliary fuses, fuse holders and protected distribution | `electrical_islands` | 180.00 | Includes DC/DC branch protection; excludes propulsion branch fuses. |
| 1000V-class service disconnect and HVIL | `electrical_islands` | 300.00 | Exact SKU unresolved; TE shunt 1000V variant exists, 450V fused variant is unsuitable. |
| Expansion/degas reservoir, cap, fill and drain hardware | `loops` | 180.00 | Pressure and attitude/slosh behaviour need definition. |
| Fixed fittings, elbows, tees, clamps and seals | `loops` | 180.00 | Excludes separately counted dry-break pairs. |
| Battery flow distribution manifold pair | `battery_sections` | 250.00 | Remove if included in quoted cold-plate assembly. |
| Strainer, bypass/check/isolation valves as required | `loops` | 150.00 | Optional devices can increase pressure drop; exact architecture unresolved. |
| Radiator inlet/outlet duct, fan shroud and sealing | `loops` | 400.00 | Custom nacelle geometry; no validated stock alternatives. |
| LV power, shielded data wiring, terminals, backshells and sleeving | `aircraft` | 1,200.00 | CAN/fibre topology unresolved; include HVIL wiring. |
| Powertrain supervisory controller, IO, drivers and communication interface | `electrical_islands` | 800.00 | Not the flight control computer. BMS/inverter firmware integration needed. |
| Auxiliary backup battery, charging/protection and isolation | `aircraft` | 600.00 | Size for safe shutdown/landing duty, separate from traction pack. |
| Equipment brackets, fasteners, bonding straps and vibration mounts | `aircraft` | 1,500.00 | Motor mounting hardware included, motors themselves excluded. |
| Charge inlet, protective cap, HVIL and charge-control interface | `aircraft` | 600.00 | External charger budget is ground equipment below. |
| External HV charger and charge harness | `ground` | 6,000.00 | Not airborne mass; specify pack charge window, current and grid supply. |
| Electrical/thermal assembly labour | `labour_hours` | 65.00 | EUR/hour author assumption; no supplier rate. |
| Custom drawings, tooling and integration development | `project` | 15,000.00 | One-time allowance; excludes formal aircraft certification programme. |
| Propeller/rotor blades and hub assembly | `rotors` | 5,000.00 | Custom 1.47m inner / 1.06m outer designs require aerodynamic and overspeed validation; no matched retail product identified. |
| External shaft coupling, bearings and retention if required | `shaft_assemblies` | 800.00 | Zero when completely supplied with motor/rotor assembly. |
| Reduction/speed-changing gearbox if required | `gearboxes` | 5,000.00 | Direct drive default: zero. Ratio, torque, speed and flight life unresolved. |
| Wing/rotor tilt actuator, gearbox, position sensing and locks | `tilt_actuators` | 3,500.00 | Airframe-owned interface; zero until actual architecture defines count. |
| FCC hardware and voter allowance | `flight_computers` | 2,500.00 | Outside electrical powertrain by default; not flight-control software or avionics suite. |
| Additional HV EMI filtering outside supplied inverter | `external_filters` | 500.00 | Zero by default; coordinate filter capacitance with insulation monitoring. |
| Additional DC link capacitors/busbar assembly | `external_dc_links` | 500.00 | Zero when included in inverter. Do not double count. |
| BMS junction/gateway/interface and configuration accessories | `bms_interfaces` | 600.00 | Includes required family interface/BJU and setup cable/software allowance; exact kit unresolved. |
| Optional pack preheat elements and controller | `heaters` | 400.00 | Zero in current model. Determine cold-weather/ground conditioning strategy. |
| Leak/level detection and wiring | `loops` | 80.00 | Exact sensing method and coolant compatibility unresolved. |

## Scope boundaries and integration checks

- Rotors and hubs: four custom allowances are included. Inner and outer aerodynamic designs need separate quotes; the same allowance is not proof they cost the same.
- Gearboxes, additional shaft hardware and tilt actuation: visible optional lines default to zero. Determine direct-drive/gearbox choice and the airframe team's tilt mechanism before assigning counts.
- Flight control computers, navigation, IMU, air data, GNSS, radios, actuators unrelated to powertrain and vehicle-level voting: not a complete avionics cost model. An optional FCC hardware allowance does not cover this suite.
- Motor position/temperature sensors, gate drivers, inverter current sensing, DC-link capacitor and motor cooling jacket: normally part of the supplied motor/inverter. Request an inclusion list; external filter and capacitor lines default to zero.
- Battery balancing: included in the selected BMS monitoring-board family. Check its actual balancing current and duty against the existing balancing model; do not add a second balancing-board purchase unless the design requires it.
- BMS junction/gateway units, software licences, programming adapters, harnesses and connector kits: retain their allowances until quotes itemise inclusions. A bare master board is not a complete BMS price.
- Coolant pump/fan drivers: may be integrated in their product or require separate power/control hardware. Their integration is covered only by the supervisory IO allowance until defined.
- Reservoir caps, drain/fill hardware, seals, clamps, bonding, creepage spacers and protective sleeving: included in the named assembly allowances, not silently absent.
- Optional chiller/refrigerant circuit: absent from the current liquid-air architecture. If ambient conditions require below-ambient cooling, add compressor, evaporator, condenser, expansion device, refrigerant and control costs as a new architecture; the current radiator budget cannot represent it.
- Heating: optional line at zero; specify whether ground preconditioning or onboard heating is needed.
- Main fuse/branch fuse/auxiliary fuse quantities are separate. Branch-fuse products cannot be substituted for a main battery fuse just because their voltage matches.
- Cross-tie isolation, precharge paths and coordinated IMDs require the actual electrical schematic. A generic count is not a fault-tolerant design.
- A manual service disconnect must be rated in its exact configuration. The referenced TE catalogue distinguishes a 1000 V shunt configuration from a 450 V fused configuration; do not buy the latter for this bus.
- Inspection, tooling, test equipment, flight testing, certification, insurance, logistics, scrap, spare packs and recurring maintenance are not fully modelled. Assembly and NRE are modest explicit placeholders, not a certification budget.

## Request-for-quotation information to prepare

For cells: annual and prototype quantity, traceability, batch matching, cell data, anticipated current/time/temperature profile, test samples and welding process. For pack components: section drawing, cell arrangement, vent route, retention loads, material/fire requirements and service access.

For cooling: heat load per mission phase, liquid inlet/outlet limits, actual glycol mixture, required liquid flow/head, ambient envelope, air mass flow/pressure, available dimensions, mass target, proof pressure, vibration and leak requirements. Ask for curves, not a single heat-rejection number.

For HV components: minimum/nominal/maximum DC voltage, transients, continuous and timed peak current, prospective short-circuit current, L/R, switching direction, isolation environment, connector mating halves and termination tools. For controls: CAN/fibre interfaces, update rates, fault response, independent power and diagnostic coverage.

Ask each supplier to separate recurring hardware, accessories, engineering/NRE, qualification work, minimum order quantity, shipping/tax, lead time and quotation validity. Replace the numerical assumptions only when those scopes match.

## What the optimizer can and cannot conclude

The cost engine provides an auditable EUR objective, a bill of quantities and low/base/high sensitivity for a given engineering design. It does not certify the product selection, solve failure tolerance, derive pump/fan operating curves or optimise supplier combinations. Unknown compatibility stays unknown. Strict mode therefore refuses the present catalogue.

For a useful early trade study, hold a reviewed product/architecture set fixed, rerun the engineering model for each design, reject its issues, and evaluate `optimizer_objective(..., allow_provisional=True)`. Carry low and high budgets alongside the base objective. Replace custom allowances and missing maps before interpreting a small cost difference as meaningful.
