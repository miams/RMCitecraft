"""
REST API Endpoints for Browser Extension Communication

Provides HTTP API for:
- Health checks
- Citation import from extension
- Command queue management for extension
"""


from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from rmcitecraft.services.citation_import import get_citation_import_service
from rmcitecraft.services.command_queue import get_command_queue


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str = "1.0.0"


class CitationImportRequest(BaseModel):
    """Citation import request model."""

    # Allow any fields from extension
    class Config:
        extra = "allow"


class CitationImportResponse(BaseModel):
    """Citation import response model."""

    status: str
    citation_id: str
    message: str


class CommandRequest(BaseModel):
    """Command creation request model."""

    type: str
    data: dict | None = None


class CommandResponse(BaseModel):
    """Command response model."""

    command_id: str
    status: str
    message: str


def create_api_router() -> APIRouter:
    """
    Create FastAPI router with all API endpoints.

    Returns:
        Configured APIRouter instance
    """
    router = APIRouter(prefix="/api")

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    @router.get("/health", response_model=HealthResponse)
    async def health_check():
        """
        Health check endpoint.

        Used by browser extension to detect if RMCitecraft is running.

        Returns:
            Health status response
        """
        logger.debug("Health check requested")
        return HealthResponse(status="ok")

    # -------------------------------------------------------------------------
    # Citation Import
    # -------------------------------------------------------------------------

    @router.post("/citation/import", response_model=CitationImportResponse)
    async def import_citation(data: dict = Body(...)):
        """
        Import citation data from browser extension.

        Receives structured census data extracted from FamilySearch page.
        Validates and queues citation for user review.

        Args:
            data: Citation data from extension

        Returns:
            Import response with citation ID

        Raises:
            HTTPException: If data validation fails
        """
        try:
            import_service = get_citation_import_service()
            citation_id = import_service.import_citation(data)

            logger.info(f"Citation imported via API: {citation_id}")

            return CitationImportResponse(
                status="success",
                citation_id=citation_id,
                message="Citation imported successfully",
            )

        except ValueError as e:
            logger.error(f"Citation import validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e)) from e

        except Exception as e:
            logger.error(f"Citation import error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    @router.get("/citation/pending")
    async def get_pending_citations():
        """
        Get all pending citations awaiting review.

        Returns:
            List of pending citation dictionaries
        """
        import_service = get_citation_import_service()
        pending = import_service.get_pending()

        logger.debug(f"Retrieved {len(pending)} pending citations via API")

        return JSONResponse(content={"citations": pending, "count": len(pending)})

    @router.get("/citation/{citation_id}")
    async def get_citation(citation_id: str):
        """
        Get a specific citation by ID.

        Args:
            citation_id: Citation ID

        Returns:
            Citation data

        Raises:
            HTTPException: If citation not found
        """
        import_service = get_citation_import_service()
        citation = import_service.get(citation_id)

        if citation is None:
            raise HTTPException(status_code=404, detail="Citation not found")

        return JSONResponse(content=citation)

    # -------------------------------------------------------------------------
    # Command Queue (Extension Polling)
    # -------------------------------------------------------------------------

    @router.get("/extension/commands")
    async def get_commands():
        """
        Get pending commands for browser extension.

        Extension polls this endpoint every 2 seconds to check for commands
        from RMCitecraft (e.g., download_image, ping, shutdown).

        Returns:
            List of pending commands
        """
        command_queue = get_command_queue()
        commands = command_queue.get_pending()

        if commands:
            logger.debug(f"Sending {len(commands)} command(s) to extension")

        return JSONResponse(content=commands)

    @router.post("/extension/commands", response_model=CommandResponse)
    async def queue_command(command: CommandRequest):
        """
        Queue a command for the browser extension.

        Used by RMCitecraft to send commands to the extension
        (e.g., trigger image download).

        Args:
            command: Command to queue

        Returns:
            Command response with ID
        """
        try:
            command_queue = get_command_queue()
            command_id = command_queue.add(command.type, command.data)

            logger.info(f"Command queued via API: {command.type} (ID: {command_id})")

            return CommandResponse(
                command_id=command_id,
                status="queued",
                message=f"Command '{command.type}' queued successfully",
            )

        except Exception as e:
            logger.error(f"Command queue error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    @router.delete("/extension/commands/{command_id}")
    async def complete_command(command_id: str, response: dict | None = Body(None)):
        """
        Mark a command as completed and remove from queue.

        Called by extension after executing a command.

        Args:
            command_id: Command ID
            response: Optional response data from extension

        Returns:
            Success response

        Raises:
            HTTPException: If command not found
        """
        command_queue = get_command_queue()

        # Check for error in response
        if response and response.get("status") == "error":
            success = command_queue.fail(command_id, response.get("error"))
        else:
            success = command_queue.complete(command_id, response)

        if not success:
            raise HTTPException(status_code=404, detail="Command not found")

        return JSONResponse(
            content={"status": "success", "message": "Command completed"}
        )

    # -------------------------------------------------------------------------
    # Statistics & Debugging
    # -------------------------------------------------------------------------

    @router.get("/stats")
    async def get_stats():
        """
        Get API statistics.

        Returns:
            Statistics for citation imports and command queue
        """
        import_service = get_citation_import_service()
        command_queue = get_command_queue()

        stats = {
            "citations": import_service.get_stats(),
            "commands": command_queue.get_stats(),
        }

        return JSONResponse(content=stats)

    return router
