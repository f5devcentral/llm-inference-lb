"""
API server module
Provides HTTP interface for optimal member selection
"""

import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
import uvicorn
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from utils.exceptions import SchedulingError, InvalidRequestError
from core.scheduler import Scheduler


class ScheduleRequest(BaseModel):
    """Schedule request model"""
    pool_name: str = Field(..., description="Pool name")
    partition: str = Field(..., description="Partition name")
    members: List[str] = Field(..., description="Candidate member list, format: [\"ip:port\", ...]")


class ScheduleResponse(BaseModel):
    """Schedule response model"""
    selected_member: str = Field(..., description="Selected member, format: ip:port or none")


class PoolStatusResponse(BaseModel):
    """Pool status response model"""
    name: str
    partition: str
    engine_type: str
    member_count: int
    members: List[Dict]


class APIServer:
    """API server"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.logger = get_logger()
        self.scheduler = Scheduler()
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application"""
        app = FastAPI(
            title="F5 LLM Inference Gateway Scheduler",
            description="F5 LLM Inference Gateway Scheduler API",
            version="1.0.0"
        )
        
        # Register routes
        self._register_routes(app)
        
        return app
    
    def _register_routes(self, app: FastAPI):
        """Register API routes"""
        
        @app.post("/scheduler/select", response_class=PlainTextResponse)
        async def select_optimal_member(request: ScheduleRequest):
            """Select optimal member"""
            try:
                # Validate request parameters
                if not request.pool_name:
                    raise InvalidRequestError("pool_name cannot be empty")
                if not request.partition:
                    raise InvalidRequestError("partition cannot be empty")
                if not request.members:
                    raise InvalidRequestError("members cannot be empty")
                
                self.logger.info(
                    f"Received schedule request: pool={request.pool_name}, "
                    f"partition={request.partition}, members={request.members}"
                )
                
                # Call scheduler to select optimal member
                selected = await self.scheduler.select_optimal_member(
                    request.pool_name,
                    request.partition,
                    request.members
                )
                
                result = selected if selected else "none"
                
                self.logger.info(f"Schedule result: {result}")
                
                return result
                
            except InvalidRequestError as e:
                self.logger.warning(f"Invalid Request: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except SchedulingError as e:
                self.logger.error(f"Scheduling Error: {e}")
                raise HTTPException(status_code=500, detail=f"Scheduling Failed: {e}")
            except Exception as e:
                self.logger.error(f"API Exception: {e}")
                raise HTTPException(status_code=500, detail="Internal Server Error")
        
        @app.get("/pools/{pool_name}/{partition}/status", response_model=PoolStatusResponse)
        async def get_pool_status(pool_name: str, partition: str):
            """Get Pool status"""
            try:
                status = self.scheduler.get_pool_status(pool_name, partition)
                if not status:
                    raise HTTPException(status_code=404, detail=f"Pool {pool_name}:{partition} does not exist")
                
                return PoolStatusResponse(**status)
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Get Pool status exception: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @app.get("/pools/status")
        async def get_all_pools_status():
            """Get all Pool status"""
            try:
                status_list = self.scheduler.get_all_pools_status()
                return {"pools": status_list}
                
            except Exception as e:
                self.logger.error(f"Get all Pool status exception: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @app.get("/health")
        async def health_check():
            """Health check"""
            return {"status": "healthy", "message": "Scheduler running normally"}
        
        @app.post("/pools/{pool_name}/{partition}/simulate")
        async def simulate_selection(
            pool_name: str, 
            partition: str, 
            request: ScheduleRequest,
            iterations: int = 100
        ):
            """Simulate selection process (for testing)"""
            try:
                results = await self.scheduler.simulate_selection(
                    pool_name, partition, request.members, iterations
                )
                return {"results": results, "iterations": iterations}
                
            except Exception as e:
                self.logger.error(f"Simulate selection exception: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @app.post("/pools/{pool_name}/{partition}/analyze")
        async def analyze_selection_accuracy(
            pool_name: str, 
            partition: str, 
            request: ScheduleRequest,
            iterations: int = 1000
        ):
            """Advanced probability analysis - Detailed analysis of selection accuracy and bias"""
            try:
                analysis = await self.scheduler.analyze_selection_accuracy(
                    pool_name, partition, request.members, iterations
                )
                return analysis
                
            except Exception as e:
                self.logger.error(f"Probability analysis exception: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
    
    async def start(self):
        """Start API server"""
        self.logger.info(f"Starting API server: {self.host}:{self.port}")
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self):
        """Run API server synchronously"""
        self.logger.info(f"Starting API server: {self.host}:{self.port}")
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False
        )


def create_api_server(host: str = "0.0.0.0", port: int = 8080) -> APIServer:
    """Create API server instance"""
    return APIServer(host, port) 