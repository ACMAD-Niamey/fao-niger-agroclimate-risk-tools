# Technical Note: Agroclimatic Risk Mapping and Advisory Product Support for FAO Niger

## 1. Purpose

This technical note defines the proposed product architecture, data inputs, analytical methods, implementation direction, and handover requirements for supporting FAO Niger in the use of spatial climate-risk information for agropastoral planning, agricultural advisory products, and anticipatory action.

The proposed approach is to build a modular workflow that uses:

- ACMAD's drought and forecast products as authoritative climate service inputs.
- Google Earth Engine (GEE) for complementary Earth observation indicators and custom spatial analysis.
- QGIS as the operational integration, visualization, map production, and handover environment.
- QGIS Processing scripts as the first implementation layer, written so they can later be wrapped inside a QGIS plugin with a simple user interface.
- Optional LLM-assisted advisory drafting, where the LLM supports language generation only after indicators and rule-based interpretation have been computed and validated.

The immediate objective is not to build a complex software platform. The objective is to define repeatable products that can be generated, reviewed, and used by FAO Niger and national counterparts.

## 2. Strategic Direction

The proposed direction is to separate the workflow into three layers:

1. Data and indicator ingestion
2. Risk and advisory product generation
3. Operational dissemination and handover

ACMAD's African Drought Monitoring and Advisory system already provides drought-relevant products, including the Combined Drought Indicator (CDI), which combines precipitation, soil moisture, and vegetation anomalies to classify agricultural drought conditions. The CDI approach is consistent with the agricultural drought methodology proposed by Sepulcre-Canto et al. (2012), where precipitation shortage, soil moisture anomaly, and fAPAR anomaly are combined into warning levels for agricultural drought monitoring. See: https://doi.org/10.5194/nhess-12-3519-2012.

The workflow should therefore avoid duplicating ACMAD's existing drought products. Instead, the system should consume ACMAD products and combine them with agricultural exposure, pastoral exposure, water access, and socioeconomic vulnerability layers to generate operational risk and advisory outputs.

GEE will be used where additional Earth observation processing is required, for example NDVI anomaly, rangeland condition, surface water dynamics, land cover masks, soil moisture proxies, heat stress, or custom start-of-season indicators. GEE is appropriate for this role because it provides cloud-based access to large geospatial datasets and scalable processing for environmental monitoring applications, including drought, food security, and climate monitoring. See Gorelick et al. (2017): https://doi.org/10.1016/j.rse.2017.06.031.

QGIS will remain the main operational environment for local review, map production, style management, layout templates, and staff handover.

## 3. Product Architecture

The implementation should be driven by the products FAO Niger needs to generate, not by the scripts themselves. The proposed minimum product set is:

1. Agropastoral Drought Risk Map
2. Cropping-Zone Drought Risk Map
3. Pastoral and Rangeland Stress Map
4. Seasonal Agricultural Advisory Product
5. Anticipatory Action Trigger Matrix
6. Administrative Risk Summary Tables
7. Map and Advisory Export Package

Each product should have a defined purpose, input data, processing logic, outputs, and update frequency.

## 4. Product 1: Agropastoral Drought Risk Map

### Purpose

Identify areas where drought hazard overlaps with agricultural and pastoral exposure in FAO Niger's areas of intervention.

### Primary Inputs

- ACMAD Combined Drought Indicator
- ACMAD drought hazard forecast
- Cultivated area layer
- Rangeland or pastoral zone layer
- Water points
- FAO intervention areas
- Administrative boundaries
- Optional population, food security, livelihood, market access, or vulnerability layers

### Analytical Logic

The conceptual basis is the standard disaster-risk framing:

```text
Risk = Hazard x Exposure x Vulnerability
```

This framing is consistent with IPCC risk terminology, where risk emerges from interactions between hazard, exposure, and vulnerability. See IPCC AR6 framing: https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/.

For implementation, the first version should use a transparent weighted score:

```text
Agropastoral Risk Score = 0.50H + 0.30E + 0.20V
```

Where:

