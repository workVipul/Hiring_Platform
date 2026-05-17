from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api/v1/sourcing", tags=["Sourcing"])


@router.get("/my-jds")
def my_jds():
    raise HTTPException(status_code=501, detail="Sourcing integration is not enabled")


@router.get("/common-jds")
def common_jds():
    raise HTTPException(status_code=501, detail="Sourcing integration is not enabled")
