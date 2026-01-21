from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.auth.auth import get_db
from utils.jwt import get_current_user
from services.storage_quota import get_storage_stats

router = APIRouter()


@router.get("/me/storage")
def get_user_storage(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return get_storage_stats(db, user)
