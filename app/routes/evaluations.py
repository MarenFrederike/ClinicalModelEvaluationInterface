from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ComparisonEvaluation, Evaluation, ModelOutput

router = APIRouter()


@router.post("/evaluations/single/{output_id}")
def submit_single_evaluation(
    output_id: int,
    db: Session = Depends(get_db),
    clinician_id: str = Form(...),
    rating: int = Form(...),
    accuracy: Optional[int] = Form(default=None),
    completeness: Optional[int] = Form(default=None),
    clarity: Optional[int] = Form(default=None),
    comments: Optional[str] = Form(default=None),
    flagged: Optional[str] = Form(default=None),
    marked_regions: Optional[str] = Form(default=None),
):
    output = db.query(ModelOutput).filter(ModelOutput.id == output_id).first()
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")
    if not (1 <= rating <= 5):
        raise HTTPException(status_code=422, detail="Rating must be between 1 and 5")

    db.add(Evaluation(
        output_id=output_id,
        clinician_id=clinician_id.strip(),
        rating=rating,
        accuracy=accuracy,
        completeness=completeness,
        clarity=clarity,
        comments=comments.strip() if comments else None,
        is_flagged=flagged is not None,
        marked_regions=marked_regions if marked_regions and marked_regions != "[]" else None,
    ))
    output.status = "evaluated"
    db.commit()
    return RedirectResponse(url=f"/?done={output.case_id}", status_code=303)


@router.post("/evaluations/compare/{case_id}")
def submit_comparison(
    case_id: int,
    db: Session = Depends(get_db),
    clinician_id: str = Form(...),
    output_a_id: int = Form(...),
    output_b_id: int = Form(...),
    axis_accuracy: str = Form(...),
    axis_completeness: str = Form(...),
    axis_safety: str = Form(...),
    axis_reasoning: str = Form(...),
    overall_preference: str = Form(...),
):
    if not db.query(ModelOutput).filter(ModelOutput.id == output_a_id).first():
        raise HTTPException(status_code=404, detail="Output A not found")
    if not db.query(ModelOutput).filter(ModelOutput.id == output_b_id).first():
        raise HTTPException(status_code=404, detail="Output B not found")

    valid_axis = {"a", "tie", "b"}
    valid_overall = {"strongly_a", "slightly_a", "tie", "slightly_b", "strongly_b"}
    if any(v not in valid_axis for v in [axis_accuracy, axis_completeness, axis_safety, axis_reasoning]):
        raise HTTPException(status_code=422, detail="Invalid axis value")
    if overall_preference not in valid_overall:
        raise HTTPException(status_code=422, detail="Invalid overall_preference value")

    db.add(ComparisonEvaluation(
        case_id=case_id,
        output_a_id=output_a_id,
        output_b_id=output_b_id,
        clinician_id=clinician_id.strip(),
        axis_accuracy=axis_accuracy,
        axis_completeness=axis_completeness,
        axis_safety=axis_safety,
        axis_reasoning=axis_reasoning,
        overall_preference=overall_preference,
    ))
    db.commit()
    return RedirectResponse(url=f"/?done={case_id}", status_code=303)
