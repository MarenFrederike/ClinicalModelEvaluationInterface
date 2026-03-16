from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Case(Base):
    """
    A clinical scenario presented to the model.
    Created by curators/admins. Contains patient context and the prompt.
    """
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    clinical_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)   # CT, MRI, X-ray, etc.
    image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    # Patient context — anonymised, used to contextualise the prompt for evaluators
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_sex: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # M / F / Other
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    outputs: Mapped[list["ModelOutput"]] = relationship(
        "ModelOutput", back_populates="case", order_by="ModelOutput.generated_at"
    )


class ModelOutput(Base):
    """
    An AI-generated report/answer for a case.
    Written to the DB by the model pipeline — independently of evaluations.
    Starts with status='queued' and waits until a clinician evaluates it.
    """
    __tablename__ = "model_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. "v1.2"
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_type: Mapped[str] = mapped_column(String(50), default="report")  # report | answer | annotation
    # Queue status — the pipeline sets this to 'queued'; flipped to 'evaluated' on first submission
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["Case"] = relationship("Case", back_populates="outputs")
    evaluations: Mapped[list["Evaluation"]] = relationship("Evaluation", back_populates="output")


class Evaluation(Base):
    """
    A clinician's structured feedback on a specific model output.
    One output can receive multiple evaluations from different clinicians.
    """
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    output_id: Mapped[int] = mapped_column(Integer, ForeignKey("model_outputs.id"), nullable=False)
    clinician_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Overall quality: 1 (unacceptable) → 5 (excellent)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    # Specific dimensions
    accuracy: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)     # clinical accuracy
    completeness: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # nothing missed
    clarity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)      # language quality
    # Free text
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Flag for serious errors (hallucinations, dangerous omissions)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    output: Mapped["ModelOutput"] = relationship("ModelOutput", back_populates="evaluations")


class ComparisonEvaluation(Base):
    """
    A clinician's head-to-head comparison of two model outputs for the same case.
    Per-axis preferences use "a", "tie", or "b".
    overall_preference uses a 5-point scale: strongly_a, slightly_a, tie, slightly_b, strongly_b.
    """
    __tablename__ = "comparison_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id"), nullable=False)
    output_a_id: Mapped[int] = mapped_column(Integer, ForeignKey("model_outputs.id"), nullable=False)
    output_b_id: Mapped[int] = mapped_column(Integer, ForeignKey("model_outputs.id"), nullable=False)
    clinician_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Per-axis preferences: "a", "tie", or "b"
    axis_accuracy: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)     # reflects medical consensus
    axis_completeness: Mapped[Optional[str]] = mapped_column(String(10), nullable=True) # thoroughness
    axis_safety: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)       # clinical safety
    axis_reasoning: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)    # reasoning quality
    # 5-point overall: strongly_a | slightly_a | tie | slightly_b | strongly_b
    overall_preference: Mapped[str] = mapped_column(String(20), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
