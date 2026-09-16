# Matcher Provider Guide — TenderMind — Offline Abstraction

**Status:** `OFFLINE` — No external API calls, no cost, no network in this task. Azure remains F0, OpenAI not called.

## 1. Where the Future Paid LLM Provider Plugs In

**Interface:** `app/matchers/base.py:BaseMatcher` — any provider must implement `match(MatcherInput) -> MatcherOutput`

**Current providers:**
- `app/matchers/mock_matcher.py:MockMatcher` — **deterministic, offline, for tests** — no API, no cost, used in `tests/test_matcher_offline.py`
- `app/matchers/openai_matcher.py:OpenAIMatcher` — **future paid provider, NOT called in offline tests** — requires `OPENAI_API_KEY=sk-proj-...` or `AZURE_OPENAI_*` and `TENDERMIND_ENABLE_LLM=1` to enable (cost guardrail). Not instantiated in this task.

**Plug-in point:**
```python
# For offline tests (this task, no cost):
from app.matchers import MockMatcher
matcher = MockMatcher()
out = matcher.safe_match(inp)  # inp: MatcherInput

# For future real LLM (when you explicitly want to incur cost):
import os
os.environ["TENDERMIND_ENABLE_LLM"] = "1"  # Required to unlock OpenAIMatcher
from app.matchers import OpenAIMatcher
matcher = OpenAIMatcher(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o")
# Or Azure OpenAI:
# matcher = OpenAIMatcher(api_key=os.environ["AZURE_OPENAI_API_KEY"], endpoint=os.environ["AZURE_OPENAI_ENDPOINT"])
out = matcher.safe_match(inp)  # Will call LLM, incur ~$0.0005 per pair
```

**File to change for real LLM:** No code change needed — just configure env vars and set `TENDERMIND_ENABLE_LLM=1`. The benchmark adapter `evaluation/matcher_benchmark.py:run_benchmark()` already accepts any `BaseMatcher`.

**Where LLM is NOT allowed:** `app/engines/decision.py:1` and `app/engines/status.py:1` — final `BID/REVIEW/NO_BID` remains deterministic (see §3).

## 2. Exact API Contract

**Input (`MatcherInput`):**
```python
{
  "requirement_id": "REQ-A",
  "requirement_text": "First-category membership required...",
  "requirement_category": "LEGAL",
  "requirement_type": "HARD_GATE",
  "mandatory": true,
  "applicable_entity": "GIZA",  # CONSORTIUM | GIZA | HYOSUNG | AMBIGUOUS
  "evidence_id": "E-001",
  "evidence_fact": "Giza Systems First Category certificate valid...",
  "evidence_type": "CERTIFICATE",
  "evidence_applicable_entity": "GIZA",
  "evidence_valid_until": "2025-12-31T00:00:00" or null,
  "evidence_reusable": true,
  "evidence_tender_source": "SA-2018-HV2" or "OTHER-001",
  "current_tender_id": "SA-2018-HV2",
  "source_document": "Giza First Category Certificate.pdf",
  "page_or_section": "Page 1"
}
```

**Output (`MatcherOutput` — strict, validated):**
```json
{
  "support": true,           // true|false|null (null = ambiguous)
  "contradiction": false,    // true if explicit contradiction (e.g., Second vs First)
  "missing_facts": [],       // List of strings if support is false
  "supporting_facts": ["Evidence shows First Category — matches requirement"],
  "contradictory_facts": [],
  "applicability": "PASS",   // PASS|FAIL|REVIEW|MISSING — requirement-level, NOT tender-level
  "confidence": 0.95,        // 0.0-1.0
  "reason": "Strong support: First Category evidence matches REQ-A — PASS with provenance ..."
}
```
**Validation:** `MatcherOutput` is a `pydantic.BaseModel` with `field_validator` for `confidence 0.0-1.0` and `applicability` enum. `BaseMatcher.safe_match()` catches `ValidationError` and returns `REVIEW` with `confidence 0.0` and `reason: "Matcher output validation failed..."` — never raises, never returns `BID`.

## 3. Why Final Decision Remains Deterministic

**Matcher NEVER produces `BID/NO_BID`.** It only produces `PASS/FAIL/REVIEW/MISSING` at the **requirement/evidence** level.

**Final tender decision is deterministic in `app/engines/decision.py:12` `decide()`:**
1. If any `mandatory HARD_GATE` is `FAIL` → `NO_BID` (`HARD_GATE_FAIL`)
2. Else if any `mandatory HARD_GATE` is `MISSING` → `REVIEW` (`MANDATORY_GATE_MISSING`)
3. Else if any `mandatory HARD_GATE` is `REVIEW` → `REVIEW`
4. Else if any `mandatory EXPERIENCE/TECHNICAL/...` is `MISSING/REVIEW` → `REVIEW`
5. Else if any `HIGH` risk → `REVIEW`
6. Else → `BID`

