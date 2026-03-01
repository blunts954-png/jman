"""
Assistant Core - Jarvis Brain (LLM orchestrator + tool router)
"""
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("jarvis.assistant")

# Try to import optional dependencies
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available")


# System prompt for Jarvis personality
SYSTEM_PROMPT = """You are Jarvis, a brutal, analytical desktop assistant.

PERSONALITY:
- Direct, no fluff, highly analytical
- Challenge self-sabotage and irrational thinking
- Prefer efficiency over pleasantries

CONSTRAINTS:
- Never perform irreversible actions (deletes, sends emails, moves money) without explicit double confirmation
- Minimize unnecessary clicks/typing
- Always use tools when appropriate

MEMORY:
- Always call memory.search for complex planning, emotional/behavioral patterns
- Include relevant memories in your context
- Update memory when new preferences or insights emerge

OUTPUT FORMAT:
Always return valid JSON with this schema:
{
  "reply": "natural language response to user",
  "thoughts": "your reasoning about the request",
  "plans": ["high-level steps to accomplish goal"],
  "actions": [
    {
      "tool": "memory.search | memory.update | os.execute_actions",
      "args": {}
    }
  ],
  "requires_confirmation": false
}

IMPORTANT: Your response must be valid JSON only, no additional text."""


# Tool definitions for LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": "Search memory for relevant context, preferences, or past experiences",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_update",
            "description": "Add or update a memory entry",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {"type": "string", "description": "Type: preference, fact, workflow, insight"},
                    "text": {"type": "string", "description": "Memory text"},
                    "metadata": {"type": "object", "description": "Additional metadata"},
                    "importance": {"type": "integer", "description": "Importance 1-10"}
                },
                "required": ["memory_type", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "os_execute_actions",
            "description": "Execute OS actions (mouse, keyboard, apps)",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "description": "List of actions to execute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "button": {"type": "string"},
                                "clicks": {"type": "integer"},
                                "amount": {"type": "integer"},
                                "text": {"type": "string"},
                                "keys": {"type": "array", "items": {"type": "string"}},
                                "key": {"type": "string"},
                                "app_name": {"type": "string"},
                                "interval": {"type": "number"}
                            }
                        }
                    }
                },
                "required": ["actions"]
            }
        }
    }
]


class SessionStateManager:
    """Manages conversation session states"""
    
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def get_or_create(self, session_id: str) -> Dict[str, Any]:
        """Get or create session state"""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "recent_messages": [],
                "current_app": None,
                "current_task": None,
                "pending_confirmation": None
            }
        return self._sessions[session_id]
    
    def update(self, session_id: str, **kwargs):
        """Update session state"""
        if session_id in self._sessions:
            self._sessions[session_id].update(kwargs)
    
    def add_message(self, session_id: str, role: str, content: str):
        """Add message to session history"""
        session = self.get_or_create(session_id)
        session["recent_messages"].append({"role": role, "content": content})
        
        # Keep only last 20 messages
        if len(session["recent_messages"]) > 20:
            session["recent_messages"] = session["recent_messages"][-20:]


