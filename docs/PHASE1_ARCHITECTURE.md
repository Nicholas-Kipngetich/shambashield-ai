# ShambaShield AI — Phase 1: Problem, Architecture and Requirements

**Status:** Complete — awaiting confirmation before Phase 2.
**Date:** 4 November 2026
**Project location:** `C:\Users\Korir\Downloads\shambashield-ai`

---

## 1. One-sentence definition

ShambaShield AI is a multi-agent advisory assistant that converts a 7-day weather forecast
for a Kenyan county into a transparent climate-risk rating, a crop-stage-specific action plan,
and a short farmer-friendly alert in English or Kiswahili.

### What it is not

- Not a yield predictor and not a source of guaranteed outcomes.
- Not a pesticide-dosage or veterinary advisor.
- Not a replacement for extension officers.
- Not a farm-level forecast: the free forecast grid is coarse, and the farmer's exact plot may
  differ. This limitation is shown in the UI.
- Not an SMS/USSD product in v1. Those channels matter, but they are out of scope for the
  hackathon build.

---

## 2. The problem

### 2.1 Who we are serving

A rain-fed smallholder farmer in a Kenyan county growing maize, beans or potatoes, making
decisions such as:

- Should I plant now, or wait?
- Should I top-dress / spray this week, or will rain wash it away?
- Is this dry spell normal, or should I protect seedlings?
- Is the heat going to hurt flowering?
- Should I harvest early because of expected heavy rain?

### 2.2 Why existing tools fall short

1. **Forecasts are not decisions.** A percentage chance of rain does not tell a farmer whether
   to delay spraying or shade seedlings.
2. **Generic advice ignores stage.** The same heat event matters far more at flowering than at
   maturity.
3. **Language and format.** County forecasts and agronomy notes are often in technical English,
   long, and not designed for a phone screen.
4. **Trust.** A confident-sounding chatbot that invents rainfall figures is worse than no advice.
   Farmers need to see the evidence and the date it was retrieved.
5. **Cost and connectivity.** Any solution must work on a low-end smartphone, on intermittent
   connectivity, and at near-zero marginal cost.

### 2.3 The design response

| Problem | Response |
|---|---|
| Forecasts are not decisions | Crop-stage risk rules + a curated action catalog |
| Generic advice | Four specialist agents, each with a narrow mandate |
| Language and format | Bilingual communication agent + mobile-first UI |
| Trust | Deterministic risk engine, numeric-grounding checks, provenance panel |
| Cost and connectivity | Server-side calls, small models, caching, explicit demo/fallback modes |

> **No invented statistics.** This document intentionally contains no impact numbers.
> Any figure used in the Builder Center article must be sourced and cited (e.g. FAOSTAT,
> World Bank, KALRO) and verified before publication.

---

## 3. Why this project is competitive

| Judging criterion | How ShambaShield earns it | Evidence to show |
|---|---|---|
| **Social impact (25%)** | A specific, underserved user; a concrete decision window; bilingual output; affordable actions | Persona, before/after user journey, demo scenario in Kiswahili |
| **Technical execution (25%)** | Five Strands agents; genuine delegation; tool calling; typed handoffs; deterministic guardrails; tests; fallback modes | Architecture diagram, agent trace, test output, failure injection demo |
| **Communication quality (25%)** | Mobile UI with a clear risk banner, evidence chips, 3 actions, provenance and disclaimer; 3-minute demo | Screenshots, article, video script |
| **Originality (25%)** | Kenyan county/crop/stage context; separation of forecast facts from AI interpretation; catalog-bound recommendations; demo resilience | Design-decision section, comparison with a basic chatbot |

### Compared with a basic chatbot

| Basic chatbot | ShambaShield AI |
|---|---|
| Answers from model memory | Reads live forecast data through a tool |
| One prompt, one voice | Five agents with explicit, separate mandates |
| Free-text output | Pydantic contracts between agents and to the UI |
| Can invent rainfall and temperatures | All numbers originate in the forecast; outputs are checked |
| English-only | English and Kiswahili |
| No audit trail | Assessment ID, timestamp, data source, rule trace |
| Breaks when the API breaks | Clearly labelled demo data and rule-based fallback |

