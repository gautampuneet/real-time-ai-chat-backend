"""Conversation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.dependencies import CurrentUser, DatabaseDep, PaginationDep
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdateRequest,
)
from app.schemas.message import MessageListResponse, MessageResponse
from app.services.conversation import ConversationService
from app.services.message import MessageService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: CurrentUser,
    db: DatabaseDep,
) -> ConversationResponse:
    conversation = await ConversationService(db).create_conversation(
        owner_id=current_user.id,
        title=payload.title,
    )
    return ConversationResponse.model_validate(conversation)


@router.get(
    "",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List conversations",
)
async def list_conversations(
    current_user: CurrentUser,
    db: DatabaseDep,
    pagination: PaginationDep,
) -> ConversationListResponse:
    page = await ConversationService(db).list_conversations(
        owner_id=current_user.id,
        pagination=pagination,
    )
    return ConversationListResponse.create(
        items=[ConversationResponse.model_validate(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rename a conversation",
)
async def rename_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    current_user: CurrentUser,
    db: DatabaseDep,
) -> ConversationResponse:
    conversation = await ConversationService(db).rename_conversation(
        conversation_id=conversation_id,
        owner_id=current_user.id,
        title=payload.title,
    )
    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseDep,
) -> Response:
    await ConversationService(db).delete_conversation(
        conversation_id=conversation_id,
        owner_id=current_user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List conversation messages",
)
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseDep,
    pagination: PaginationDep,
) -> MessageListResponse:
    page = await MessageService(db).list_conversation_messages(
        conversation_id=conversation_id,
        owner_id=current_user.id,
        pagination=pagination,
    )
    return MessageListResponse.create(
        items=[MessageResponse.model_validate(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
