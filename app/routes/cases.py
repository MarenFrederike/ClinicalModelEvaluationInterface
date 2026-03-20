from itertools import combinations
import json

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased, joinedload

from app.database import get_db
from app.models import Case, ComparisonEvaluation, Evaluation, ModelOutput

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def compute_dice(region_a_list, region_b_list):
    """
    Compute Dice similarity coefficient between two sets of regions.
    Dice = 2 * |Overlap| / (|Region A| + |Region B|)
    Regions expected in normalized [0,1] coordinates: {x, y, w, h}
    """
    if not region_a_list or not region_b_list:
        return 0.0

    # Calculate total area for each set
    area_a = sum(region['w'] * region['h'] for region in region_a_list)
    area_b = sum(region['w'] * region['h'] for region in region_b_list)

    if area_a == 0 or area_b == 0:
        return 0.0

    # Calculate overlaps between all pairs of regions
    overlap = 0.0
    for ra in region_a_list:
        for rb in region_b_list:
            # Calculate intersection rectangle
            x_min_a, y_min_a = ra['x'], ra['y']
            x_max_a = ra['x'] + ra['w']
            y_max_a = ra['y'] + ra['h']

            x_min_b, y_min_b = rb['x'], rb['y']
            x_max_b = rb['x'] + rb['w']
            y_max_b = rb['y'] + rb['h']

            x_min = max(x_min_a, x_min_b)
            x_max = min(x_max_a, x_max_b)
            y_min = max(y_min_a, y_min_b)
            y_max = min(y_max_a, y_max_b)

            if x_max > x_min and y_max > y_min:
                overlap += (x_max - x_min) * (y_max - y_min)

    dice = 2 * overlap / (area_a + area_b)
    return round(dice, 3)


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


@router.get("/compare")
def compare_global(request: Request, db: Session = Depends(get_db)):
    """Find the globally least-compared pair across all cases and load the comparison form."""
    cases = db.query(Case).options(joinedload(Case.outputs)).all()

    # Build list of all possible pairs with their comparison counts
    all_pairs = []
    for case in cases:
        outputs = sorted(case.outputs, key=lambda o: o.id)
        if len(outputs) < 2:
            continue

        for a, b in combinations(outputs, 2):
            count = db.query(ComparisonEvaluation).filter(
                or_(
                    and_(ComparisonEvaluation.output_a_id == a.id,
                         ComparisonEvaluation.output_b_id == b.id),
                    and_(ComparisonEvaluation.output_a_id == b.id,
                         ComparisonEvaluation.output_b_id == a.id),
                )
            ).count()
            all_pairs.append((count, case, a, b))

    if not all_pairs:
        raise HTTPException(status_code=400, detail="No cases available for comparison")

    # Sort by comparison count and pick the least-compared
    all_pairs.sort(key=lambda x: x[0])
    best_count, case, output_a, output_b = all_pairs[0]

    return templates.TemplateResponse("compare.html", {
        "request": request,
        "case": case,
        "output_a": output_a,
        "output_b": output_b,
        "pair_count": best_count,
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
    # Fetch all evaluations to compute global statistics
    all_outputs = db.query(ModelOutput).options(joinedload(ModelOutput.evaluations)).all()

    total_evals = 0
    total_flagged = 0

    # Compute model-level aggregations (for radar charts)
    models_data = {}  # model_key → {evals_list, ratings_dict}

    for output in all_outputs:
        evals = output.evaluations
        total_evals += len(evals)
        flagged = sum(1 for e in evals if e.is_flagged)
        total_flagged += flagged

        model_key = f"{output.model_name} {output.model_version}" if output.model_version else output.model_name
        if model_key not in models_data:
            models_data[model_key] = {
                "model_name": output.model_name,
                "model_version": output.model_version,
                "evals": [],
            }
        models_data[model_key]["evals"].extend(evals)

    # Calculate averages per model
    def avg(values):
        v = [x for x in values if x is not None]
        return round(sum(v) / len(v), 2) if v else 0  # Default to 0 for missing ratings

    models_summary = []
    for model_key, data in sorted(models_data.items()):
        evals = data["evals"]
        if not evals:
            continue

        models_summary.append({
            "model_key": model_key,
            "model_name": data["model_name"],
            "model_version": data["model_version"],
            "avg_overall_rating": avg([e.rating for e in evals]),
            "avg_accuracy": avg([e.accuracy for e in evals]),
            "avg_completeness": avg([e.completeness for e in evals]),
            "avg_clarity": avg([e.clarity for e in evals]),
            "eval_count": len(evals),
            "flag_count": sum(1 for e in evals if e.is_flagged),
        })

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

    # ── Dice score evaluation for marked regions ──────────────────────────────
    dice_data = []  # List of {model_key, case_id, dice_score}
    for output in all_outputs:
        model_key = f"{output.model_name} {output.model_version}" if output.model_version else output.model_name
        bounding_boxes = []
        if output.bounding_boxes:
            try:
                bounding_boxes = json.loads(output.bounding_boxes)
            except (json.JSONDecodeError, TypeError):
                bounding_boxes = []

        for eval in output.evaluations:
            marked_regions = []
            if eval.marked_regions:
                try:
                    marked_regions = json.loads(eval.marked_regions)
                except (json.JSONDecodeError, TypeError):
                    marked_regions = []

            # Only compute Dice if both regions exist
            if bounding_boxes and marked_regions:
                dice_score = compute_dice(marked_regions, bounding_boxes)
                dice_data.append({
                    "model_key": model_key,
                    "case_id": output.case_id,
                    "dice_score": dice_score,
                    "eval_id": eval.id,
                })

    return templates.TemplateResponse("results.html", {
        "request": request,
        "models_summary": models_summary,
        "total_evals": total_evals,
        "total_flagged": total_flagged,
        "total_cases": len(db.query(Case).all()),
        "elo_rankings": elo_rankings,
        "total_comparisons": sum(comp_counts.values()) // 2 if comp_counts else 0,
        "dice_data": dice_data,
    })