---

## 4. System architecture

### 4.1 High-level diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Streamlit UI (mobile-first, 360 px wide and up)                           │
│  County • Location • Crop • Planting stage • Language • [Analyse My Farm]  │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    │  FarmerProfile (validated)
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR AGENT  (Strands Agent, Amazon Bedrock)                       │
│  • plans the assessment          • delegates to four specialists          │
│  • enforces ordering/completeness • resolves severity conflicts            │
│  • emits FinalReport (structured output)                                   │
└──┬────────────────┬──────────────────┬──────────────────┬─────────────────┘
   │ tool call      │ tool call        │ tool call        │ tool call
   ▼                ▼                  ▼                  ▼
┌─────────────┐ ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐
│  WEATHER    │ │  CROP RISK   │ │ ACTION PLANNER │ │ FARMER COMMS     │
│ INTELLIGENCE│ │  ASSESSMENT  │ │                │ │                  │
│   Agent     │ │    Agent     │ │    Agent       │ │    Agent         │
└──────┬──────┘ └──────┬───────┘ └───────┬────────┘ └────────┬─────────┘
       │               │                 │                   │
       ▼               ▼                 ▼                   ▼
┌─────────────┐ ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐
│ Open-Meteo  │ │ Risk engine  │ │ Action catalog │ │ Glossary +       │
│ forecast +  │ │ + crop/stage │ │ (curated YAML) │ │ numeric/output   │
│ normaliser  │ │ knowledge    │ │                │ │ validators       │
└──────┬──────┘ └──────────────┘ └────────────────┘ └──────────────────┘
       │
       ▼
  DynamoDB (history)  ──►  FinalReport  ──►  S3 (optional JSON/PDF report)
                              │
                              ▼
                    UI renders validated report
```

### 4.2 Why Strands

- **Agents are model + tools + prompt.** Each specialist is a real Strands `Agent`, not a prompt
  string hidden in a function.
- **Agents-as-tools** is a first-class multi-agent pattern. The orchestrator delegates through
  tools, so the model decides when to call a specialist and can react to the result.
- **Structured output** (`structured_output_model`) gives us Pydantic-validated handoffs rather
  than parsing prose.
- **Model portability.** Bedrock today; another provider can be swapped without rewriting the
  agent logic.
- **Observability.** Callbacks and OpenTelemetry let us show and record the agent trace.

### 4.3 Why this orchestration style

| Option | Trade-off | Decision |
|---|---|---|
| **Agents as tools** | Genuine delegation; LLM chooses calls; easy to explain | **Chosen** |
| Graph / workflow | Deterministic DAG, but the orchestrator becomes a wiring diagram | Considered; a code-level validator enforces the DAG anyway |
| Swarm | Emergent handoffs, but nondeterministic, harder to bound cost/latency | Rejected for a 3-minute demo |

The orchestrator is instructed to run the four specialists in order. Code then **verifies** that
all four outputs exist and are valid. If the orchestrator skips a step or fails, a recovery path
invokes the missing specialist directly (same agents, same tools) and continues. This is
delegation with a safety net, not four unrelated functions.

### 4.4 Request lifecycle

1. **Validate** the farmer profile (allow-listed county, crop and stage; language `en`/`sw`).
2. **Resolve location**: curated county centroid first, Open-Meteo geocoding second, optional
   manual latitude/longitude for advanced users.
3. **Weather Intelligence Agent**
   - calls `get_forecast` (Open-Meteo, 7 days, hourly + daily),
   - normalises the response into a `WeatherSnapshot`,
   - runs the deterministic hazard detector,
   - returns `WeatherFindings` with per-hazard evidence.
4. **Crop Risk Agent**
   - loads the crop/stage sensitivity profile,
   - calls `assess_crop_risk(snapshot, hazards, crop, stage)`,
   - explains which hazards dominate and what is uncertain,
   - returns `CropRiskAssessment`.
5. **Action Planner Agent**
   - calls `get_action_catalog(hazards, crop, stage)`,
   - selects 3–5 actions, prioritised by urgency, cost and feasibility,
   - returns `ActionPlan` containing catalog IDs only.
6. **Farmer Communication Agent**
   - writes a ≤120-word alert in the chosen language,
   - must use the supplied risk tier and at least one supplied evidence value,
   - returns `FarmerMessage`.
7. **Orchestrator** synthesises the `FinalReport`, resolves conflicts using the rules in §6,
   and hands off to the validator.
8. **Validator** recomputes the risk tier, checks every recommended action ID, and checks that
   numbers in the prose trace back to the snapshot. A failed check triggers one repair attempt,
   then the deterministic fallback.
9. **Persist** the report to DynamoDB (or local JSON in development) and optionally to S3.
10. **Render** the report in the UI with provenance and disclaimer.

---

## 5. Data contracts

All handoffs are Pydantic v2 models in `src/shambashield/contracts.py`. The language model never
writes raw JSON into a database without validation.

```python
# Indicative shapes — final field names are fixed in Phase 2.

