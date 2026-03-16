from itertools import combinations

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased, joinedload

from app.database import get_db
from app.models import Case, ComparisonEvaluation, Evaluation, ModelOutput

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index(request: Request, db: Session = Depends(get_db), done: int = None):
    cases = (
        db.query(Case)
        .options(joinedload(Case.outputs))
        .order_by(Case.id)
        .all()
    )

    # Count submitted evaluations per case for progress display
    eval_counts = {}
    for case in cases:
        output_ids = [o.id for o in case.outputs]
        if output_ids:
            count = db.query(Evaluation).filter(
                Evaluation.output_id.in_(output_ids)
            ).count()
        else:
            count = 0
        eval_counts[case.id] = count

    return templates.TemplateResponse("index.html", {
        "request": request,
        "cases": cases,
        "eval_counts": eval_counts,
        "done": done,
    })


@router.get("/cases/{case_id}/evaluate")
def evaluate_select(request: Request, case_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(Case)
        .options(joinedload(Case.outputs))
        .filter(Case.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Attach eval count to each output, sort fewest-first
    output_data = []
    for output in case.outputs:
        count = db.query(Evaluation).filter(Evaluation.output_id == output.id).count()
        output_data.append({"output": output, "eval_count": count})
    output_data.sort(key=lambda x: x["eval_count"])

    return templates.TemplateResponse("pick_output.html", {
        "request": request,
        "case": case,
        "output_data": output_data,
    })


@router.get("/cases/{case_id}/evaluate/{output_id}")
def evaluate_page(request: Request, case_id: int, output_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(Case)
        .options(joinedload(Case.outputs))
        .filter(Case.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    output = next((o for o in case.outputs if o.id == output_id), None)
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    return templates.TemplateResponse("evaluate.html", {
        "request": request,
        "case": case,
        "output": output,
    })


@router.get("/cases/{case_id}/compare")
def compare_page(request: Request, case_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(Case)
        .options(joinedload(Case.outputs))
        .filter(Case.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    outputs = sorted(case.outputs, key=lambda o: o.id)
    if len(outputs) < 2:
        raise HTTPException(status_code=400, detail="Case needs at least two outputs to compare")

    # Find the pair compared fewest times — works for any number of outputs
    pair_counts = []
    for a, b in combinations(outputs, 2):
        count = db.query(ComparisonEvaluation).filter(
            or_(
                and_(ComparisonEvaluation.output_a_id == a.id,
                     ComparisonEvaluation.output_b_id == b.id),
                and_(ComparisonEvaluation.output_a_id == b.id,
                     ComparisonEvaluation.output_b_id == a.id),
            )
        ).count()
        pair_counts.append((count, a, b))

    pair_counts.sort(key=lambda x: x[0])
    best_count, output_a, output_b = pair_counts[0]

    return templates.TemplateResponse("compare.html", {
        "request": request,
        "case": case,
        "output_a": output_a,
        "output_b": output_b,
        "pair_count": best_count,
    })


@router.get("/cases/{case_id}/image")
def case_image(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or not case.image_data:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=case.image_data, media_type="image/jpeg")


@router.get("/results")
def results_page(request: Request, db: Session = Depends(get_db)):
    cases = (
        db.query(Case)
        .options(joinedload(Case.outputs).joinedload(ModelOutput.evaluations))
        .order_by(Case.id)
        .all()
    )

    # Pre-compute per-output stats so the template stays simple
    results = []
    total_evals = 0
    total_flagged = 0

    for case in cases:
        output_rows = []
        for output in sorted(case.outputs, key=lambda o: o.id):
            evals = output.evaluations
            n = len(evals)
            total_evals += n
            flags = sum(1 for e in evals if e.is_flagged)
            total_flagged += flags

            def avg(values):
                v = [x for x in values if x is not None]
                return round(sum(v) / len(v), 1) if v else None

            output_rows.append({
                "output": output,
                "n": n,
                "avg_rating":       avg([e.rating for e in evals]),
                "avg_accuracy":     avg([e.accuracy for e in evals]),
                "avg_completeness": avg([e.completeness for e in evals]),
                "avg_clarity":      avg([e.clarity for e in evals]),
                "flags": flags,
                "evals": evals,
            })
        results.append({"case": case, "outputs": output_rows})

    # ── Elo ranking from head-to-head comparisons ──────────────────────────
    PREF_TO_SCORE = {
        "strongly_a": 1.00,
        "slightly_a": 0.75,
        "tie":        0.50,
        "slightly_b": 0.25,
        "strongly_b": 0.00,
    }
    K = 32

    OutputA = aliased(ModelOutput)
    OutputB = aliased(ModelOutput)
    comparisons = (
        db.query(ComparisonEvaluation, OutputA, OutputB)
        .join(OutputA, ComparisonEvaluation.output_a_id == OutputA.id)
        .join(OutputB, ComparisonEvaluation.output_b_id == OutputB.id)
        .order_by(ComparisonEvaluation.submitted_at)
        .all()
    )

    def model_key(o: ModelOutput) -> str:
        return f"{o.model_name} {o.model_version}" if o.model_version else o.model_name

    elo: dict[str, float] = {}
    comp_counts: dict[str, int] = {}
    axis_stats: dict[str, dict] = {}   # model → axis → {wins, total}

    AXES = ["accuracy", "completeness", "safety", "reasoning"]

    for comp, oa, ob in comparisons:
        ka, kb = model_key(oa), model_key(ob)
        for k in (ka, kb):
            elo.setdefault(k, 1500.0)
            comp_counts.setdefault(k, 0)
            axis_stats.setdefault(k, {ax: {"wins": 0, "total": 0} for ax in AXES})

        # Elo update from overall_preference
        score_a = PREF_TO_SCORE.get(comp.overall_preference, 0.5)
        e_a = 1 / (1 + 10 ** ((elo[kb] - elo[ka]) / 400))
        delta = K * (score_a - e_a)
        elo[ka] += delta
        elo[kb] -= delta
        comp_counts[ka] += 1
        comp_counts[kb] += 1

        # Per-axis win accumulation
        axis_vals = {
            "accuracy":     comp.axis_accuracy,
            "completeness": comp.axis_completeness,
            "safety":       comp.axis_safety,
            "reasoning":    comp.axis_reasoning,
        }
        for ax, val in axis_vals.items():
            if val is None:
                continue
            axis_stats[ka][ax]["total"] += 1
            axis_stats[kb][ax]["total"] += 1
            if val == "a":
                axis_stats[ka][ax]["wins"] += 1
            elif val == "b":
                axis_stats[kb][ax]["wins"] += 1

    # Build sorted leaderboard
    def win_pct(stats: dict, ax: str) -> str:
        t = stats[ax]["total"]
        return f"{round(stats[ax]['wins'] / t * 100)}%" if t else "—"

    elo_rankings = sorted(
        [
            {
                "model": k,
                "elo": round(elo[k]),
                "comparisons": comp_counts[k],
                "accuracy":     win_pct(axis_stats[k], "accuracy"),
                "completeness": win_pct(axis_stats[k], "completeness"),
                "safety":       win_pct(axis_stats[k], "safety"),
                "reasoning":    win_pct(axis_stats[k], "reasoning"),
            }
            for k in elo
        ],
        key=lambda x: x["elo"],
        reverse=True,
    )

    return templates.TemplateResponse("results.html", {
        "request": request,
        "results": results,
        "total_evals": total_evals,
        "total_flagged": total_flagged,
        "cases_complete": sum(
            1 for r in results
            if all(row["n"] > 0 for row in r["outputs"])
        ),
        "total_cases": len(cases),
        "elo_rankings": elo_rankings,
        "total_comparisons": sum(comp_counts.values()) // 2 if comp_counts else 0,
    })
