#!/usr/bin/env python3
"""
evaluate_rag.py — Measure RAG quality using Ragas metrics.

Usage:
    python scripts/evaluate_rag.py --backend http://localhost:8000 --output scripts/eval_results/

Requires: pip install ragas  (requirements-dev.txt)
Requires: running KRAI backend
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, faithfulness

DATASET_PATH = Path(__file__).parent / "eval_dataset.json"
DEFAULT_BACKEND = os.getenv("KRAI_BACKEND_URL", "http://localhost:8000")
API_TOKEN = os.getenv("KRAI_API_TOKEN", "")


async def get_answer(client: httpx.AsyncClient, backend: str, question: str, scope_doc_id: str | None) -> str:
    scope = {"document_id": scope_doc_id} if scope_doc_id else None
    payload = {
        "message": question,
        "session_id": f"eval-{hash(question)}",
        "scope": scope,
    }
    headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
    resp = await client.post(f"{backend}/agent/chat", json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    return resp.json()["response"]


async def get_contexts(client: httpx.AsyncClient, backend: str, question: str, scope_doc_id: str | None) -> list[str]:
    payload = {"query": question, "limit": 10}
    if scope_doc_id:
        payload["document_id"] = scope_doc_id
    headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
    resp = await client.post(f"{backend}/search/", json=payload, headers=headers, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results") or data.get("data") or []
    return [r.get("content", r.get("text_chunk", "")) for r in results if r.get("content") or r.get("text_chunk")]


async def collect_samples(backend: str, dataset: list) -> list[dict]:
    samples = []
    async with httpx.AsyncClient() as client:
        for i, entry in enumerate(dataset, 1):
            question = entry["question"]
            ground_truth = entry["ground_truth"]
            scope_doc_id = entry.get("scope_document_id")
            print(f"[{i}/{len(dataset)}] {question[:60]}...", flush=True)
            try:
                answer, contexts = await asyncio.gather(
                    get_answer(client, backend, question, scope_doc_id),
                    get_contexts(client, backend, question, scope_doc_id),
                )
                samples.append(
                    {
                        "question": question,
                        "answer": answer,
                        "contexts": contexts,
                        "ground_truth": ground_truth,
                    }
                )
            except Exception as e:
                print(f"  Warning Failed: {e}", flush=True)
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--output", default=str(Path(__file__).parent / "eval_results"))
    parser.add_argument("--dataset", default=str(DATASET_PATH))
    args = parser.parse_args()

    with open(args.dataset) as f:
        dataset = json.load(f)

    print(f"Collecting {len(dataset)} samples from {args.backend}...")
    samples = asyncio.run(collect_samples(args.backend, dataset))

    if not samples:
        print("No samples collected. Is the backend running?")
        sys.exit(1)

    if len(samples) < len(dataset) * 0.5:
        print(f"⚠ Only {len(samples)}/{len(dataset)} samples collected — aborting evaluation (< 50%).")
        sys.exit(1)

    print(f"\nEvaluating {len(samples)} samples with Ragas...")
    ds = Dataset.from_list(samples)
    result = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])

    print("\n" + "=" * 50)
    print("RAG EVALUATION RESULTS")
    print("=" * 50)
    print(result)

    Path(args.output).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    out_path = Path(args.output) / f"{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "backend": args.backend,
                "sample_count": len(samples),
                "metrics": {k: (float(v) if v == v else None) for k, v in result.items()},
                "samples": samples,
            },
            f,
            indent=2,
        )
    print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
