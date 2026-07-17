"""MCP server marketplace API.

Endpoints for browsing, installing, enabling and health-checking external MCP
servers. Mutating endpoints require admin access; read-only endpoints require
authentication when auth is enabled.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from homomics_lab.api.auth import require_admin, require_auth
from homomics_lab.mcp.marketplace import MCPServerEntry, MCPMarketplace

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _marketplace(request: Request) -> MCPMarketplace:
    marketplace = getattr(request.app.state, "mcp_marketplace", None)
    if marketplace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP marketplace not initialized",
        )
    return marketplace


@router.get("/servers", response_model=List[Dict[str, Any]])
async def list_servers(
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_auth),
):
    """List all MCP servers in the marketplace."""
    return [entry.model_dump() for entry in marketplace.list_servers()]


@router.post("/servers", response_model=Dict[str, Any])
async def add_server(
    data: MCPServerEntry,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_admin),
):
    """Add a new user-defined MCP server."""
    try:
        entry = marketplace.add_server(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return entry.model_dump()


@router.delete("/servers/{id}", response_model=Dict[str, bool])
async def remove_server(
    id: str,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_admin),
):
    """Remove a user-defined MCP server."""
    try:
        removed = marketplace.remove_server(id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{id}' not found",
        )
    return {"removed": True}


@router.post("/servers/{id}/install", response_model=Dict[str, Any])
async def install_server(
    id: str,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_admin),
):
    """Install a stdio MCP server into an isolated venv."""
    try:
        entry = await marketplace.install_server(id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return entry.model_dump()


@router.post("/servers/{id}/enable", response_model=Dict[str, Any])
async def enable_server(
    id: str,
    request: Request,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_admin),
):
    """Enable an MCP server and register its tools."""
    try:
        entry = await marketplace.enable_server(id, request.app.state.tool_registry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return entry.model_dump()


@router.post("/servers/{id}/disable", response_model=Dict[str, Any])
async def disable_server(
    id: str,
    request: Request,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_admin),
):
    """Disable an MCP server and unregister its tools."""
    try:
        entry = await marketplace.disable_server(id, request.app.state.tool_registry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return entry.model_dump()


@router.get("/servers/{id}/tools", response_model=Dict[str, Any])
async def list_server_tools(
    id: str,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_auth),
):
    """Return the cached tool list for a server."""
    entry = marketplace.get_server(id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{id}' not found",
        )
    return {"id": id, "tools": entry.tools}


@router.post("/servers/{id}/health", response_model=Dict[str, Any])
async def health_check(
    id: str,
    marketplace: MCPMarketplace = Depends(_marketplace),
    _user_id: str = Depends(require_auth),
):
    """Connect to a server and return its current tool list / error."""
    try:
        return await marketplace.health_check(id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