RiskLevel = Literal["low", "moderate", "high", "unknown"]
Language  = Literal["en", "sw"]
Crop      = Literal["maize", "beans", "potatoes", "other"]
Stage     = Literal[
    "land_preparation", "planting", "emergence", "vegetative",
    "flowering", "grain_filling", "maturity", "harvest",
]

class FarmerProfile(BaseModel):
    county: str
    location: str | None
    crop: Crop
    stage: Stage
    language: Language
    latitude: float | None = None
    longitude: float | None = None

class DailyForecast(BaseModel):
    date: date
    tmax_c: float
    tmin_c: float
    rain_mm: float
    rain_probability_pct: int | None
    et0_mm: float | None
    wind_max_kmh: float | None

class WeatherSnapshot(BaseModel):
    county: str
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    retrieved_at: datetime
    source: Literal["open-meteo", "demo"]
    days: list[DailyForecast]          # exactly 7
    hourly_rain_mm: list[float] | None

class Hazard(BaseModel):
    kind: Literal["drought", "excess_rain", "heat", "wind", "data_gap"]
    severity: Literal["low", "moderate", "high"]
    window_start: date
    window_end: date
    evidence: list[str]                # templated from measured values
    metrics: dict[str, float]

class WeatherFindings(BaseModel):
    snapshot: WeatherSnapshot
    hazards: list[Hazard]
    summary: str                       # interpretation, no new numbers

class CropRiskAssessment(BaseModel):
    crop: Crop
    stage: Stage
    risk_level: RiskLevel
    drivers: list[str]                 # hazard kinds, ranked
    impact_explanation: str
    uncertainty: list[str]
    stage_sensitivity: str

class RecommendedAction(BaseModel):
    action_id: str                     # must exist in the catalog
    title: str
    why: str
    when: str
    cost_tier: Literal["free", "low", "medium"]
    urgency: Literal["now", "this_week", "monitor"]

class ActionPlan(BaseModel):
    actions: list[RecommendedAction]   # 3–5
    deferred: list[str]                # considered but not prioritised
    assumptions: list[str]

class FarmerMessage(BaseModel):
    language: Language
    headline: str
    body: str                          # ≤120 words
    action_sentence: str
    uncertainty_note: str

class FinalReport(BaseModel):
    assessment_id: str
    generated_at: datetime
    farmer: FarmerProfile
    weather: WeatherSnapshot
    weather_findings: WeatherFindings
    crop_risk: CropRiskAssessment
    action_plan: ActionPlan
    farmer_message: FarmerMessage
    risk_level: RiskLevel
    risk_rationale: list[str]
    data_source: Literal["open-meteo", "demo"]
    degraded_mode: bool
    disclaimer: str
