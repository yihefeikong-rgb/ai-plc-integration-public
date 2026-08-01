"""对话历史 API 路由"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security import require_local_session
from storage.conversations import ConversationStore

router = APIRouter()

store: ConversationStore = None  # type: ignore


def set_store(s: ConversationStore):
    global store
    store = s


class CreateConversation(BaseModel):
    title: str = ""
    model_id: str = "deepseek"


class AddMessage(BaseModel):
    role: str
    content: str
    msg_type: str = "text"
    metadata: dict = {}


class UpdateTitle(BaseModel):
    title: str


@router.get("")
async def list_conversations(limit: int = 50, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    return {"conversations": store.list_conversations(limit)}


@router.post("", status_code=201)
async def create_conversation(data: CreateConversation, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    conv = store.create_conversation(data.title, data.model_id)
    return {"conversation": conv}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"conversation": conv}


@router.put("/{conv_id}")
async def update_conversation(conv_id: str, data: UpdateTitle, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    ok = store.update_conversation(conv_id, data.title)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"status": "updated"}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    ok = store.delete_conversation(conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"status": "deleted"}


@router.post("/{conv_id}/messages", status_code=201)
async def add_message(conv_id: str, data: AddMessage, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    msg = store.add_message(conv_id, data.role, data.content, data.msg_type, data.metadata)
    return {"message": msg}


@router.get("/stats/overview")
async def conversation_stats(_actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    return store.get_stats()
