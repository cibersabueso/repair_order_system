from fastapi import APIRouter, Depends
from typing import Any

from ...application import CommandHandler, CommandRequest, CommandResponse
from ..adapters import InMemoryRepairOrderRepository

router = APIRouter(prefix="/api/v1", tags=["repair-orders"])

_repository = InMemoryRepairOrderRepository()


def get_repository() -> InMemoryRepairOrderRepository:
    return _repository


def get_command_handler(
    repository: InMemoryRepairOrderRepository = Depends(get_repository)
) -> CommandHandler:
    return CommandHandler(repository)


@router.post("/commands", response_model=CommandResponse)
async def process_commands(
    request: CommandRequest,
    handler: CommandHandler = Depends(get_command_handler)
) -> CommandResponse:
    return handler.execute(request.commands)


@router.post("/reset")
async def reset_repository(
    repository: InMemoryRepairOrderRepository = Depends(get_repository)
) -> dict[str, str]:
    repository.clear()
    return {"status": "ok", "message": "Repository cleared"}