class AssistantCore:
    """Main assistant orchestrator"""
    
    def __init__(self):
        self._llm_client = None
        self._sessions = SessionStateManager()
        self._initialized = False
    
    async def initialize(self):
        """Initialize assistant core"""
        if self._initialized:
            return
        
        from core.config import get_config
        config = get_config().llm
        
        if OPENAI_AVAILABLE and config.api_key:
            self._llm_client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url if config.base_url != "http://localhost:11434" else None
            )
            self._model = config.model
            self._temperature = config.temperature
            self._max_tokens = config.max_tokens
            self._tools_enabled = config.tools_enabled
            logger.info(f"LLM initialized: {config.provider}/{config.model}")
        
        self._initialized = True
    
    async def process_query(
        self,
        session_id: str,
        text: str,
        mode: str = "voice",
        include_actions: bool = True
    ) -> Dict[str, Any]:
        """
        Process user query through the assistant
        
        Args:
            session_id: Session ID
            text: User input text
            mode: Input mode (voice, text, action)
            include_actions: Whether to execute actions
            
        Returns:
            Response with reply and actions
        """
        await self.initialize()
        
        # Get or create session
        session = self._sessions.get_or_create(session_id)
        
        # Add user message to history
        self._sessions.add_message(session_id, "user", text)
        
        # Get memory context
        memory_results = []
        try:
            from services.memory.service import get_memory_service
            memory_service = get_memory_service()
            
            # Search memory for relevant context
            if any(keyword in text.lower() for keyword in ["prefer", "like", "hate", "always", "never", "remember"]):
                memory_results = await memory_service.search(text, top_k=5)
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
        
        # Build context for LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add memory context if available
        if memory_results:
            memory_context = "Relevant memories:\n"
            for mem in memory_results:
                memory_context += f"- [{mem.get('type', 'unknown')}]: {mem.get('text', '')}\n"
            messages.append({"role": "system", "content": memory_context})
        
        # Add conversation history
        messages.extend(session["recent_messages"][-10:])
        

        messages.append({"role": "user", "content": text})
        
        # Call LLM
        response_text = ""
        actions = []
        requires_confirmation = False
        
        if self._llm_client and self._tools_enabled:
            try:
                # Make LLM call with tools
                response = await self._llm_client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                    tools=TOOLS,
                    tool_choice="auto"
                )
                
                # Parse response
                response_message = response.choices[0].message
                
                # Handle tool calls
                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        
                        logger.info(f"LLM called tool: {tool_name}")
                        
                        # Execute tool
                        if tool_name == "memory_search":
                            result = await self._execute_memory_search(tool_args)
                            actions.append({"tool": "memory_search", "result": result})
                        
                        elif tool_name == "memory_update":
                            result = await self._execute_memory_update(tool_args)
                            actions.append({"tool": "memory_update", "result": result})
                        
                        elif tool_name == "os_execute_actions":
                            # Check if confirmation needed
                            if self._check_destructive_action(tool_args.get("actions", [])):
                                requires_confirmation = True
                                session["pending_confirmation"] = json.dumps(tool_args)
                            else:
                                result = await self._execute_os_actions(tool_args.get("actions", []))
                                actions.append({"tool": "os_execute_actions", "result": result})
                
                # Get text response
                response_text = response_message.content or ""
                
            except Exception as e:
                logger.error(f"LLM call error: {e}")
                response_text = "I encountered an error processing your request."
        else:
            # Fallback response without LLM
            response_text = await self._fallback_response(text)
        
        # Parse JSON from response if present
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
                parsed = json.loads(json_str)
                response_text = parsed.get("reply", response_text)
        except Exception as e:
            logger.debug(f"Could not parse JSON from response: {e}")
        
        # Add assistant response to history
        self._sessions.add_message(session_id, "assistant", response_text)
        
        return {
            "reply_text": response_text,
            "actions": actions,
            "memory_updates": [],
            "requires_confirmation": requires_confirmation,
            "session_id": session_id
        }
    
    async def _execute_memory_search(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute memory search tool"""
        try:
            from services.memory.service import get_memory_service
            memory_service = get_memory_service()
            return await memory_service.search(
                query=args.get("query", ""),
                top_k=args.get("top_k", 5)
            )
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []
    
    async def _execute_memory_update(self, args: Dict[str, Any]) -> str:
        """Execute memory update tool"""
        try:
            from services.memory.service import get_memory_service
            memory_service = get_memory_service()
            return await memory_service.update(
                memory_type=args.get("memory_type", "insight"),
                text=args.get("text", ""),
                metadata=args.get("metadata", {}),
                importance=args.get("importance", 5)
            )
        except Exception as e:
            logger.error(f"Memory update error: {e}")
            return ""
    
    async def _execute_os_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute OS actions"""
        try:
            from services.os_operator.service import get_os_operator
            os_operator = get_os_operator()
            return await os_operator.execute_actions(actions)
        except Exception as e:
            logger.error(f"OS actions error: {e}")
            return [{"success": False, "error": str(e)}]
    
    def _check_destructive_action(self, actions: List[Dict[str, Any]]) -> bool:
        """Check if actions are potentially destructive"""
        destructive_types = ["delete", "format", "send_email", "move_money"]
        
        for action in actions:
            action_type = action.get("type", "")
            if any(d in action_type.lower() for d in destructive_types):
                return True
        
        return False
    
    async def _fallback_response(self, text: str) -> str:
        """Generate fallback response without LLM"""
        text_lower = text.lower()
        
        if "open" in text_lower:
            # Extract app name
            words = text.split()
            if len(words) > 1:
                app = words[-1]
                return f"Opening {app}..."
        
        if "type" in text_lower or "write" in text_lower:
            return "What would you like me to type?"
        
        if "click" in text_lower:
            return "Where would you like me to click?"
        
        return "I understand. How would you like me to proceed?"
    
    async def confirm_action(self, session_id: str) -> Dict[str, Any]:
        """Confirm and execute pending action"""
        session = self._sessions.get_or_create(session_id)
        
        pending = session.get("pending_confirmation")
        if not pending:
            return {"success": False, "error": "No pending confirmation"}
        
        try:
            actions = json.loads(pending)
            result = await self._execute_os_actions(actions.get("actions", []))
            session["pending_confirmation"] = None
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_assistant_core: Optional[AssistantCore] = None


def get_assistant_core() -> AssistantCore:
    """Get assistant core singleton"""
    global _assistant_core
    if _assistant_core is None:
        _assistant_core = AssistantCore()
    return _assistant_core
