"""
inspect_db.py — Print the current state of all three tables to the terminal.
Run from the project root:  python scripts/inspect_db.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models import Case, ModelOutput, Evaluation


def avg(values):
    v = [x for x in values if x is not None]
    return round(sum(v) / len(v), 1) if v else None


def main():
    db = SessionLocal()

    cases = db.query(Case).order_by(Case.id).all()
    outputs = db.query(ModelOutput).order_by(ModelOutput.id).all()
    evaluations = db.query(Evaluation).order_by(Evaluation.id).all()

    # ── Cases ────────────────────────────────────────────────────────────────
    print("=" * 70)
    print(f"  CASES  ({len(cases)} rows)")
    print("=" * 70)
    for c in cases:
        patient = f"{c.patient_age}y {c.patient_sex}" if c.patient_age else "—"
        print(f"  [{c.id:>2}]  {c.modality:<6}  {patient:<8}  {c.title}")
    print()

    # ── Model Outputs ─────────────────────────────────────────────────────────
    queued = sum(1 for o in outputs if o.status == "queued")
    evaluated = sum(1 for o in outputs if o.status == "evaluated")
    print("=" * 70)
    print(f"  MODEL OUTPUTS  ({len(outputs)} rows — {queued} queued, {evaluated} evaluated)")
    print("=" * 70)
    for o in outputs:
        n_evals = len(o.evaluations)
        print(
            f"  [{o.id:>2}]  case={o.case_id}  "
            f"{o.model_name} {o.model_version or ''}  "
            f"status={o.status:<10}  {n_evals} eval(s)"
        )
    print()

    # ── Evaluations ───────────────────────────────────────────────────────────
    flagged = sum(1 for e in evaluations if e.is_flagged)
    print("=" * 70)
    print(f"  EVALUATIONS  ({len(evaluations)} rows — {flagged} flagged)")
    print("=" * 70)
    if evaluations:
        print(
            f"  {'ID':>3}  {'output':>6}  {'clinician':<14}  "
            f"{'rating':>6}  {'acc':>4}  {'comp':>4}  {'clar':>4}  "
            f"{'flag':<5}  comments"
        )
        print("  " + "-" * 66)
        for e in evaluations:
            flag = "⚑" if e.is_flagged else ""
            comment = (e.comments[:40] + "…") if e.comments and len(e.comments) > 40 else (e.comments or "")
            print(
                f"  [{e.id:>2}]  out={e.output_id:>2}  {e.clinician_id:<14}  "
                f"  {e.rating}/5    {e.accuracy or '—':>3}   {e.completeness or '—':>3}   {e.clarity or '—':>3}  "
                f"{flag:<5}  {comment}"
            )
    else:
        print("  (no evaluations yet)")
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    if evaluations:
        ratings = [e.rating for e in evaluations]
        print("=" * 70)
        print("  SUMMARY")
        print("=" * 70)
        print(f"  Total evaluations : {len(evaluations)}")
        print(f"  Average rating    : {avg(ratings)}/5")
        print(f"  Flagged outputs   : {flagged}")
        clinicians = sorted(set(e.clinician_id for e in evaluations))
        print(f"  Clinicians        : {', '.join(clinicians)}")
        print()

    db.close()


if __name__ == "__main__":
    main()
