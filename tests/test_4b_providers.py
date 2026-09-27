"""Stage 4B tests (fast: stub transports + artifact consistency, no model calls)."""
import json
from pathlib import Path

from app.pipeline.ai_router import AITask, Router
from app.pipeline.contracts import LLMNormalizationResult, RequirementCandidate
from evaluation.stage4b import providers as P
from evaluation.stage4b import run_4b

OUT = Path(run_4b.__file__).parent


def _cand(text="The 220kV GIS transformer must be installed and tested."):
    return RequirementCandidate(candidate_id="c1", parent_chunk_id="p",
                                source_document="D.pdf", page=1, source_text=text,
                                span=[0, len(text)],
                                deterministic_signal_categories=["TECHNICAL"])


def _stub_transport(payload):
    def _t(candidate):
        return payload
    return _t


class _StubProvider(P._OllamaMinimalProvider):
    provider_name = "stub"
    ollama_model = "stub-model"

    def __init__(self, payload):
        super().__init__()
        self._payload = payload

    def health_check(self):
        return True, "stub"

    def normalize_requirement(self, candidate):
        # bypass transport, keep shared parsing/whitelisting semantics
        from evaluation.stage3h.single_req_tasks import parse_single_requirement
        req, status = parse_single_requirement(self._payload)
        if status != "ok" or not req:
            return None, status, 0.01, self._payload
        return LLMNormalizationResult(summary=req["summary"], category=req["category"],
                                      mandatory=req.get("mandatory"),
                                      applicable_entity=req.get("applicable_entity")), "ok", 0.01, self._payload


def test_all_provider_classes_registered_and_shaped():
    assert set(P.PROVIDER_CLASSES) == {"qwen25", "qwen3", "gemma", "phi", "gemini"}
    for tag, cls in P.PROVIDER_CLASSES.items():
        prov = cls()
        assert prov.model_name
        assert prov.provider_name
        ok_caps = prov.capabilities()
        assert ok_caps and ok_caps[0].task == AITask.REQUIREMENT_NORMALIZATION.value
        assert ok_caps[0].confidence == "none"


def test_providers_return_same_schema_no_provenance():
    raw = json.dumps({"requirements": [{"summary": "Install GIS", "category": "TECHNICAL",
                                        "mandatory": None, "applicable_entity": None,
                                        "candidate_id": "FORGED", "source_document": "X.pdf"}]})
    res, status, _, _ = _StubProvider(raw).normalize_requirement(_cand())
    assert status == "ok"
    assert set(res.to_dict()) == {"summary", "category", "mandatory", "applicable_entity"}


def test_unavailable_provider_handling():
    g = P.GeminiProvider()
    ok, msg = g.health_check()
    assert ok is False and "NOT_CONFIGURED" in msg
    res, status, lat, _ = g.normalize_requirement(_cand())
    assert res is None and status == "provider_not_configured" and lat == 0.0
    from app.pipeline.contracts import NOT_CONFIGURED
    r = Router()
    assert r.route(AITask.RECONCILIATION) is NOT_CONFIGURED
    assert r.route(AITask.REQUIREMENT_NORMALIZATION) is NOT_CONFIGURED  # empty router: nothing wired


def test_router_delegation_no_model_logic():
    import inspect
    src = inspect.getsource(Router.route)
    for token in ("qwen", "gemma", "phi", "gemini", "ollama"):
        assert token not in src.lower()


def test_manifest_consistency_and_fixture_identity():
    manifest = json.loads((OUT / "benchmark_manifest.json").read_text(encoding="utf-8"))
    assert manifest["temperature"] == 0 and manifest["timeout_s"] == 90
    assert manifest["contract"] == "minimal-1"
    for ds, info in manifest["datasets"].items():
        cands, _ = run_4b._load(OUT.parents[1] / "evaluation" /
                                ("stage3i/generated_candidates.json" if ds == "primary"
                                 else "stage3k/representative_candidates_3k.json"))
        assert run_4b.fixture_sha(cands) == info["fixture_sha"]
        assert info["n"] == len(cands)


def test_same_candidates_across_models():
    primaries = {}
    for tag in ("qwen25", "qwen3", "gemma", "phi"):
        recs = [json.loads(l) for l in
                (OUT / f"{tag}_primary_raw.jsonl").read_text(encoding="utf-8").splitlines()]
        primaries[tag] = [(r["candidate_id"], r["source_text"]) for r in recs]
    base = primaries["qwen25"]
    for tag, rows in primaries.items():
        assert rows == base, f"candidate mismatch for {tag}"
    shas = set()
    for tag in primaries:
        for line in (OUT / f"{tag}_primary_raw.jsonl").read_text(encoding="utf-8").splitlines():
            shas.add(json.loads(line)["fixture_sha"])
    assert len(shas) == 1


def test_no_model_specific_prompt_mutation():
    import inspect
    src = inspect.getsource(P._OllamaMinimalProvider.normalize_requirement)
    assert "MINIMAL_CONTRACT_SYSTEM" in src and "build_user_message" in src
    # shared method carries no model-name literals; per-model choice lives in
    # subclass attributes (ollama_model/think), recorded in the manifest
    for token in ("qwen", "gemma", "phi", "gemini"):
        assert token not in src.lower()


def test_production_default_unchanged():
    import app.processing as proc
    assert proc.LLM_MODEL == "qwen2.5:3b"
    assert proc.PIPELINE_VERSION == "1.0"
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
