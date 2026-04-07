import os
import sys
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, LLMContextPrecisionWithoutReference
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

# Ensure project root is importable when running:
# python backend/evals/run_eval.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.graph.nodes import compliance_audit_node


load_dotenv(override=True)

DATA_PATH = PROJECT_ROOT / "backend/evals/data/eval_set.jsonl"
REPORTS_DIR = PROJECT_ROOT / "backend/evals/reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_cases(path: Path) -> list[dict]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for key in ["id", "question", "transcript", "ocr_text"]:
                if key not in row:
                    raise ValueError(f"Line {i} missing key: {key}")
            cases.append(row)
    return cases


def run_one_case(case: dict) -> dict:
    state = {
        "video_metadata": {},
        "transcript": case["transcript"],
        "ocr_text": case.get("ocr_text", []),
    }

    t0 = time.perf_counter()
    pred = compliance_audit_node(state)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    response = pred.get("final_report", "") or ""
    retrieved_contexts = pred.get("retrieved_contexts", []) or []
    status = pred.get("final_status", "FAIL")

    return {
        "id": case["id"],
        "question": case["question"],
        "status": status,
        "response": response,
        "retrieved_contexts": retrieved_contexts,
        "latency_ms": latency_ms,
        "error": pred.get("errors", []),
    }


def build_ragas_dataset(case_results: list[dict]) -> Dataset:
    rows = []
    for r in case_results:
        rows.append(
            {
                "user_input": r["question"],
                "response": r["response"],
                "retrieved_contexts": r["retrieved_contexts"],
            }
        )
    return Dataset.from_list(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="run", help="label for report filename")
    parser.add_argument("--max-cases", type=int, default=0, help="limit number of cases (0 = all)")
    args = parser.parse_args()

    cases = load_cases(DATA_PATH)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    if not cases:
        raise ValueError(f"No cases found in {DATA_PATH}")

    case_results = []
    for case in cases:
        try:
            case_results.append(run_one_case(case))
        except Exception as e:
            case_results.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "status": "FAIL",
                    "response": "",
                    "retrieved_contexts": [],
                    "latency_ms": None,
                    "error": [str(e)],
                }
            )

    latencies = [r["latency_ms"] for r in case_results if r["latency_ms"] is not None]
    avg_latency_ms = mean(latencies) if latencies else None
    error_rate = mean([1 if r["error"] else 0 for r in case_results]) if case_results else 1.0

    ragas_ds = build_ragas_dataset(case_results)

    # Evaluator models
    chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    embed_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    if not chat_deployment:
        raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT is not set")

    eval_llm = AzureChatOpenAI(
        azure_deployment=chat_deployment,
        openai_api_version=api_version,
        temperature=0.0,
    )
    eval_embeddings = AzureOpenAIEmbeddings(
        azure_deployment=embed_deployment,
        openai_api_version=api_version,
    )

    ragas_result = evaluate(
        dataset=ragas_ds,
        metrics=[
            faithfulness,
            answer_relevancy,
            LLMContextPrecisionWithoutReference(),
        ],
        llm=eval_llm,
        embeddings=eval_embeddings,
        raise_exceptions=False,
        show_progress=True,
    )

    ragas_scores = ragas_result.to_pandas().mean(numeric_only=True).to_dict()
    # JSON-safe cleanup for NaN/inf metric values
    ragas_scores = {
        k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
        for k, v in ragas_scores.items()
    }

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tag": args.tag,
        "num_cases": len(case_results),
        "avg_latency_ms": avg_latency_ms,
        "error_rate": error_rate,
        "ragas_scores": ragas_scores,
        "cases": case_results,
    }

    out_file = REPORTS_DIR / f"eval_{args.tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "report_file": str(out_file),
            "num_cases": summary["num_cases"],
            "avg_latency_ms": summary["avg_latency_ms"],
            "error_rate": summary["error_rate"],
            "ragas_scores": summary["ragas_scores"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