```

**Why typed contracts:** they make agent failures visible, make tests meaningful, and let the UI
render facts separately from narrative. They also prevent a downstream agent from silently
inventing a field.

---

## 6. The deterministic risk engine

### 6.1 Principle

The LLM does **not** decide the risk tier. It explains a tier produced by explicit rules over
measured forecast values. This makes the rating reproducible, testable and defensible.

Initial thresholds below are **engineering defaults**, stored in `config/thresholds.yaml`.
They are informed by general agronomic guidance but must be reviewed by an agronomist before
any real-world pilot. They are not presented as universal scientific constants.

### 6.2 Hazard rules (initial defaults)

| Hazard | Moderate trigger | High trigger | Notes |
|---|---|---|---|
| **Drought / water deficit** | 7-day `Σrain − 0.8·ΣET0 < −25 mm` or ≥5 consecutive days `<1 mm` rain | Same deficit `< −45 mm`, or ≥7 dry days | ET0 supplied by Open-Meteo; crop-stage multiplier below |
| **Excess rain** | 3-day `Σrain ≥ 60 mm` or any day `≥ 40 mm` | 3-day `Σrain ≥ 100 mm` or any day `≥ 70 mm` | Soil infiltration and slope are unknown; flagged as uncertainty |
| **Heat** | `Tmax ≥ 35 °C` on ≥2 days | `Tmax ≥ 38 °C` on ≥3 days | Threshold adjusted by stage sensitivity |
| **Wind** | `wind_max ≥ 30 km/h` on ≥2 days | `wind_max ≥ 45 km/h` | Optional; used for spraying/lodging caution |
| **Data gap** | Missing ET0 or fewer than 5 forecast days | Forecast unavailable | Never report "low" when data is insufficient |

### 6.3 Crop-stage sensitivity

A small, explicit modifier table (not model-generated):

| Stage | Drought | Excess rain | Heat |
|---|---|---|---|
| Emergence / seedling | high | moderate | moderate |
| Vegetative | moderate | moderate | moderate |
| Flowering | high | high | high |
| Grain filling / tuberisation | high | moderate | high |
| Maturity / harvest | low | high | moderate |

The engine uses these sensitivities to **escalate** a hazard by at most one level. It never
de-escalates below the raw weather hazard. This is deliberately conservative.

### 6.4 Aggregation and conflict resolution

1. `final_tier = max(weather hazard tiers, crop risk tier)`.
2. If any specialist reports **high**, the final tier is **high**.
3. If data is insufficient, the tier is **unknown**, not **low**.
4. If the communication agent's text implies a different tier, the text is rejected and
   regenerated.
5. The rationale lists the exact rule and measured values that drove the tier.

This directly addresses "resolve conflicting recommendations": severity cannot be talked down.

### 6.5 Action catalog

`src/shambashield/data/actions.yaml` contains curated actions with:

```yaml
- id: maize_veg_mulch
  hazards: [drought, heat]
  crops: [maize]
  stages: [emergence, vegetative]
  title_en: "Spread crop residue or dry grass between rows"
  title_sw: "Weka matandazo kati ya mistari"
  why: "Reduces evaporation from the soil surface."
  when: "This week, before the dry spell peaks."
  cost_tier: free
  effort: low
  source_note: "General conservation-agriculture practice; verify locally."