**Hard rules enforced AFTER matcher (in `status.py` and `decision.py`), not by matcher:**
- `MISSING != FAIL` — no evidence → `MISSING_EVIDENCE`, never `FAIL`
- `RISK != NO_BID` — risks always `REVIEW`
- `contradiction` → `FAIL` at requirement level, but `NO_BID` only if that requirement is `mandatory HARD_GATE`
- `ambiguity` (`AMBIGUOUS` or `support=null`) → `REVIEW`
- `wrong tender non-reusable` → `MISSING` (evidence ignored)
- `expired` (`valid_until < now`) → `REVIEW` (not `PASS`)
- `wrong entity` (GIZA vs HYOSUNG) → `MISSING`

**Even if LLM says `support:true` for OEM evidence on `REQ-K` (type-test), the deterministic layer still returns `MISSING` for `REQ-K` because `OEM` does not satisfy `type-test` per `mock_matcher.py` hard rule — LLM cannot bypass.**

## 4. How to Run Offline Tests (No Cost, No Network)

```powershell
cd "C:\Users\EgyTech\Documents\Default Project\TenderMind"
# 1. Install deps (no Azure/LLM needed for offline)
pip install -r requirements.txt

# 2. Run offline matcher tests (11 cases, deterministic, no API)
python tests/test_matcher_offline.py
# Expected: All 11 offline matcher tests passed

# 3. Run full offline suite (including existing)
python tests/test_azure_doc_intel.py
python tests/test_azure_wiring.py
# Note: tests/test_smoke_azure.py requires mock, not real Azure — will pass offline

# 4. Run benchmark adapter smoke (5 pairs, mock, no LLM)
python -c "from evaluation.matcher_benchmark import run_benchmark; from app.matchers import MockMatcher; print(run_benchmark(MockMatcher(), limit=5))"
```

**Do NOT run full 84-pair LLM benchmark without valid key and explicit opt-in:**
```powershell
# This would incur cost — DO NOT run in this cost-guardrailed task:
# $env:TENDERMIND_ENABLE_LLM="1"
# $env:OPENAI_API_KEY="sk-proj-..."  # Must be sk-proj-, not sk-svcacct-
# python evaluation/matcher_benchmark.py  # Would call OpenAI for 84 pairs
```

## 5. Explicit Warning — Real LLM Inference May Incur API Costs

**Cost per tender if you enable real LLM:**
- `21 requirements × 4 evidences = 84` matcher calls
- Each call: ~120 tokens input (requirement + evidence + provenance) + ~80 tokens output (JSON) ≈ 200 tokens
- Total: `84 × 200 ≈ 16,800 tokens` per tender
- `GPT-4o` pricing (2024): ~$5.00 / 1M input + $15.00 / 1M output → **~$0.04–$0.06 per tender** for matching alone
- `Azure OpenAI` similar, plus `Document Intelligence` OCR `~$14/tender` for 1394 pages (`prebuilt-layout` $10/1K)
- **Total tender with Azure OCR + LLM matching: ~$14.04/tender** (per `docs/AI_Evaluation_Run_Sarai_Real_v4.md:1`)

**Guardrail:** `OpenAIMatcher` checks `TENDERMIND_ENABLE_LLM=1` before any API call — without it, `match()` raises `RuntimeError` with safe message (no key logged) and `safe_match()` returns `REVIEW`. Offline tests **never** set this flag, so **zero API calls** in this task.

## 6. What Was NOT Changed (Frozen)

- `frozen acceptance criteria` — `docs/AI_Acceptance_Criteria.md:1` thresholds unchanged (Requirement F1 ≥0.90, etc.)
- `evaluation/sarai_gold_dataset.json` — not modified, not loaded during matcher inference
- `app/engines/decision.py` — deterministic `BID/REVIEW/NO_BID` logic unchanged
- `app/engines/status.py` — hard rules unchanged (added via matcher, not replaced)
- Existing tender/company evidence — `app/seed.py` 21 REQ + 4 E unchanged
- Azure tier — remains **F0** per your COST GUARDRAIL (do NOT switch to S0, do NOT call Azure)

## 7. What Exact Command Will Later Be Needed to Run Real LLM Matching (WITHOUT Running It Now)

**When you explicitly want to incur cost and have valid `sk-proj-...` or `AZURE_OPENAI_*`:**
```powershell
cd "C:\Users\EgyTech\Documents\Default Project\TenderMind"
$env:TENDERMIND_ENABLE_LLM="1"
$env:OPENAI_API_KEY="sk-proj-..."  # Never commit, never log
# OR for Azure OpenAI:
# $env:AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
# $env:AZURE_OPENAI_API_KEY="<key>"
# $env:AZURE_OPENAI_API_VERSION="2024-02-15-preview"

# Run the 84-pair benchmark with real LLM (will call OpenAI 84 times, ~12s, ~$0.04)
python evaluation/matcher_benchmark.py

# Then rerun the real benchmark (after also configuring Azure S0 for OCR):
python evaluation/run_real_benchmark_v4.py
# Expected: matching_macro_f1 ≥0.93, overall PASS (if OCR also S0)
```
**Do NOT run this now — cost guardrail prohibits any network inference in this task.**
