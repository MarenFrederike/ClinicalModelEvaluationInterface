from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, SessionLocal
from app.models import Base
from app.seed import seed
from app.routes import cases, evaluations


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Clinical Model Evaluation Interface", lifespan=lifespan)

app.include_router(cases.router)
app.include_router(evaluations.router)
