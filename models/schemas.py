"""
Pydantic schemas for Jarvis Desktop Assistant
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ActionType(str, Enum):
    """OS Operator action types"""
    MOVE_MOUSE = "move_mouse"
    CLICK = "click"
    SCROLL = "scroll"
    TYPE_TEXT = "type_text"
    HOTKEY = "hotkey"
    KEY = "key"
    OPEN_APP = "open_app"
    FOCUS_APP = "focus_app"
    SCREENSHOT = "screenshot"
    GET_ACTIVE_WINDOW = "get_active_window"


class MouseButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


# Voice Models
class TranscriptRequest(BaseModel):
    """Request to transcribe audio"""
    session_id: str
    audio_data: Optional[bytes] = None
    audio_path: Optional[str] = None


class TranscriptResponse(BaseModel):
    """Response with transcribed text"""
    text: str
    session_id: str
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SpeakRequest(BaseModel):
    """Request to synthesize speech"""
    text: str
    session_id: str
    voice_id: Optional[str] = None
    rate: int = 200
    volume: int = 100


class SpeakResponse(BaseModel):
    """Response from speech synthesis"""
    success: bool
    session_id: str
    duration: Optional[float] = None


# Memory Models
class MemoryType(str, Enum):
    """Types of memory entries"""
    PREFERENCE = "preference"
    FACT = "fact"
    WORKFLOW = "workflow"
    INSIGHT = "insight"
    EPISODE = "episode"


class MemorySearchRequest(BaseModel):
    """Request to search memory"""
    query: str
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None
    memory_type: Optional[MemoryType] = None


class MemoryEntry(BaseModel):
    """A single memory entry"""
    id: Optional[str] = None
    type: MemoryType
    text: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    importance: int = Field(ge=1, le=10, default=5)
    source: Optional[str] = None
    timestamp: Optional[datetime] = None


class MemoryUpdateRequest(BaseModel):
    """Request to update/add memory"""
    type: MemoryType
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    importance: int = Field(ge=1, le=10, default=5)


class MemoryProfileResponse(BaseModel):
    """User profile from memory"""
    id: str
    key: str
    value_text: str
    confidence: float = 1.0
    last_updated: datetime


class Playbook(BaseModel):
    """A procedural playbook"""
    id: Optional[str] = None
    name: str
    description: str
    steps: List[Dict[str, Any]]
    tags: List[str] = Field(default_factory=list)


# OS Operator Models
class MouseMoveAction(BaseModel):
    """Move mouse to position"""
    type: Literal[ActionType.MOVE_MOUSE] = ActionType.MOVE_MOUSE
    x: int
    y: int
    duration: float = 0.0


class ClickAction(BaseModel):
    """Click mouse button"""
    type: Literal[ActionType.CLICK] = ActionType.CLICK
    button: MouseButton = MouseButton.LEFT
    clicks: int = 1
    x: Optional[int] = None
    y: Optional[int] = None


class ScrollAction(BaseModel):
    """Scroll mouse"""
    type: Literal[ActionType.SCROLL] = ActionType.SCROLL
    amount: int
    x: Optional[int] = None
    y: Optional[int] = None


class TypeTextAction(BaseModel):
    """Type text"""
    type: Literal[ActionType.TYPE_TEXT] = ActionType.TYPE_TEXT
    text: str
    interval: float = 0.0


class HotkeyAction(BaseModel):
    """Press hotkey combination"""
    type: Literal[ActionType.HOTKEY] = ActionType.HOTKEY
    keys: List[str]


class KeyAction(BaseModel):
    """Press single key"""
    type: Literal[ActionType.KEY] = ActionType.KEY
    key: str


class OpenAppAction(BaseModel):
    """Open application"""
    type: Literal[ActionType.OPEN_APP] = ActionType.OPEN_APP
    app_name: str
    arguments: Optional[str] = None


class FocusAppAction(BaseModel):
    """Focus existing application"""
    type: Literal[ActionType.FOCUS_APP] = ActionType.FOCUS_APP
    app_name: str


class ScreenshotAction(BaseModel):
    """Take screenshot"""
    type: Literal[ActionType.SCREENSHOT] = ActionType.SCREENSHOT
    region: Optional[Dict[str, int]] = None
    save_path: Optional[str] = None


class GetActiveWindowAction(BaseModel):
    """Get active window info"""
    type: Literal[ActionType.GET_ACTIVE_WINDOW] = ActionType.GET_ACTIVE_WINDOW


# Union type for all actions
OSAction = (
    MouseMoveAction | ClickAction | ScrollAction | TypeTextAction |
    HotkeyAction | KeyAction | OpenAppAction | FocusAppAction |
    ScreenshotAction | GetActiveWindowAction
)


class ExecuteActionsRequest(BaseModel):
    """Request to execute multiple OS actions"""
    actions: List[OSAction]
    session_id: str


class ExecuteActionsResponse(BaseModel):
    """Response from action execution"""
    success: bool
    results: List[Dict[str, Any]]
    session_id: str


# Assistant Core Models
class SessionState(BaseModel):
    """Conversation session state"""
    session_id: str
    recent_messages: List[Dict[str, str]] = Field(default_factory=list)
    current_app: Optional[str] = None
    current_task: Optional[str] = None
    pending_confirmation: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)


class ToolCall(BaseModel):
    """A tool call from the LLM"""
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """LLM response with tool calls"""
    reply: str
    thoughts: Optional[str] = None
    plans: Optional[List[str]] = None
    actions: List[ToolCall] = Field(default_factory=list)
    requires_confirmation: bool = False


class QueryRequest(BaseModel):
    """Request to assistant core"""
    session_id: str
    text: str
    mode: Literal["voice", "text", "action"] = "voice"
    include_actions: bool = True


class QueryResponse(BaseModel):
    """Response from assistant core"""
    reply_text: str
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    memory_updates: List[MemoryEntry] = Field(default_factory=list)
    requires_confirmation: bool = False
    session_id: str


# Memory Distillation Models
class ChatChunk(BaseModel):
    """A chunk of conversation for distillation"""
    messages: List[Dict[str, str]]
    source: str
    timestamp: Optional[datetime] = None


class DistillationResult(BaseModel):
    """Result from memory distillation"""
    memories: List[MemoryEntry]
    profile_updates: List[Dict[str, str]] = Field(default_factory=list)
    playbooks: List[Playbook] = Field(default_factory=list)
