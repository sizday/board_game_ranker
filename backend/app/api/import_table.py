from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.infrastructure.repositories import replace_all_from_table

router = APIRouter()


class ImportTableRequest(BaseModel):
    rows: List[dict]


class ImportTableResponse(BaseModel):
    status: str
    games_imported: int = 0
    message: str = ""


@router.post("/import-table", response_model=ImportTableResponse)
async def import_table(request: ImportTableRequest, db: Session = Depends(get_db)):
    """Import games data from table to database."""
    try:
        replace_all_from_table(db, request.rows)
        db.commit()
        return ImportTableResponse(status="ok", games_imported=len(request.rows))
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))