- H = drought hazard severity
- E = agricultural and pastoral exposure
- V = vulnerability or socioeconomic sensitivity

### Suggested Scoring

Hazard score:

```text
0 = no drought
1 = watch
2 = warning
3 = alert
```

Exposure score:

```text
0 = no relevant exposure
1 = low exposure
2 = moderate exposure
3 = high exposure
```

Vulnerability score:

```text
0 = low vulnerability
1 = moderate vulnerability
2 = high vulnerability
3 = very high vulnerability
```

Risk class:

```text
0.0-0.9 = low risk
1.0-1.6 = moderate risk
1.7-2.3 = high risk
2.4-3.0 = very high risk
```

### Outputs

- Risk raster or vector layer
- Risk map layout
- Administrative summary table
- FAO intervention-zone summary
- Metadata file describing date, input layers, indicator version, and formula

## 5. Product 2: Cropping-Zone Drought Risk Map

### Purpose

Identify cultivated areas where drought or rainfall deficits may affect crop establishment, growth, flowering, or yield formation.

### Inputs

- ACMAD CDI
- ACMAD drought hazard forecast
- ACMAD seasonal forecast or rainfall forecast product
- Cultivated area mask
- Crop calendar
- Rainfall anomaly
- Soil moisture anomaly
- Start-of-season status
- Dry-spell indicator
- Administrative boundaries

### Analytical Logic

```text
Crop Risk = Drought Hazard x Cropping Exposure x Crop Stage Sensitivity
```

The crop-stage component is important because the same climate anomaly may have different agricultural implications depending on whether crops are at planting, vegetative growth, flowering, grain filling, or harvest stage.

Suggested first-version score:

```text
Crop Risk Score = 0.40H + 0.25M + 0.20S + 0.15E
```

Where:

- H = drought hazard class
- M = moisture stress indicator, using rainfall anomaly, soil moisture anomaly, or dry-spell status
- S = crop-stage sensitivity
- E = cultivated-area exposure

This is aligned with FAO Agricultural Stress Index System logic, which uses vegetation health, crop masks, and crop-cycle information to identify agricultural areas affected by water stress. See FAO ASIS: https://eo.apps.fao.org/asis/index_1.jsp?lang=en.

### Outputs

- Cropping-zone drought risk map
- Affected cultivated area by administrative unit
- Crop-calendar advisory flag
- Draft advisory statements by zone

## 6. Product 3: Pastoral and Rangeland Stress Map

### Purpose

Identify pastoral areas where drought hazard, vegetation stress, and water access stress may affect livestock systems.

### Inputs

- ACMAD CDI
- ACMAD drought hazard forecast
- NDVI or fAPAR anomaly
- Rangeland mask
- Surface water or water-point layer
- Distance to water points
- Livestock density or pastoral livelihood zone layer, if available
- Administrative boundaries
- FAO intervention zones

### Analytical Logic

```text
Pastoral Risk Score = 0.35H + 0.30Vg + 0.20W + 0.15L
```

Where:

- H = drought hazard
- Vg = vegetation or biomass anomaly
- W = water access stress
- L = livestock or pastoral exposure

### Outputs

- Rangeland stress map
- Pastoral risk classes
- Water-point stress watch areas
- Summary by administrative unit or livelihood zone
- Advisory inputs for livestock mobility, feed, water, and animal health planning

## 7. Product 4: Seasonal Agricultural Advisory Product

### Purpose

Translate ACMAD seasonal forecast and drought forecast information into downstream advisory products for FAO Niger, extension actors, and national counterparts.

### Inputs

- ACMAD seasonal forecast
- ACMAD drought forecast
- ACMAD CDI
- Crop calendar
- Cropping-zone risk map
- Pastoral stress map
- FAO intervention zones
- Historical advisory language or approved message library

### Analytical Logic

This product should be rule-based in the first version, with optional LLM assistance for drafting text.

Example rule:

```text
IF seasonal rainfall forecast indicates elevated probability of below-normal rainfall
AND drought hazard forecast is warning or alert
AND crop calendar stage is planting or early vegetative growth
THEN advisory flag = delayed onset or early-season drought risk
```