```

The planner may rank and phrase actions, but every `action_id` must exist in the catalog.
This blocks plausible-sounding but unaffordable or unsafe inventions (e.g. "buy a generator").

---

## 7. Reliability, responsible AI and failure modes

### 7.1 Failure matrix

| Failure | Behaviour | UI |
|---|---|---|
| Open-Meteo timeout / 5xx | Retry twice with backoff; then load a **labelled** demo fixture | Amber banner: "Using demonstration data — not a live forecast" |
| Geocoding returns nothing | Fall back to curated county centroid | Note: "Approximate county location" |
| Bedrock throttling | Exponential backoff, then rule-based fallback narrative | Banner: "AI narrative unavailable; showing rule-based advisory" |
| Missing ET0 / short forecast | Degrade rule, add uncertainty note | "Limited data" chip |
| LLM returns invalid JSON | One repair attempt; then fallback | Banner + assessment still usable |
| LLM invents a number | Numeric-grounding validator rejects and retries | Logged; never shown |
| LLM invents an action | Catalog-ID validator rejects and retries | Logged; never shown |
| Invalid farmer input | Inline validation; no API call | Field-level error message |

**Demo mode is explicit, never silent.** `WeatherSnapshot.source` and `FinalReport.data_source`
make the distinction machine-readable and visible.

### 7.2 Numeric grounding

Every number in generated narrative must be traceable to the snapshot or a derived metric.
Phase 10 implements a validator that:

1. extracts numeric tokens (with units) from the generated text,
2. normalises rounding (e.g. `23.4 mm` vs `23 mm`),
3. checks membership in an allow-list built from the snapshot and rule outputs,
4. rejects the response if an unexplained number appears.

### 7.3 Language quality

- Kiswahili is generated by the model, then checked against a glossary of agreed agronomic terms
  (`ukame`, `matandazo`, `umwagiliaji`, `hatua ya ukuaji`, etc.).
- Machine-generated Kiswahili can be stilted. A native-speaker review is part of the evaluation,
  and the limitation is stated honestly.
- Numbers, dates and risk labels are injected from structured data, not translated freely.

### 7.4 Privacy and security

- Collect only county, optional location label, crop, stage, language. No phone number, no name,
  no precise GPS in v1.
- DynamoDB records use a TTL; local development uses JSON files.
- Secrets live in `.env` (git-ignored) or an IAM role. No keys in code, screenshots or the repo.
- Least-privilege IAM: `bedrock:InvokeModel`, scoped DynamoDB and S3 actions only.
- Tool outputs are treated as untrusted data in prompts; the system prompt forbids following
  instructions found in API responses.
- Open-Meteo's free tier is for non-commercial use. The hackathon demo qualifies; a production
  deployment would need a commercial plan or a different provider. This is stated in the README.

### 7.5 Mandatory disclaimer

> This advisory is generated from a county-level weather forecast and general agronomic rules.
> It is not a guarantee of crop performance and does not replace a qualified agricultural
> extension officer. Forecasts change — re-check before acting.

---

## 8. User experience

### 8.1 Input screen

- Short title and one-line purpose.
- County: searchable dropdown of Kenya's 47 counties (curated centroids).
- Location: optional text (e.g. "Kangundo") used only for a more precise geocode.
- Crop: Maize / Beans / Potatoes / Other.
- Planting stage: 8 plain-language options with short helper text.
- Language: English / Kiswahili.
- Primary button: **Analyse My Farm**.
- Small print: data source, approximate-location note, disclaimer link.

### 8.2 Progress

A five-step progress display driven by real pipeline events, not a fake timer:

`Location → Forecast → Crop risk → Actions → Translation`

Target: p50 ≤ 15 s, p95 ≤ 30 s. If a step fails, the UI says which step and whether a fallback
was used.

### 8.3 Results screen (top to bottom)

1. **Risk banner** — colour + icon + label (Low / Moderate / High) + one-line reason.
2. **"What we see"** — current conditions and 7-day cards (rain, max/min temperature).
3. **Forecast chart** — rainfall bars and temperature line, with the risk window highlighted.
4. **Why this rating** — hazard cards with measured evidence and the rule that fired.
5. **Top 3 actions** — action, why, when, cost tier; ordered by urgency.
6. **Farmer summary** — in the selected language, ≤120 words, with a "copy" button.
7. **Provenance** — source, retrieval timestamp, coordinates, assessment ID, data mode.
8. **Uncertainty & disclaimer** — what could change and what the tool cannot know.
9. **Feedback** — "Was this useful?" (local only in v1).

### 8.4 Mobile constraints

- Single column; body text ≥16 px; tap targets ≥44 px.
- Charts responsive, no hover-only information.
- No horizontal scrolling at 360 px.
- Works with browser zoom at 200%.

### 8.5 Example scenario

**Input:** Machakos County, Maize, Vegetative growth, Kiswahili.

**Expected output shape:**
- Risk: High (example: 7-day deficit < −45 mm plus 3 days ≥ 36 °C).
- Evidence: cumulative rainfall, ET0 deficit, heat days — all from the snapshot.
- Impact: water stress during vegetative growth reduces leaf expansion and vigour.
- Actions: mulch; prioritise any available water for the most vulnerable block; delay
  fertiliser application until rain is likely.
- Kiswahili summary: short, direct, with the same numbers.
- Banner and footer clearly state forecast date and that the advice is advisory.

The exact tier depends on the live forecast; the demo must never hard-code a "High" result.

---

## 9. Repository structure (target)

```
shambashield-ai/
├─ app.py                          # Streamlit entry point
├─ pyproject.toml
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ README.md
├─ config/
│  ├─ thresholds.yaml              # risk rules (reviewable, versioned)
│  └─ settings.yaml
├─ docs/
│  ├─ PHASE1_ARCHITECTURE.md
│  └─ EVALUATION.md
├─ src/shambashield/
│  ├─ __init__.py
│  ├─ config.py                    # env + settings loading
│  ├─ logging_setup.py             # structured logs, request IDs
│  ├─ contracts.py                 # Pydantic models
│  ├─ orchestrator.py              # Strands orchestrator + delegation
│  ├─ pipeline.py                  # validation, fallback, persistence
│  ├─ agents/
│  │  ├─ weather.py
│  │  ├─ crop_risk.py
│  │  ├─ action_planner.py
│  │  └─ communication.py
│  ├─ tools/
│  │  ├─ open_meteo.py             # forecast + geocoding clients
│  │  ├─ risk_rules.py             # deterministic engine
│  │  ├─ action_catalog.py
│  │  └─ validators.py             # grounding + catalog checks
│  ├─ data/
│  │  ├─ counties.yaml             # 47 counties + centroids
│  │  ├─ crops.yaml                # stage sensitivities
│  │  ├─ actions.yaml              # curated action catalog
│  │  └─ demo_forecasts/           # labelled fixtures
│  ├─ storage/
│  │  ├─ repository.py             # interface
│  │  ├─ local_json.py             # dev fallback
│  │  ├─ dynamodb.py               # optional AWS
│  │  └─ s3_reports.py             # optional AWS
│  └─ ui/
│     ├─ components.py
│     └─ charts.py
└─ tests/
   ├─ fixtures/
   ├─ test_contracts.py
   ├─ test_risk_rules.py
   ├─ test_open_meteo.py
   ├─ test_action_catalog.py
   ├─ test_validators.py
   ├─ test_pipeline.py
   └─ test_scenarios.py
