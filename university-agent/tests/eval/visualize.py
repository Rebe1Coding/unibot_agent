"""Визуализация результатов оценки."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
CHARTS_DIR.mkdir(exist_ok=True)


def main():
    scores_path = OUTPUT_DIR / "detailed_scores.json"
    summary_path = OUTPUT_DIR / "summary.json"

    if not scores_path.exists():
        print(f"Файл не найден: {scores_path}")
        print("Сначала запустите run_eval.py")
        sys.exit(1)

    with open(scores_path, encoding="utf-8") as f:
        scores = json.load(f)

    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    _plot_category_bar(summary)
    _plot_score_distribution(scores)
    _plot_radar(summary)
    _plot_per_question_heatmap(scores)
    _plot_score_histogram(scores)
    print(f"Графики сохранены в {CHARTS_DIR}")


def _plot_category_bar(summary: dict):
    """Столбчатая диаграмма: средний балл по категориям."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cats = list(summary["categories"].keys())
    means = [summary["categories"][c]["mean"] for c in cats]

    # Сокращённые названия
    short_names = {
        "Релевантный (RAG)": "RAG",
        "На подумать": "Рассуждения",
        "Не по теме": "Off-topic",
        "Провокационный/Мета": "Мета",
        "Стресс-кейс": "Стресс",
    }
    labels = [short_names.get(c, c) for c in cats]

    colors = ["#2ecc71", "#3498db", "#e74c3c", "#f39c12", "#9b59b6"]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, means, color=colors, edgecolor="white", linewidth=1.2)

    for bar, val in zip(bars, means):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Средний балл (1–5)", fontsize=12)
    ax.set_title("Средний балл агента по категориям", fontsize=14, fontweight="bold")
    ax.axhline(y=3.0, color="gray", linestyle="--", alpha=0.5, label="Порог (3.0)")
    ax.legend(fontsize=10)

    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "01_category_bar.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_score_distribution(scores: list[dict]):
    """Box-plot распределения баллов по категориям."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_cat: dict[str, list[float]] = {}
    for s in scores:
        by_cat.setdefault(s["category"], []).append(s.get("score", 0))

    short_names = {
        "Релевантный (RAG)": "RAG",
        "На подумать": "Рассуждения",
        "Не по теме": "Off-topic",
        "Провокационный/Мета": "Мета",
        "Стресс-кейс": "Стресс",
    }

    cats_order = [
        "Релевантный (RAG)",
        "На подумать",
        "Не по теме",
        "Провокационный/Мета",
        "Стресс-кейс",
    ]
    data = [by_cat.get(c, []) for c in cats_order]
    labels = [short_names.get(c, c) for c in cats_order]

    fig, ax = plt.subplots(figsize=(10, 6))
    bp = ax.boxplot(data, labels=labels, patch_artist=True, showmeans=True)

    colors = ["#2ecc71", "#3498db", "#e74c3c", "#f39c12", "#9b59b6"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    for median in bp["medians"]:
        median.set_color("black")
        median.set_linewidth(2)

    ax.set_ylabel("Балл (1–5)", fontsize=12)
    ax.set_title("Распределение баллов по категориям", fontsize=14, fontweight="bold")
    ax.axhline(y=3.0, color="gray", linestyle="--", alpha=0.5, label="Порог (3.0)")
    ax.legend(fontsize=10)

    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "02_boxplot.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_radar(summary: dict):
    """Радарная диаграмма по категориям."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    cats = list(summary["categories"].keys())
    values = [summary["categories"][c]["mean"] for c in cats]

    short_names = {
        "Релевантный (RAG)": "RAG",
        "На подумать": "Рассуждения",
        "Не по теме": "Off-topic",
        "Провокационный/Мета": "Мета",
        "Стресс-кейс": "Стресс",
    }
    labels = [short_names.get(c, c) for c in cats]

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.fill(angles, values, alpha=0.25, color="#3498db")
    ax.plot(angles, values, color="#3498db", linewidth=2, marker="o", markersize=8)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=9)
    ax.set_title("Профиль качества агента (радар)", fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "03_radar.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_per_question_heatmap(scores: list[dict]):
    """Тепловая карта: баллы по каждому вопросу."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    cats_order = [
        "Релевантный (RAG)",
        "На подумать",
        "Не по теме",
        "Провокационный/Мета",
        "Стресс-кейс",
    ]
    short_names = {
        "Релевантный (RAG)": "RAG",
        "На подумать": "Рассуждения",
        "Не по теме": "Off-topic",
        "Провокационный/Мета": "Мета",
        "Стресс-кейс": "Стресс",
    }

    max_q = max(len([s for s in scores if s["category"] == c]) for c in cats_order)
    heatmap = np.full((len(cats_order), max_q), np.nan)

    for i, cat in enumerate(cats_order):
        cat_scores = [s["score"] for s in scores if s["category"] == cat]
        for j, val in enumerate(cat_scores):
            heatmap[i, j] = val

    fig, ax = plt.subplots(figsize=(18, 5))

    cmap = plt.cm.RdYlGn
    im = ax.imshow(heatmap, cmap=cmap, aspect="auto", vmin=0, vmax=5)

    ax.set_yticks(range(len(cats_order)))
    ax.set_yticklabels([short_names.get(c, c) for c in cats_order], fontsize=11)
    ax.set_xlabel("Номер вопроса в категории", fontsize=12)
    ax.set_title("Тепловая карта оценок по вопросам", fontsize=14, fontweight="bold")

    # Аннотации
    for i in range(heatmap.shape[0]):
        for j in range(heatmap.shape[1]):
            if not np.isnan(heatmap[i, j]):
                ax.text(
                    j,
                    i,
                    f"{heatmap[i, j]:.1f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="black" if 1.5 < heatmap[i, j] < 4.0 else "white",
                )

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Балл (1–5)", fontsize=11)

    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "04_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_score_histogram(scores: list[dict]):
    """Гистограмма распределения всех баллов."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    all_vals = [s["score"] for s in scores]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(all_vals, bins=10, range=(0, 5), edgecolor="white", color="#3498db", alpha=0.8)
    ax.axvline(
        x=sum(all_vals) / len(all_vals),
        color="#e74c3c",
        linestyle="--",
        linewidth=2,
        label=f'Среднее ({sum(all_vals)/len(all_vals):.2f})',
    )
    ax.axvline(x=3.0, color="gray", linestyle=":", linewidth=1.5, label="Порог (3.0)")
    ax.set_xlabel("Балл (1–5)", fontsize=12)
    ax.set_ylabel("Количество вопросов", fontsize=12)
    ax.set_title("Распределение оценок (все вопросы)", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)

    plt.tight_layout()
    fig.savefig(CHARTS_DIR / "05_histogram.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