Example output message category:

```text
Monitor conditions closely; prepare extension messaging on planting date adjustment, water conservation, drought-tolerant varieties where appropriate, and localized support to vulnerable farming households.
```

### LLM Use

If an LLM is used, it should not determine the scientific classification or trigger level. It should receive only validated indicators, rule outputs, map summaries, and an approved message library.

Recommended pattern:

```text
Validated indicators + rule-based interpretation + approved message library -> LLM draft -> expert review -> publication
```

This keeps the LLM in a drafting and synthesis role, not a decision-making role.

### Outputs

- Seasonal advisory note
- Crop-calendar update
- Zone-specific advisory statements
- Map package
- Summary table by administrative unit
- Optional French-language advisory draft

## 8. Product 5: Anticipatory Action Trigger Matrix

### Purpose

Define objective thresholds that can support anticipatory action discussions and operational decision-making.

### Inputs

- ACMAD CDI
- ACMAD drought hazard forecast
- ACMAD seasonal forecast
- Rainfall anomaly
- Start-of-season indicator
- Dry-spell indicator
- Soil moisture anomaly
- NDVI or fAPAR anomaly
- Cropping-zone risk map
- Pastoral stress map
- Exposure and vulnerability layers

### Trigger Logic

The trigger matrix should use multiple evidence levels rather than a single indicator.

Proposed trigger stages:

```text
Watch
Warning
Alert
```

Example trigger criteria:

```text
Watch:
- CDI = watch, or
- seasonal forecast indicates elevated dry tendency, or
- rainfall deficit appears in exposed agricultural areas

Warning:
- CDI = warning and exposed cultivated/rangeland area is moderate or high, or
- start of season is delayed beyond an agreed threshold, or
- dry spell exceeds threshold during a sensitive crop stage

Alert:
- CDI = alert and exposure/vulnerability is high, or
- drought forecast indicates persistence or worsening, or
- vegetation/soil moisture indicators confirm agricultural or pastoral impact
```

### Outputs

- Trigger matrix table
- Trigger map by administrative unit or FAO intervention zone
- Evidence package for decision meetings
- Recommended anticipatory action menu
- Monitoring log of trigger changes over time

## 9. Product 6: Administrative Risk Summary Tables

### Purpose

Convert spatial outputs into decision-ready summaries by region, department, commune, livelihood zone, or FAO intervention area.

### Inputs

- Risk maps
- Administrative boundaries
- Exposure layers
- Population or vulnerability layers
- Crop and pastoral masks

### Outputs

Example summary fields:

```text
admin_id
admin_name
period
drought_class
mean_risk_score
max_risk_class
cultivated_area_exposed_ha
rangeland_area_exposed_ha
water_points_in_high_risk_area
population_exposed
trigger_level
recommended_action_category
```

## 10. Product 7: Map and Advisory Export Package

### Purpose

Produce a standardized set of outputs for downstream use in bulletins, seasonal notices, reports, and coordination meetings.

### Outputs

- Print-ready map layouts in PDF or PNG
- GeoPackage containing final layers
- CSV or Excel summary table
- Metadata file
- Advisory text draft
- Processing log

## 11. Data Input Plan

### ACMAD Inputs

ACMAD should be treated as the primary source for operational drought and forecast products.

Expected ACMAD inputs:

- Combined Drought Indicator
- Drought hazard forecast
- Seasonal forecast
- Rainfall anomaly or rainfall forecast products
- Dry-spell or agriculture-relevant forecast products, where available
- Dekadal or monthly monitoring products

Access method:

- ACMAD API
- Country, date, period, indicator, and product filters
- Standardized local cache
- Metadata capture for each download

### GEE Inputs

GEE should be used for complementary indicators and custom processing.

Potential GEE-derived indicators:

- NDVI anomaly
- Vegetation condition index
- fAPAR or proxy vegetation anomaly if available
- Surface water occurrence or change
- Land cover and cultivated area masks
- Rangeland masks
- Soil moisture proxy
- Land surface temperature or heat stress
- Start-of-season indicator
- Dry-spell indicator if not already available from ACMAD

