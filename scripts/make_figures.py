"""Draw the figures used in the README and the methodology notes.

Every figure is rebuilt from files in the repository, so the figures always
match the latest results:

    corpus_map.png          the 87 articles by section, annotated or not
    data_funnel.png         from all civil judgments to the study A questions
    atom_example.png        article 6:162 BW split into labelled atoms
    results.png             retrieval scores per system, with 95% intervals
    blind_spots.png         how often each often-cited article is found
    citation_links.png      per section, how many articles have a citation link

Inputs: data/processed/ (statutes, references, case-law citations),
data/annotations/, and outputs/tables/ (written by scripts/build_study_a.py
and scripts/run_baselines.py). Output: outputs/figures/.

Example (from the repo root):

    python scripts/make_figures.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PROCESSED = PROJECT_ROOT / "data" / "processed"
ANNOTATIONS = PROJECT_ROOT / "data" / "annotations"
TABLES = PROJECT_ROOT / "outputs" / "tables"
FIGURES = PROJECT_ROOT / "outputs" / "figures"
INDEX = PROJECT_ROOT / "data" / "raw" / "case_law" / "index.csv"

# Civil judgments with text on rechtspraak.nl, 2000-2026, as indexed by
# scripts/fetch_caselaw.py; used when the (git-ignored) index is not present
INDEXED_JUDGMENTS = 291_252

# Okabe-Ito colours: distinguishable with colour-vision deficiencies
SECTIONS = {
    "/Boek7/Titeldeel7/Afdeling5": ("WGBO: medical treatment", "7:446–468", "#0072B2"),
    "/Boek6/Titeldeel1/Afdeling9": ("Non-performance", "6:74–94", "#E69F00"),
    "/Boek6/Titeldeel1/Afdeling10": ("Damages", "6:95–110", "#009E73"),
    "/Boek6/Titeldeel3/Afdeling1": ("Tort, general", "6:162–168", "#D55E00"),
    "/Boek6/Titeldeel3/Afdeling2": ("Liability for persons, things", "6:169–184", "#CC79A7"),
}
INK, MUTED, GRID = "#1f2a33", "#6b7780", "#e3e7ea"
PRE, POST = "#0072B2", "#D55E00"

SYSTEMS = {  # run_baselines.py name -> label, in the order they build on each other
    "random": "Random order",
    "bm25": "BM25 (keywords)",
    "dense": "Dense (BGE-M3)",
    "hybrid": "BM25 + dense, z-score fusion",
    "hybrid_rrf": "BM25 + dense, rank fusion",
    "graph_cite": "+ spreading along citations",
    "graph_tree": "+ spreading within sections",
    "graph_both": "+ spreading along both",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.titleweight": "bold",
    "axes.titlesize": 11,
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": INK,
    "text.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})


def _articles() -> list[dict]:
    with (PROCESSED / "statutes.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def _section(article: dict) -> str:
    """The afdeling an article belongs to, e.g. "/Boek6/Titeldeel1/Afdeling9".

    Some afdelingen are split further into paragrafen (6:74-94); those
    articles still belong to their afdeling.
    """
    return re.match(r".*?/Afdeling\d+", article["path"]).group(0)


def _annotated() -> set[str]:
    return {p.stem.replace("_", ":") for p in ANNOTATIONS.glob("[67]_*.json")}


def _save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / name)
    plt.close(fig)
    print(f"  {name}")


# -------------------------------------------------------------- corpus map

def corpus_map() -> None:
    arts, annotated = _articles(), _annotated()
    rows = []
    for path, (name, span, colour) in SECTIONS.items():
        ids = [a["article_id"] for a in arts if _section(a) == path]
        rows.append((f"{name}\n{span}", sum(i in annotated for i in ids), len(ids), colour))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(rows))[::-1]
    for yi, (label, done, total, colour) in zip(y, rows):
        ax.barh(yi, done, color=colour, height=0.6)
        ax.barh(yi, total - done, left=done, color=colour, alpha=0.22, height=0.6)
        ax.text(total + 0.4, yi, f"{done} of {total} annotated", va="center", color=MUTED, fontsize=9)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.set_xlabel("Articles")
    ax.set_xlim(0, 32)
    ax.tick_params(axis="y", length=0)
    total_done, total = sum(r[1] for r in rows), sum(r[2] for r in rows)
    ax.set_title(f"The corpus: {total} articles of the Dutch Civil Code, "
                 f"{total_done} split into atoms so far")
    _save(fig, "corpus_map.png")


# -------------------------------------------------------------- data funnel

def data_funnel() -> None:
    if INDEX.exists():
        with INDEX.open(encoding="utf-8") as f:
            indexed = sum(1 for _ in f) - 1
    else:
        indexed = INDEXED_JUDGMENTS
    cites = pd.read_csv(PROCESSED / "caselaw_citations.csv", dtype=str).fillna("")
    cand = cites[cites["set"] == "candidate"]
    wgbo = int((cand["n_wgbo_articles"].astype(int) > 0).sum())
    summary = json.loads((TABLES / "study_a_dataset_summary.json").read_text(encoding="utf-8"))
    dev, test = summary["split"]["dev"], summary["split"]["test"]

    stages = [
        ("Civil judgments on rechtspraak.nl\nwith full text, 2000–2026", indexed),
        ("Medical terms in title or summary\n(downloaded)", len(cand)),
        ("Cite at least one WGBO article", wgbo),
        ("Facts section found and usable\n(the study A questions)", summary["items"]),
    ]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    y = np.arange(len(stages))[::-1]
    for yi, (label, n) in zip(y, stages):
        ax.barh(yi, n, color="#0072B2", alpha=0.35 + 0.15 * (len(stages) - yi), height=0.6)
        ax.text(n * 1.15, yi, f"{n:,}", va="center", fontweight="bold")
    ax.set_xscale("log")
    ax.set_xlim(100, indexed * 6)
    ax.set_yticks(y, [s[0] for s in stages])
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Judgments (log scale)")
    ax.text(summary["items"] * 2.6, y[-1], f"= {dev} dev  +  {test} test",
            va="center", color=MUTED, fontsize=9)
    ax.set_title("From all civil judgments to a test set of real cases")
    _save(fig, "data_funnel.png")


# ------------------------------------------------------------- atom example

LABEL_FIELDS = ["actors", "legal_relations", "acts", "temporal", "explicit_references",
                "hierarchies", "residual"]
FIELD_NAMES = {"legal_relations": "relations", "explicit_references": "references"}


def atom_example(article: str = "6:162") -> None:
    atoms = json.loads((ANNOTATIONS / f"{article.replace(':', '_')}.json").read_text(encoding="utf-8"))
    blocks = []
    for a in atoms:
        text = textwrap.wrap(a["text"], 92)
        labels = [f"{FIELD_NAMES.get(f, f)}: {', '.join(a[f])}" for f in LABEL_FIELDS if a[f]]
        labels = [line for lab in labels for line in textwrap.wrap(lab, 100)]
        blocks.append((a, text, labels))

    line = 0.24  # inches per text line
    height = 0.7 + sum((len(t) + len(lab) + 1.6) * line for _, t, lab in blocks)
    fig = plt.figure(figsize=(9, height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 9)
    ax.set_ylim(height, 0)

    ax.text(0.2, 0.35, f"Article {article} BW (tort) split into atoms",
            fontsize=12, fontweight="bold", va="center")
    y = 0.75
    for a, text, labels in blocks:
        pre = a["condition_type"] == "pre_condition"
        ax.text(0.2, y + 0.12, a["atom_id"], fontsize=9, color=MUTED, va="center",
                family="DejaVu Sans Mono")
        ax.text(1.45, y + 0.12, "pre-condition" if pre else "post-condition", fontsize=8,
                color="white", va="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc=PRE if pre else POST, ec="none"))
        y += 0.38
        for t in text:
            ax.text(0.35, y, t, fontsize=10, va="center")
            y += line
        for lab in labels:
            ax.text(0.35, y, lab, fontsize=8.5, va="center", color=MUTED)
            y += line
        y += 0.32
        ax.plot([0.2, 8.8], [y - 0.2, y - 0.2], color=GRID, lw=1)
    _save(fig, "atom_example.png")


# ------------------------------------------------------------------ results

def _bootstrap_ci(values: np.ndarray, draws: int = 5000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (draws, len(values)))].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def results(split: str = "dev") -> None:
    pq = pd.read_csv(TABLES / f"baselines_{split}_per_query.csv")
    systems = [s for s in SYSTEMS if s in set(pq["system"])]
    metrics = [("mrr", "MRR"), ("recall@10", "Recall@10"), ("ndcg@10", "nDCG@10")]
    n = pq["ecli"].nunique()

    fig, axes = plt.subplots(1, 3, figsize=(10, 4), sharey=True)
    y = np.arange(len(systems))[::-1]
    best = systems[-1]
    for ax, (col, title) in zip(axes, metrics):
        for yi, s in zip(y, systems):
            v = pq.loc[pq["system"] == s, col].to_numpy()
            lo, hi = _bootstrap_ci(v)
            colour = "#0072B2" if s == best else ("#9aa5ad" if s == "random" else INK)
            ax.plot([lo, hi], [yi, yi], color=colour, lw=2, alpha=0.45, solid_capstyle="round")
            ax.plot(v.mean(), yi, "o", color=colour, ms=6)
            ax.text(hi + 0.012, yi, f"{v.mean():.2f}", va="center", fontsize=8.5, color=colour)
        ax.set_title(title)
        ax.set_xlim(0, 0.75)
        ax.grid(axis="x", color=GRID)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(y, [SYSTEMS[s] for s in systems])
    fig.suptitle(f"Finding the articles a judge cited ({n} {split} judgments, 87 articles). "
                 "Dot = mean, line = 95% interval", x=0.01, ha="left", fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    _save(fig, "results.png")


# -------------------------------------------------------------- blind spots

def blind_spots(split: str = "dev", n_articles: int = 11, k: int = 10) -> None:
    ranks = pd.read_csv(TABLES / f"baselines_{split}_answer_ranks.csv")
    shown = ["bm25", "dense", "hybrid_rrf", "graph_both"]
    counts = ranks[ranks["system"] == "bm25"]["article"].value_counts()
    articles = counts.index[:n_articles].tolist()
    names = {a["article_id"]: _short_name(a["article_id"]) for a in _articles()}

    share = np.zeros((len(articles), len(shown)))
    found = np.zeros_like(share, dtype=int)
    for j, s in enumerate(shown):
        r = ranks[ranks["system"] == s]
        for i, a in enumerate(articles):
            hits = r.loc[r["article"] == a, "rank"] <= k
            found[i, j], share[i, j] = int(hits.sum()), hits.mean()

    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.imshow(share, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(len(articles)):
        for j in range(len(shown)):
            dark = share[i, j] > 0.55
            label = f"{found[i, j]}/{counts[articles[i]]}"
            ax.text(j, i, label, ha="center", va="center", fontsize=9,
                    color="white" if dark else (POST if found[i, j] == 0 else INK),
                    fontweight="bold" if found[i, j] == 0 else "normal")
    ax.set_xticks(range(len(shown)), [SYSTEMS[s].replace(", ", ",\n") for s in shown], fontsize=9)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(articles)), [f"{a}  {names.get(a, '')}" for a in articles])
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_title(f"How often each often-cited article reaches the top {k} "
                 f"(found / times cited, {split} set)", pad=42)
    _save(fig, "blind_spots.png")


_TOPICS = {
    "7:446": "treatment agreement", "7:448": "informing the patient", "7:450": "consent",
    "7:453": "duty of care", "7:454": "medical file", "7:457": "confidentiality",
    "7:462": "hospital liability", "7:464": "medical examinations", "6:74": "non-performance",
    "6:96": "damages: costs", "6:162": "tort", "6:89": "complaining in time",
    "7:456": "access to the file", "7:458": "data for research", "6:106": "non-material damage",
}


def _short_name(article: str) -> str:
    return _TOPICS.get(article, "")


# ----------------------------------------------------------- citation links

def citation_links() -> None:
    arts = _articles()
    ids = [a["article_id"] for a in arts]
    section = {a["article_id"]: _section(a) for a in arts}
    links = set()
    with (PROCESSED / "statute_references.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s, t = r["source_article"], r["target_article"]
            if s in section and t in section and s != t:
                links.add(tuple(sorted((s, t))))
    linked = {a for pair in links for a in pair}

    # One block per article, so every bar can be counted against the axis
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = np.arange(len(SECTIONS))[::-1]
    for yi, (path, (name, span, colour)) in zip(y, SECTIONS.items()):
        members = [a for a in ids if section[a] == path]
        n_linked = sum(a in linked for a in members)
        for i in range(len(members)):
            ax.barh(yi, 1, left=i, height=0.6, edgecolor="white", lw=1.2,
                    color=colour if i < n_linked else "white")
            if i >= n_linked:  # outline without covering the white gap
                ax.add_patch(plt.Rectangle((i + 0.08, yi - 0.27), 0.84, 0.54,
                                           fill=False, edgecolor=colour, lw=1.2))
        ax.text(len(members) + 0.5, yi, f"{len(members) - n_linked} of {len(members)} without any link",
                va="center", color=MUTED, fontsize=9)
    ax.set_yticks(y, [f"{name}\n{span}" for name, span, _ in SECTIONS.values()])
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 34)
    ax.set_xticks(range(0, 31, 5))
    ax.set_xticks(range(0, 31), minor=True)
    ax.set_xlabel("Articles (one block each; filled = cites or is cited by another article)")
    ax.set_title(f"Explicit citations between articles: {len(links)} links; "
                 f"{len(ids) - len(linked)} of {len(ids)} articles have none")
    _save(fig, "citation_links.png")


def main() -> None:
    print(f"Writing figures to {FIGURES.relative_to(PROJECT_ROOT)}/")
    corpus_map()
    data_funnel()
    atom_example()
    results()
    blind_spots()
    citation_links()


if __name__ == "__main__":
    main()
