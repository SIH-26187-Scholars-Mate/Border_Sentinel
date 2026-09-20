import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from app.core.config import get_settings
from app.core.database import get_supabase
from app.schemas.zone import ZoneCreate, ZoneOut

_memory: dict[str, dict] = {}
def _mem(): return get_settings().database_mode == 'memory'
def list_zones(camera_id: UUID):
    if _mem(): return [ZoneOut(**r) for r in _memory.values() if str(r['camera_id']) == str(camera_id)]
    rows=get_supabase().table('zones').select('*').eq('camera_id',str(camera_id)).order('created_at').execute().data
    return [ZoneOut(**r) for r in rows]
def create_zone(camera_id: UUID, data: ZoneCreate):
    rid=uuid.uuid4(); now=datetime.now(timezone.utc)
    record={'id':rid,'camera_id':camera_id,**data.model_dump()}
    if _mem(): _memory[str(rid)]={**record}; return ZoneOut(**record)
    payload={**data.model_dump(mode='json'),'id':str(rid),'camera_id':str(camera_id),'created_at':now.isoformat()}
    rows=get_supabase().table('zones').insert(payload).execute().data
    return ZoneOut(**rows[0])
def update_zone(zone_id: UUID, data: ZoneCreate) -> Optional[ZoneOut]:
    """Overwrites an existing zone's shape/name/settings in place, so
    editing a fence keeps its id (and history/references to it) instead of
    deleting and recreating it."""
    if _mem():
        existing = _memory.get(str(zone_id))
        if existing is None: return None
        existing.update(data.model_dump())
        return ZoneOut(**existing)
    rows=get_supabase().table('zones').update(data.model_dump(mode='json')).eq('id',str(zone_id)).execute().data
    return ZoneOut(**rows[0]) if rows else None
def delete_zone(zone_id: UUID):
    if _mem(): return _memory.pop(str(zone_id),None) is not None
    rows=get_supabase().table('zones').delete().eq('id',str(zone_id)).execute().data
    return bool(rows)