```

---

## 10. Evaluation framework

### 10.1 Test scenarios (fixed forecast fixtures)

| # | County | Crop | Stage | Injected condition | Expected tier |
|---|---|---|---|---|---|
| 1 | Machakos | Maize | Vegetative | Severe deficit + heat | High |
| 2 | Kisumu | Beans | Flowering | 3-day heavy rain | High |
| 3 | Nakuru | Potatoes | Tuberisation | Heat spike | High |
| 4 | Garissa | Maize | Emergence | Long dry spell | High |
| 5 | Trans Nzoia | Maize | Grain filling | Moderate rain, mild temps | Low/Moderate |
| 6 | Nyeri | Beans | Vegetative | Normal rainfall | Low |
| 7 | Any | Any | Any | Missing forecast | Unknown + demo banner |
| 8 | Any | Any | Any | Bedrock timeout | Fallback narrative |

Fixtures are synthetic but realistic, and labelled as synthetic. They are not presented as
observed weather.

### 10.2 Measurable indicators

| Dimension | Metric | Target | Method |
|---|---|---|---|
| Risk correctness | Tier agreement with expert-labelled fixtures | ≥ 6/7 | Automated |
| Evidence grounding | Narrative numbers traceable to data | 100% | Automated validator |
| Action safety | Recommended IDs present in catalog | 100% | Automated |
| Action affordability | No medium-cost action when a free one exists | 100% | Rule check |
| Relevance | Mean reviewer score | ≥ 4/5 | Rubric, 2 reviewers |
| Kiswahili clarity | Native-speaker score | ≥ 4/5 | Rubric |
| Latency | p50 / p95 | ≤ 15 s / ≤ 30 s | Timed runs |
| Cost | Per assessment | ≤ US$0.03 | Token accounting |
| Completion | Scenarios completing without crash | 8/8 | Automated |
| Failure handling | Injected failures handled with correct banner | 3/3 | Fault injection |
| Accessibility | Usable at 360 px and 200% zoom | Pass | Manual checklist |

### 10.3 What we will not claim

- No "X% yield increase" or "reached N farmers" claims without measured evidence.
- No statement that the advice is agronomically validated until an extension officer signs off.
- No claim that county-level forecast equals farm-level conditions.

---

## 11. Key risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Bedrock model access not enabled in the chosen region | Blocks all agents | Phase 2 verifies access before code; fallback model list |
| Agent latency too high for demo | Poor UX | Small models, prompt discipline, 7-day data only, progress UI, caching |
| LLM loses structured data between steps | Wrong report | Typed JSON handoffs, validators, deterministic fallback |
| Kiswahili quality | Trust | Glossary, native review, short templated sentences |
| Forecast API down during judging | Demo failure | Pre-recorded fixtures + explicit demo mode + video backup |
| Scope creep (SMS, maps, PDF) | Nothing finished | Phase gates; PDF and SMS explicitly out of v1 |
| Secrets leaked | Security incident | `.env`, `.gitignore`, secret scan before publishing |
| Open-Meteo licence | Compliance | Non-commercial hackathon use acknowledged; production plan noted |

---

## 12. Phase plan

| Phase | Deliverable | Gate |
|---|---|---|
| 1 | This document, README | Your confirmation |
| 2 | Python env, Strands + Bedrock smoke test, repo skeleton | One agent answers via Bedrock |
| 3 | Weather Intelligence Agent + Open-Meteo tool | Live forecast for Machakos |
| 4 | Crop Risk Agent + rules engine | Fixture-based tier tests pass |
| 5 | Action Planner + catalog | Catalog-bound plan for 3 crops |
| 6 | Communication Agent (EN/SW) | 120-word output, numbers grounded |
| 7 | Orchestrator + delegation + conflict resolution | Full trace of 5 agents |
| 8 | API hardening: retries, caching, demo mode | Injected failures handled |
| 9 | Streamlit UI + charts | Mobile layout at 360 px |
| 10 | Tests, evaluation, logging | Targets in §10.2 met or explained |
| 11 | DynamoDB/S3 + deployment (if feasible) | History persists; app reachable |
| 12 | GitHub, article, 3-minute video | Public repo + links |

Each phase ends with a runnable check. We do not start the next phase until it passes.

---

## 13. Phase 2 prerequisites (please have these ready)

1. **AWS account** with billing enabled.
2. **Amazon Bedrock model access** in one region. Recommended: `us-east-1` for the widest
   model selection; latency from Kenya is acceptable for this workload.
3. **AWS credentials** for local development (SSO or a scoped IAM user). The AWS CLI is not
   currently installed on this machine — Phase 2 will install/configure it.
4. **Python 3.13** is installed (`py` launcher). Strands supports 3.10+; if a dependency
   disagrees, we will add Python 3.12 via `pyenv-win` or the official installer.
5. **Git** is installed.
6. A decision on the model: a small, fast model for specialists and a stronger model for the
   orchestrator, or one model for everything (simpler, slightly less optimal). We will verify
   available IDs with `aws bedrock list-foundation-models` before choosing.

### Open decisions for you

- **Region:** `us-east-1` (recommended) or another region?
- **AWS storage:** enable DynamoDB + S3 in Phase 11, or keep local JSON only and present AWS
  storage as an optional extension? (Recommendation: build the local repository interface in
  Phase 2, add DynamoDB in Phase 11 only if time allows.)
- **Demo data:** should the app ship with a "Load demo scenario" control for offline judging?
  (Recommendation: yes, clearly labelled.)

---

## 14. Phase 1 acceptance checklist

- [x] Problem and target user defined.
- [x] Scope and non-goals defined.
- [x] Five-agent architecture and delegation pattern chosen.
- [x] Typed data contracts sketched.
- [x] Deterministic risk rules and conflict resolution defined.
- [x] Responsible-AI and failure behaviour defined.
- [x] UX flow and mobile constraints defined.
- [x] Repository structure defined.
- [x] Evaluation framework with measurable targets defined.
- [x] Phase plan and Phase 2 prerequisites listed.

**Next:** confirm Phase 1 (and answer the three open decisions), then we begin Phase 2.
