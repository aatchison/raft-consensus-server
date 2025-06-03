"""
Raft HTTP Server

Author: OpenHands AI Assistant
Created: 2025

This module provides an HTTP API wrapper around the Raft consensus node.
It exposes both the internal Raft RPCs (RequestVote, AppendEntries) and
client-facing APIs for interacting with the replicated state machine.

Key features:
- RESTful API for client operations (GET, SET, DELETE)
- Internal Raft RPC endpoints for cluster communication
- Real-time status monitoring and cluster health
- CORS support for web-based clients
- Automatic request routing to leader nodes

The server provides a simple key-value store interface backed by the
Raft consensus algorithm, ensuring strong consistency across the cluster.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import asyncio
import logging

from raft_node import RaftNode, RequestVoteRequest, RequestVoteResponse, AppendEntriesRequest, AppendEntriesResponse
from log_entry import LogEntry
from config import RaftConfig


# Pydantic models for API
class SetValueRequest(BaseModel):
    key: str
    value: Any


class DeleteValueRequest(BaseModel):
    key: str


class GetValueResponse(BaseModel):
    key: str
    value: Any
    found: bool


class StatusResponse(BaseModel):
    node_id: str
    state: str
    current_term: int
    voted_for: Optional[str]
    commit_index: int
    last_applied: int
    log_size: int
    state_machine: Dict[str, Any]


class RaftServer:
    """HTTP server wrapper for Raft node."""
    
    def __init__(self, config: RaftConfig):
        self.config = config
        self.raft_node = RaftNode(config)
        self.app = FastAPI(title=f"Raft Server - {config.node_id}")
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._setup_routes()
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"raft_server.{config.node_id}")
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.on_event("startup")
        async def startup():
            await self.raft_node.start()
            self.logger.info(f"Raft server {self.config.node_id} started on {self.config.host}:{self.config.port}")
        
        @self.app.on_event("shutdown")
        async def shutdown():
            await self.raft_node.stop()
            self.logger.info(f"Raft server {self.config.node_id} stopped")
        
        # Health check
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "node_id": self.config.node_id}
        
        # Raft RPC endpoints
        @self.app.post("/raft/request_vote")
        async def request_vote(request_data: dict):
            try:
                request = RequestVoteRequest(**request_data)
                response = await self.raft_node.handle_request_vote(request)
                return response.__dict__
            except Exception as e:
                self.logger.error(f"Error handling request_vote: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/raft/append_entries")
        async def append_entries(request_data: dict):
            try:
                # Convert entries back to LogEntry objects
                entries = [LogEntry.from_dict(entry_dict) for entry_dict in request_data.get('entries', [])]
                request = AppendEntriesRequest(
                    term=request_data['term'],
                    leader_id=request_data['leader_id'],
                    prev_log_index=request_data['prev_log_index'],
                    prev_log_term=request_data['prev_log_term'],
                    entries=entries,
                    leader_commit=request_data['leader_commit']
                )
                response = await self.raft_node.handle_append_entries(request)
                return response.__dict__
            except Exception as e:
                self.logger.error(f"Error handling append_entries: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Client API endpoints
        @self.app.post("/api/set")
        async def set_value(request: SetValueRequest):
            """Set a key-value pair."""
            if self.raft_node.state.value != "leader":
                raise HTTPException(
                    status_code=400, 
                    detail=f"Not the leader. Current state: {self.raft_node.state.value}"
                )
            
            command = {
                "type": "set",
                "key": request.key,
                "value": request.value
            }
            
            success = await self.raft_node.append_entry(command)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to append entry")
            
            return {"success": True, "message": f"Set {request.key}={request.value}"}
        
        @self.app.post("/api/delete")
        async def delete_value(request: DeleteValueRequest):
            """Delete a key."""
            if self.raft_node.state.value != "leader":
                raise HTTPException(
                    status_code=400, 
                    detail=f"Not the leader. Current state: {self.raft_node.state.value}"
                )
            
            command = {
                "type": "delete",
                "key": request.key
            }
            
            success = await self.raft_node.append_entry(command)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to append entry")
            
            return {"success": True, "message": f"Deleted {request.key}"}
        
        @self.app.get("/api/get/{key}")
        async def get_value(key: str):
            """Get a value by key."""
            value = self.raft_node.get_state_machine_value(key)
            return GetValueResponse(
                key=key,
                value=value,
                found=value is not None
            )
        
        @self.app.get("/api/status")
        async def get_status():
            """Get the current status of the node."""
            status = self.raft_node.get_status()
            return StatusResponse(**status)
        
        @self.app.get("/api/state_machine")
        async def get_state_machine():
            """Get the entire state machine."""
            return {"state_machine": self.raft_node.state_machine}
        
        @self.app.get("/")
        async def root():
            """Root endpoint with basic information."""
            return {
                "message": f"Raft Server - Node {self.config.node_id}",
                "state": self.raft_node.state.value,
                "term": self.raft_node.current_term,
                "endpoints": {
                    "health": "/health",
                    "status": "/api/status",
                    "set_value": "/api/set",
                    "get_value": "/api/get/{key}",
                    "delete_value": "/api/delete",
                    "state_machine": "/api/state_machine"
                }
            }


async def run_server(config: RaftConfig):
    """Run the Raft server."""
    import uvicorn
    
    server = RaftServer(config)
    
    uvicorn_config = uvicorn.Config(
        server.app,
        host=config.host,
        port=config.port,
        log_level="info"
    )
    
    server_instance = uvicorn.Server(uvicorn_config)
    await server_instance.serve()