### Local and Partner Inputs

Required local layers:

- FAO intervention zones
- Administrative boundaries
- Cultivated areas
- Rangelands and pastoral zones
- Water points
- Crop calendars
- Livelihood zones
- Population or settlement layers
- Vulnerability or food security layers, where available

## 12. Implementation Architecture

The implementation should begin with QGIS Processing scripts, not a full plugin. The scripts should be written with clean inputs and outputs so that they can later be wrapped by a QGIS plugin user interface.

### Proposed Components

```text
qgis_project/
  fao_niger_agroclimate_template.qgz

scripts/
  acmad/
    fetch_acmad_product.py
    parse_acmad_response.py
    cache_acmad_product.py

  gee/
    run_gee_indicator.py
    export_gee_indicator.py
    download_gee_output.py

  processing/
    build_agropastoral_risk.py
    build_crop_risk.py
    build_pastoral_risk.py
    build_trigger_matrix.py
    summarize_by_admin.py
    export_map_package.py

styles/
  drought_classes.qml
  crop_risk.qml
  pastoral_risk.qml
  trigger_levels.qml

layouts/
  agropastoral_risk_layout.qpt
  crop_risk_layout.qpt
  pastoral_risk_layout.qpt
  advisory_layout.qpt

data/
  raw/
  processed/
  cache/
  outputs/
```

### Plugin-Ready Design

Each QGIS Processing script should expose parameters that a future plugin can pass through a simple UI.

Example parameters:

```text
country
reporting_period
admin_level
hazard_product
forecast_product
crop_calendar
exposure_layer
vulnerability_layer
output_folder
```

This allows the same backend to be used in three ways:

1. Directly from QGIS Processing Toolbox
2. From a command-line or scheduled workflow
3. From a future QGIS plugin interface

### Future Plugin UI Concept

The future QGIS plugin can provide a simple interface:

```text
Step 1: Select product
- Agropastoral drought risk
- Cropping-zone risk
- Pastoral stress
- Seasonal advisory
- Trigger matrix

Step 2: Select period and geography
- Dekad/month/season
- Admin level
- FAO intervention area

Step 3: Select data sources
- Fetch from ACMAD API
- Pull from GEE
- Use cached local data

Step 4: Generate outputs
- Map layers
- Summary tables
- Advisory draft
- Export package
```

## 13. Workflow Sequence

The recommended operational workflow is:

1. User selects reporting period and product.
2. Script checks local cache for required ACMAD products.
3. If missing or outdated, script fetches products from ACMAD API.
4. Script checks whether complementary GEE indicators are required.
5. GEE outputs are generated or downloaded.
6. Risk formulas are applied in QGIS Processing.
7. Outputs are summarized by administrative unit or FAO intervention zone.
8. Styles and layouts are applied.
9. Export package is generated.
10. Technical user reviews the outputs.
11. Advisory language is drafted using rule-based templates, optionally with LLM assistance.
12. FAO Niger or national counterparts validate the product before dissemination.

## 14. Threshold Development

Thresholds should be developed in stages.

### Stage 1: Initial Expert Rules

Use transparent rules based on ACMAD product classes and exposure levels.

Example:

```text
CDI alert + high cultivated exposure = high crop risk
CDI warning + high rangeland exposure + negative NDVI anomaly = high pastoral risk
CDI alert + high vulnerability = anticipatory action alert
```

### Stage 2: Local Validation

Review trigger thresholds with:

- FAO Niger technical staff
- National meteorological service
- Agriculture and livestock technical counterparts
- Food security or early warning partners
- Field teams

### Stage 3: Historical Testing

Where data are available, test the thresholds against historical drought seasons, agricultural impact reports, food security outcomes, or field observations.

### Stage 4: Operational Adoption

Adopt thresholds only after they are documented, reviewed, and accepted by the relevant operational partners.

## 15. Governance and Quality Control

