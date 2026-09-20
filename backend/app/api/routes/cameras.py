"""
app/api/routes/cameras.py
Camera CRUD endpoints — all routes are JWT-protected.

GET    /cameras               list all cameras
POST   /cameras               create a new camera
GET    /cameras/{camera_id}   get a single camera
PATCH  /cameras/{camera_id}   update fields
DELETE /cameras/{camera_id}   remove a camera
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate
from app.schemas.user import UserOut
from app.services import camera_service

router = APIRouter(prefix="/cameras", tags=["cameras"])

# Reusable auth dependency alias
_Auth = Annotated[UserOut, Depends(get_current_user)]


@router.get("", response_model=list[CameraOut])
async def list_cameras(_: _Auth) -> list[CameraOut]:
    return camera_service.list_cameras()


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
async def create_camera(body: CameraCreate, _: _Auth) -> CameraOut:
    return camera_service.create_camera(body)


@router.post("/stop-all", response_model=dict)
async def stop_all_cameras(_: _Auth) -> dict:
    stopped = camera_service.stop_all_cameras()
    return {"stopped": stopped, "status": "stopped"}


@router.post("/{camera_id}/start", response_model=CameraOut)
async def start_camera(camera_id: UUID, _: _Auth) -> CameraOut:
    camera = camera_service.start_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera


@router.post("/{camera_id}/stop", response_model=CameraOut)
async def stop_camera(camera_id: UUID, _: _Auth) -> CameraOut:
    camera = camera_service.stop_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera


@router.get("/{camera_id}/worker", response_model=dict)
async def camera_worker_status(camera_id: UUID, _: _Auth) -> dict:
    result = camera_service.worker_status(camera_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return result


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(camera_id: UUID, _: _Auth) -> CameraOut:
    camera = camera_service.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera


@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(camera_id: UUID, body: CameraUpdate, _: _Auth) -> CameraOut:
    camera = camera_service.update_camera(camera_id, body)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: UUID, _: _Auth) -> None:
    if not camera_service.delete_camera(camera_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
