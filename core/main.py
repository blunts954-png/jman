"""
Jarvis Desktop Assistant - Main FastAPI Application
"""
import os
import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.config import load_config, get_config
from models.schemas import (
    TranscriptRequest, TranscriptResponse,
    SpeakRequest, SpeakResponse,
    MemorySearchRequest, MemoryUpdateRequest, MemoryEntry,
    QueryRequest, QueryResponse,
    ExecuteActionsRequest, ExecuteActionsResponse,
)

# Configure logging from environment variable
LOG_LEVEL = os.getenv("JARVIS_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv(
    "JARVIS_LOG_FORMAT",
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT
)
logger = logging.getLogger("jarvis")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Starting Jarvis Desktop Assistant...")
    
    # Load configuration
    config = load_config()
    logger.info(f"Loaded configuration: {config.name} v{config.version}")
    
    # Create data directories
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    (data_dir / "screenshots").mkdir(exist_ok=True)
    (data_dir / "chroma").mkdir(exist_ok=True)
    
    # Initialize services
    try:
        from services.memory.service import MemoryService
        memory_service = MemoryService()
        app.state.memory_service = memory_service
        logger.info("Memory service initialized")
    except Exception as e:
        logger.warning(f"Memory service not initialized: {e}")
        app.state.memory_service = None
    
    try:
        from services.voice.service import VoiceService
        voice_service = VoiceService()
        app.state.voice_service = voice_service
        logger.info("Voice service initialized")
    except Exception as e:
        logger.warning(f"Voice service not initialized: {e}")
        app.state.voice_service = None
    
    try:
        from services.os_operator.service import OSOperator
        os_operator = OSOperator()
        app.state.os_operator = os_operator
        logger.info("OS Operator initialized")
    except Exception as e:
        logger.warning(f"OS Operator not initialized: {e}")
        app.state.os_operator = None
    
    try:
        from services.assistant.core import AssistantCore
        assistant_core = AssistantCore()
        app.state.assistant_core = assistant_core
        logger.info("Assistant Core initialized")
    except Exception as e:
        logger.warning(f"Assistant Core not initialized: {e}")
        app.state.assistant_core = None
    
    yield
    
    logger.info("Shutting down Jarvis...")


# Create FastAPI app
app = FastAPI(
    title="Jarvis Desktop Assistant",
    description="Always-on desktop assistant with voice, memory, and OS control",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "jarvis",
        "version": get_config().version
    }


# Voice Service Routes
@app.post("/voice/transcript", response_model=TranscriptResponse)
async def transcript_audio(request: TranscriptRequest):
    """Transcribe audio to text using STT"""
    voice_service = app.state.voice_service
    
    if voice_service is None:
        raise HTTPException(status_code=503, detail="Voice service not available")
    
    try:
        text = await voice_service.transcribe(
            audio_data=request.audio_data,
            audio_path=request.audio_path
        )
        
        return TranscriptResponse(
            text=text,
            session_id=request.session_id,
            confidence=1.0
        )
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice/speak", response_model=SpeakResponse)
async def speak_text(request: SpeakRequest):
    """Synthesize speech from text using TTS"""
    voice_service = app.state.voice_service
    
    if voice_service is None:
        raise HTTPException(status_code=503, detail="Voice service not available")
    
    try:
        duration = await voice_service.speak(
            text=request.text,
            voice_id=request.voice_id,
            rate=request.rate,
            volume=request.volume
        )
        
        return SpeakResponse(
            success=True,
            session_id=request.session_id,
            duration=duration
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Memory Service Routes
@app.post("/memory/search")
async def search_memory(request: MemorySearchRequest):
    """Search memory for relevant context"""
    memory_service = app.state.memory_service
    
    if memory_service is None:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        results = await memory_service.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            memory_type=request.memory_type
        )
        
        return {"results": results}
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/update")
async def update_memory(request: MemoryUpdateRequest):
    """Add new memory entry"""
    memory_service = app.state.memory_service
    
    if memory_service is None:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        entry_id = await memory_service.update(
            memory_type=request.type,
            text=request.text,
            metadata=request.metadata,
            importance=request.importance
        )
        
        return {"id": entry_id, "success": True}
    except Exception as e:
        logger.error(f"Memory update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/profile")
async def get_profile():
    """Get user profile from memory"""
    memory_service = app.state.memory_service
    
    if memory_service is None:
        raise HTTPException(status_code=503, detail="Memory service not available")
    
    try:
        profile = await memory_service.get_profile()
        return {"profile": profile}
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# OS Operator Routes
@app.post("/os/execute_actions", response_model=ExecuteActionsResponse)
async def execute_actions(request: ExecuteActionsRequest):
    """Execute OS actions (mouse, keyboard, apps)"""
    os_operator = app.state.os_operator
    
    if os_operator is None:
        raise HTTPException(status_code=503, detail="OS Operator not available")
    
    try:
        results = await os_operator.execute_actions(request.actions)
        
        return ExecuteActionsResponse(
            success=all(r.get("success", False) for r in results),
            results=results,
            session_id=request.session_id
        )
    except Exception as e:
        logger.error(f"Action execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Assistant Core Routes
@app.post("/assistant/query", response_model=QueryResponse)
async def query_assistant(request: QueryRequest):
    """Process user query through assistant core"""
    assistant_core = app.state.assistant_core
    
    if assistant_core is None:
        raise HTTPException(status_code=503, detail="Assistant Core not available")
    
    try:
        response = await assistant_core.process_query(
            session_id=request.session_id,
            text=request.text,
            mode=request.mode,
            include_actions=request.include_actions
        )
        
        return response
    except Exception as e:
        logger.error(f"Assistant query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Session management
@app.post("/session/create")
async def create_session():
    """Create a new conversation session"""
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


# Run the application
if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    uvicorn.run(
        "core.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug
    )
