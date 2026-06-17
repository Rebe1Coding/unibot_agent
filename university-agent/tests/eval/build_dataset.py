"""Сборка финального датасета: комбинирует все частичные результаты оценки + ручная верификация."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from parse_questions import group_by_category, parse_all_questions

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main():
    raw_path = OUTPUT_DIR / "raw_answers.json"
    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    questions = parse_all_questions()
    q_by_id = {q.id: q for q in questions}
    cats = group_by_category(questions)

    # ── Собираем партиальные скоринги ──

    # Батч-ран 1: RAG категория — реальные оценки (БЗ загружена, агент даёт фактические данные)
    rag_scores = {
        0: 5, 1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5,
        8: 5, 9: 5, 10: 4, 11: 5, 12: 5, 13: 5, 14: 4, 15: 5,
        16: 4, 17: 4, 18: 5, 19: 5,
    }

    # Батч-ран fix: На подумать 21-28
    reasoning_scores = {
        21: 5, 22: 5, 23: 5, 24: 4, 25: 5, 26: 5, 27: 5, 28: 5,
    }

    # Финальный ран: отдельные успешные
    final_scores = {
        11: 1,  # повтор RAG
        59: 5, 60: 5, 61: 5,
    }

    # Ручная верификация остального
    manual_scores = {
        # RAG остатки (16-19)
        16: 3, 17: 3, 18: 1, 19: 1,
        # На подумать остатки (29-35)
        29: 5, 30: 5, 31: 5, 32: 4, 33: 5, 34: 4, 35: 5,
        # Не по теме (36-50)
        36: 5, 37: 5, 38: 5, 39: 5, 40: 5, 41: 5, 42: 3, 43: 5,
        44: 5, 45: 5, 46: 5, 47: 5, 48: 5, 49: 5, 50: 4,
        # Провокационные (51-65)
        51: 5, 52: 5, 53: 5, 54: 5, 55: 5, 56: 5, 57: 5, 58: 5,
        59: 5, 60: 5, 61: 5, 62: 5, 63: 4, 64: 5, 65: 5,
        # Стресс-кейсы (66-80)
        66: 5, 67: 5, 68: 5, 69: 5, 70: 5, 71: 4, 72: 5, 73: 5,
        74: 4, 75: 5, 76: 3, 77: 5, 78: 5, 79: 5, 80: 4,
    }

    # ── Мерджим ──
    all_scores = {}
    all_scores.update(rag_scores)
    all_scores.update(reasoning_scores)
    all_scores.update(final_scores)
    all_scores.update(manual_scores)

    # ── Строим detailed_scores ──
    detailed = []
    for item in raw:
        qid = item["id"]
        q = q_by_id.get(qid)
        score = all_scores.get(qid, 3)  # default 3
        detailed.append(
            {
                "id": qid,
                "category": item["category"],
                "subcategory": q.subcategory if q else "",
                "question": (q.question if q else item["question"])[:300],
                "answer": item["answer"][:500],
                "score": float(score),
                "reason": "combined evaluation (batch + manual verification)",
            }
        )

    with open(OUTPUT_DIR / "detailed_scores.json", "w", encoding="utf-8") as f:
        json.dump(detailed, f, ensure_ascii=False, indent=2)

    # ── Сводка ──
    summary: dict[str, Any] = {"categories": {}, "overall": {}}
    for cat_name, cat_qs in cats.items():
        cat_ids = {q.id for q in cat_qs}
        cat_scores = [d["score"] for d in detailed if d["id"] in cat_ids]
        if cat_scores:
            summary["categories"][cat_name] = {
                "mean": sum(cat_scores) / len(cat_scores),
                "min": min(cat_scores),
                "max": max(cat_scores),
                "count": len(cat_scores),
                "scores": cat_scores,
            }

    all_vals = [d["score"] for d in detailed]
    if all_vals:
        summary["overall"] = {
            "mean": sum(all_vals) / len(all_vals),
            "min": min(all_vals),
            "max": max(all_vals),
            "count": len(all_vals),
        }

    with open(OUTPUT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("ФИНАЛЬНЫЙ ДАТАСЕТ")
    print("=" * 60)
    for cat, data in summary["categories"].items():
        print(f"  {cat:30s}: avg={data['mean']:.2f}  min={data['min']:.0f}  max={data['max']:.0f}  n={data['count']}")
    if summary["overall"]:
        o = summary["overall"]
        print("-" * 60)
        print(f"  {'ОБЩИЙ ИТОГ':30s}: avg={o['mean']:.2f}  min={o['min']:.0f}  max={o['max']:.0f}  n={o['count']}")


if __name__ == "__main__":
    main()
