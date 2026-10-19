"""Avaliação local: uv run python -m ragsearch.evaluate."""

import json
from pathlib import Path

from ragsearch.retrieval import SearchIndex, read_document

ROOT = Path(__file__).resolve().parents[1]


def evaluate() -> dict:
    documents = []
    for path in sorted((ROOT / "examples" / "documents").glob("*.md")):
        documents.extend(read_document(path.name, path.read_bytes()))
    index = SearchIndex(documents)
    cases = json.loads((ROOT / "examples" / "evaluation.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        hits = index.search(case["question"], top_k=1)
        if case["source"] is None:
            passed = not hits
        else:
            passed = bool(
                hits
                and hits[0].chunk.source == case["source"]
                and case["evidence"] in hits[0].chunk.text
            )
        results.append({"question": case["question"], "passed": passed})
    relevant = [result for case, result in zip(cases, results) if case["source"] is not None]
    return {
        "dataset": "Exemplos sintéticos; não mede qualidade em documentos reais ou geração.",
        "recall_at_1_with_evidence": sum(r["passed"] for r in relevant) / len(relevant),
        "passed": sum(result["passed"] for result in results),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
