# app/models/room.py
from pydantic import BaseModel
from typing import Optional, List

class Room(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_by: str
    created_at: str
    member_count: int = 0

class CreateRoomRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    created_by: str = "anonymous"

class PublishMessageRequest(BaseModel):
    room_id: str
    content: str
    sender: Optional[str] = "anonymous"