Each generated product should include:

- Data source
- Product version
- Date of download
- Processing date
- Period represented
- Spatial resolution
- Known limitations
- Formula used
- Thresholds used
- Person or team responsible for review

For LLM-assisted advisory drafting, quality control should include:

- No direct publication without expert review
- Advisory language constrained by approved message templates
- Traceability from advisory text back to indicators and rule outputs
- Clear distinction between observed conditions, forecast conditions, and recommended actions

## 16. Phased Implementation Plan

### Phase 1: Product Definition and Prototype

Tasks:

- Confirm products with FAO Niger
- Confirm priority administrative levels and intervention zones
- Inventory available exposure and vulnerability layers
- Test ACMAD API access
- Test GEE authentication and export workflow
- Build prototype agropastoral risk map

Outputs:

- Product specification
- Data inventory
- First QGIS template
- Prototype risk map

### Phase 2: QGIS Processing Scripts

Tasks:

- Develop ACMAD API fetch scripts
- Develop GEE indicator scripts
- Develop risk scoring scripts
- Develop administrative summaries
- Develop map export package

Outputs:

- QGIS Processing scripts
- Reusable styles
- Layout templates
- Sample output package

### Phase 3: Advisory and Trigger Logic

Tasks:

- Define rule-based advisory logic
- Define anticipatory action trigger matrix
- Create approved message library
- Test seasonal forecast and drought forecast integration
- Add optional LLM-assisted drafting workflow

Outputs:

- Advisory generator prototype
- Trigger matrix
- Advisory templates
- Review workflow

### Phase 4: Plugin Wrapper

Tasks:

- Wrap validated scripts in QGIS plugin UI
- Add simple data-source selection
- Add product selection
- Add progress logging and error handling
- Package documentation

Outputs:

- QGIS plugin prototype
- User guide
- Technical guide
- Training materials

## 17. Key Decisions Required

The following decisions should be made before implementation:

1. Which ACMAD API products are authoritative for each use case?
2. Which administrative level should be used for reporting?
3. Which crop calendar should be used for Niger?
4. Which land use or cultivated-area product should be adopted?
5. Which vulnerability layers are acceptable for operational use?
6. Which products must work offline using cached data?
7. Should advisory drafting be rule-based only, or rule-based with optional LLM assistance?
8. Who validates trigger thresholds before they are used operationally?
9. Should the first user interface be QGIS Processing Toolbox only, or a lightweight plugin prototype?

## 18. Recommended Immediate Tasks

1. Create a product specification table for the seven products listed above.
2. Confirm ACMAD API endpoints and response formats for CDI, drought forecast, and seasonal forecast.
3. Compile FAO Niger intervention zones, admin boundaries, cultivated areas, rangelands, water points, and crop calendars.
4. Select one pilot geography and one reporting period.
5. Prototype the agropastoral drought risk map.
6. Validate the risk formula and classes with technical counterparts.
7. Build the QGIS Processing scripts only after the product logic is accepted.

## 19. References

- Sepulcre-Canto, G., Horion, S., Singleton, A., Carrao, H., and Vogt, J. (2012). Development of a Combined Drought Indicator to detect agricultural drought in Europe. Natural Hazards and Earth System Sciences, 12, 3519-3531. https://doi.org/10.5194/nhess-12-3519-2012
- Gorelick, N., Hancher, M., Dixon, M., Ilyushchenko, S., Thau, D., and Moore, R. (2017). Google Earth Engine: Planetary-scale geospatial analysis for everyone. Remote Sensing of Environment, 202, 18-27. https://doi.org/10.1016/j.rse.2017.06.031
- FAO. Agricultural Stress Index System (ASIS). https://eo.apps.fao.org/asis/index_1.jsp?lang=en
- IPCC. Climate Change 2021: The Physical Science Basis, Chapter 1: Framing, Context and Methods. https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/
- ACMAD. African Drought Monitoring and Advisory indicators. https://ada.acmad.org/api/main/indicators/
- ACMAD. Climate and Development Products. https://acmad.org/cdd/
