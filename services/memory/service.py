"""
Memory Service - Jason Memory DB for personal context
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("jarvis.memory")

# Try to import optional dependencies
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("Chroma not available - vector search disabled")

try:
    from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.warning("SQLAlchemy not available")


Base = declarative_base()


class UserProfile(Base):
    """User profile table"""
    __tablename__ = "user_profile"
    
    id = Column(String, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value_text = Column(Text)
    confidence = Column(Integer, default=1)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Playbook(Base):
    """Playbook table"""
    __tablename__ = "playbooks"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    steps_json = Column(Text)
    tags = Column(JSON, default=list)


class Episode(Base):
    """Episode table"""
    __tablename__ = "episodes"
    
    id = Column(String, primary_key=True)
    source = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    summary = Column(Text)
    raw_ref = Column(Text)


class MemoryService:
    """Memory service with vector search and structured storage"""
    
    def __init__(self):
        self.config = None
        self._chroma_client = None
        self._collection = None
        self._engine = None
        self._Session = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize memory service"""
        if self._initialized:
            return
        
        from core.config import get_config
        self.config = get_config().memory
        
        # Initialize vector DB
        if CHROMA_AVAILABLE:
            try:
                self._chroma_client = chromadb.PersistentClient(
                    path=self.config.chroma_persist_directory
                )
                self._collection = self._chroma_client.get_or_create_collection(
                    name="memory_chunks",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Chroma vector DB initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Chroma: {e}")
        
        # Initialize SQL database
        if SQLALCHEMY_AVAILABLE:
            try:
                if self.config.db_type == "postgres":
                    db_url = f"postgresql://{self.config.postgres_user}:{self.config.postgres_password}@{self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_db}"
                else:
                    db_url = "sqlite:///./data/jarvis.db"
                
                self._engine = create_engine(db_url)
                Base.metadata.create_all(self._engine)
                self._Session = sessionmaker(bind=self._engine)
                logger.info(f"SQL database initialized: {self.config.db_type}")
            except Exception as e:
                logger.error(f"Failed to initialize SQL database: {e}")
        
        self._initialized = True
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memory using vector similarity
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters
            memory_type: Filter by memory type
            
        Returns:
            List of memory entries
        """
        await self.initialize()
        
        results = []
        
        # Vector search
        if self._collection is not None:
            try:
                # Build where filter
                where = {}
                if memory_type:
                    where["type"] = memory_type
                if filters:
                    where.update(filters)
                
                query_results = self._collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where if where else None
                )
                
                if query_results["ids"] and query_results["ids"][0]:
                    for i, mem_id in enumerate(query_results["ids"][0]):
                        results.append({
                            "id": mem_id,
                            "text": query_results["documents"][0][i],
                            "type": query_results["metadatas"][0][i].get("type", "unknown"),
                            "score": 1 - query_results["distances"][0][i] if "distances" in query_results else None,
                            "metadata": query_results["metadatas"][0][i]
                        })
            except Exception as e:
                logger.error(f"Vector search error: {e}")
        
        return results
    
    async def update(
        self,
        memory_type: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: int = 5
    ) -> str:
        """
        Add or update memory entry
        
        Args:
            memory_type: Type of memory (preference, fact, workflow, insight)
            text: Memory text
            metadata: Additional metadata
            importance: Importance level 1-10
            
        Returns:
            Memory entry ID
        """
        await self.initialize()
        
        entry_id = str(uuid.uuid4())
        meta = metadata or {}
        meta["type"] = memory_type
        meta["importance"] = importance
        meta["created_at"] = datetime.now(timezone.utc).isoformat()
        
        # Add to vector DB
        if self._collection is not None:
            try:
                self._collection.add(
                    ids=[entry_id],
                    documents=[text],
                    metadatas=[meta]
                )
                logger.info(f"Added memory entry: {entry_id}")
            except Exception as e:
                logger.error(f"Failed to add to vector DB: {e}")
        
        # Add to SQL DB
        if self._Session is not None:
            try:
                session = self._Session()
                episode = Episode(
                    id=entry_id,
                    source="jarvis",
                    summary=text,
                    raw_ref=json.dumps(meta)
                )
                session.add(episode)
                session.commit()
                session.close()
            except Exception as e:
                logger.error(f"Failed to add to SQL DB: {e}")
        
        return entry_id
    
    async def get_profile(self) -> List[Dict[str, Any]]:
        """
        Get user profile from memory
        
        Returns:
            List of profile entries
        """
        await self.initialize()
        
        profile = []
        
        if self._Session is not None:
            try:
                session = self._Session()
                profiles = session.query(UserProfile).all()
                
                for p in profiles:
                    profile.append({
                        "id": p.id,
                        "key": p.key,
                        "value_text": p.value_text,
                        "confidence": p.confidence,
                        "last_updated": p.last_updated.isoformat() if p.last_updated else None
                    })
                
                session.close()
            except Exception as e:
                logger.error(f"Failed to get profile: {e}")
        
        # Also search for preferences in vector DB
        if self._collection is not None:
            try:
                prefs = self._collection.get(where={"type": "preference"})
                if prefs["ids"]:
                    for i, mem_id in enumerate(prefs["ids"]):
                        profile.append({
                            "id": mem_id,
                            "key": "preference",
                            "value_text": prefs["documents"][i],
                            "source": "memory"
                        })
            except Exception as e:
                logger.error(f"Failed to get preferences: {e}")
        
        return profile
    
    async def get_playbooks(self) -> List[Dict[str, Any]]:
        """
        Get all playbooks
        
        Returns:
            List of playbook entries
        """
        await self.initialize()
        
        playbooks = []
        
        if self._Session is not None:
            try:
                session = self._Session()
                playbook_list = session.query(Playbook).all()
                
                for p in playbook_list:
                    playbooks.append({
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "steps": json.loads(p.steps_json) if p.steps_json else [],
                        "tags": p.tags or []
                    })
                
                session.close()
            except Exception as e:
                logger.error(f"Failed to get playbooks: {e}")
        
        return playbooks
    
    async def add_profile_entry(self, key: str, value: str, confidence: int = 1):
        """Add profile entry"""
        await self.initialize()
        
        if self._Session is not None:
            try:
                session = self._Session()
                
                # Check if exists
                existing = session.query(UserProfile).filter_by(key=key).first()
                
                if existing:
                    existing.value_text = value
                    existing.confidence = confidence
                    existing.last_updated = datetime.now(timezone.utc)
                else:
                    profile = UserProfile(
                        id=str(uuid.uuid4()),
                        key=key,
                        value_text=value,
                        confidence=confidence,
                        last_updated=datetime.now(timezone.utc)
                    )
                    session.add(profile)
                
                session.commit()
                session.close()
                logger.info(f"Added profile entry: {key}")
            except Exception as e:
                logger.error(f"Failed to add profile entry: {e}")
    
    async def add_playbook(self, name: str, description: str, steps: List[Dict], tags: List[str] = None):
        """Add playbook"""
        await self.initialize()
        
        if self._Session is not None:
            try:
                session = self._Session()
                playbook = Playbook(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    steps_json=json.dumps(steps),
                    tags=tags or []
                )
                session.add(playbook)
                session.commit()
                session.close()
                logger.info(f"Added playbook: {name}")
            except Exception as e:
                logger.error(f"Failed to add playbook: {e}")


# Singleton instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get memory service singleton"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
