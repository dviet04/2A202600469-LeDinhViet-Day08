#!/usr/bin/env python3
"""
Đánh giá retrieval đơn giản — before/after khi pipeline đổi dữ liệu embed.

Không bắt buộc LLM: chỉ kiểm tra top-k chunk có chứa keyword kỳ vọng hay không
(tiếp nối tinh thần Day 08/09 nhưng tập trung data layer).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

# =========================
# 🔹 Utility: Load questions
# =========================
def load_questions(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"questions not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

# =========================
# 🔹 Setup Chroma collection
# =========================
def load_collection():
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("Install: pip install chromadb sentence-transformers", file=sys.stderr)
        sys.exit(1)

    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    collection_name = os.environ.get("CHROMA_COLLECTION", "day10_kb")
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=db_path)
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)

    try:
        return client.get_collection(name=collection_name, embedding_function=emb)
    except Exception as e:
        print(f"Collection error: {e}", file=sys.stderr)
        sys.exit(2)


# =========================
# 🔹 Evaluate ONE question
# =========================
def evaluate_single_question(col, q: Dict[str, Any], top_k: int) -> Dict[str, Any]:
    text = q["question"]

    res = col.query(query_texts=[text], n_results=top_k)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    # Top-1 info
    top_doc = (metas[0] or {}).get("doc_id", "") if metas else ""
    preview = (docs[0] or "")[:180].replace("\n", " ") if docs else ""

    # Merge top-k content
    blob = " ".join(docs).lower()

    # Expected / forbidden logic
    must_any = [x.lower() for x in q.get("must_contain_any", [])]
    forbidden = [x.lower() for x in q.get("must_not_contain", [])]

    ok_any = any(m in blob for m in must_any) if must_any else True
    bad_forb = any(m in blob for m in forbidden) if forbidden else False

    # Top-1 doc match
    want_top1 = (q.get("expect_top1_doc_id") or "").strip()
    top1_expected = ""
    if want_top1:
        top1_expected = "yes" if top_doc == want_top1 else "no"

    return {
        "question_id": q.get("id", ""),
        "question": text,
        "top1_doc_id": top_doc,
        "top1_preview": preview,
        "contains_expected": "yes" if ok_any else "no",
        "hits_forbidden": "yes" if bad_forb else "no",
        "top1_doc_expected": top1_expected,
    }

# =========================
# 🔹 Aggregate metrics
# =========================
def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)

    correct = sum(1 for r in results if r["contains_expected"] == "yes")
    forbidden = sum(1 for r in results if r["hits_forbidden"] == "yes")
    top1_match = sum(1 for r in results if r["top1_doc_expected"] == "yes")

    return {
        "total_questions": total,
        "accuracy_contains_expected": round(correct / total, 3) if total else 0,
        "forbidden_rate": round(forbidden / total, 3) if total else 0,
        "top1_match_rate": round(top1_match / total, 3) if total else 0,
    }

# =========================
# 🔹 Save CSV
# =========================
def write_csv(path: Path, rows: List[Dict[str, Any]], top_k: int):
    fieldnames = [
        "question_id",
        "question",
        "top1_doc_id",
        "top1_preview",
        "contains_expected",
        "hits_forbidden",
        "top1_doc_expected",
        "top_k_used",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in rows:
            r["top_k_used"] = top_k
            writer.writerow(r)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        default=str(ROOT / "data" / "test_questions.json"),
        help="JSON danh sách câu hỏi golden (retrieval)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "eval" / "before_after_eval.csv"),
        help="CSV kết quả",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("Install: pip install chromadb sentence-transformers", file=sys.stderr)
        return 1

    qpath = Path(args.questions)
    if not qpath.is_file():
        print(f"questions not found: {qpath}", file=sys.stderr)
        return 1

    questions = json.loads(qpath.read_text(encoding="utf-8"))
    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    collection_name = os.environ.get("CHROMA_COLLECTION", "day10_kb")
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=db_path)
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    try:
        col = client.get_collection(name=collection_name, embedding_function=emb)
    except Exception as e:
        print(f"Collection error: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "question_id",
        "question",
        "top1_doc_id",
        "top1_preview",
        "contains_expected",
        "hits_forbidden",
        "top1_doc_expected",
        "top_k_used",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fcsv:
        w = csv.DictWriter(fcsv, fieldnames=fieldnames)
        w.writeheader()
        for q in questions:
            text = q["question"]
            res = col.query(query_texts=[text], n_results=args.top_k)
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            top_doc = (metas[0] or {}).get("doc_id", "") if metas else ""
            preview = (docs[0] or "")[:180].replace("\n", " ") if docs else ""
            blob = " ".join(docs).lower()
            must_any = [x.lower() for x in q.get("must_contain_any", [])]
            forbidden = [x.lower() for x in q.get("must_not_contain", [])]
            ok_any = any(m in blob for m in must_any) if must_any else True
            bad_forb = any(m in blob for m in forbidden) if forbidden else False
            want_top1 = (q.get("expect_top1_doc_id") or "").strip()
            top1_expected = ""
            if want_top1:
                top1_expected = "yes" if top_doc == want_top1 else "no"
            w.writerow(
                {
                    "question_id": q.get("id", ""),
                    "question": text,
                    "top1_doc_id": top_doc,
                    "top1_preview": preview,
                    "contains_expected": "yes" if ok_any else "no",
                    "hits_forbidden": "yes" if bad_forb else "no",
                    "top1_doc_expected": top1_expected,
                    "top_k_used": args.top_k,
                }
            )

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
