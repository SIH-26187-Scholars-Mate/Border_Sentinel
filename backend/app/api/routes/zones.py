from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.schemas.user import UserOut
from app.schemas.zone import ZoneCreate, ZoneOut
from app.services import zone_service
router=APIRouter(prefix='/cameras/{camera_id}/zones',tags=['zones'])
Auth=Annotated[UserOut,Depends(get_current_user)]
@router.get('',response_model=list[ZoneOut])
async def list_zones(camera_id:UUID,_:Auth): return zone_service.list_zones(camera_id)
@router.post('',response_model=ZoneOut,status_code=status.HTTP_201_CREATED)
async def create_zone(camera_id:UUID,body:ZoneCreate,_:Auth): return zone_service.create_zone(camera_id,body)
@router.put('/{zone_id}',response_model=ZoneOut)
async def update_zone(camera_id:UUID,zone_id:UUID,body:ZoneCreate,_:Auth):
    updated=zone_service.update_zone(zone_id,body)
    if not updated: raise HTTPException(404,'Zone not found')
    return updated
@router.delete('/{zone_id}',status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(camera_id:UUID,zone_id:UUID,_:Auth):
    if not zone_service.delete_zone(zone_id): raise HTTPException(404,'Zone not found')
