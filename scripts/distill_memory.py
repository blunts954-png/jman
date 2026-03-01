"""
Memory Distillation Pipeline
Converts past chat conversations into structured memory entries
"""
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis.distill")


DISTILLATION_PROMPT = """Given this chunk of conversation, extract up to {max_entries} canonical memory entries as JSON objects.

Return a JSON array with objects containing:
- type: "preference", "fact", "workflow", or "insight"
- text: The distilled memory text
- importance: 1-10 rating
- source: The original source (chatgpt, gemini, perplexity, etc.)

Conversation chunk:
{chunk}

Return ONLY valid JSON, no additional text."""


PROFILE_SYNTHESIS_PROMPT = """Given these distilled memories, synthesize a user profile.

Extract key facts, preferences, and behavioral patterns.
Return a JSON object with:
- key: Profile key
- value_text: Profile value
- confidence: 1-10 confidence rating

Memories:
{memories}

Return ONLY valid JSON."""


PLAYBOOK_EXTRACTION_PROMPT = """Given these memories, identify any recurring workflows or procedures that could be playbooks.

Extract structured workflows with:
- name: Playbook name
- description: What it does
- steps: Array of step objects
- tags: Relevant tags

Memories:
{memories}

Return ONLY valid JSON array of playbooks."""


class MemoryDistiller:
    """Memory distillation from chat logs"""
    
    def __init__(self):
        self._llm_client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the distiller"""
        if self._initialized:
            return
        
        from core.config import get_config
        config = get_config().llm
        
        if config.api_key:
            try:
                from openai import AsyncOpenAI
                self._llm_client = AsyncOpenAI(api_key=config.api_key)
                self._model = config.model
                logger.info("Distiller LLM initialized")
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}")
        
        self._initialized = True
    
    async def distill_chat_file(
        self,
        file_path: str,
        source: str,
        chunk_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Distill memory from a chat export file
        
        Args:
            file_path: Path to chat export (JSON or HTML)
            source: Source platform (chatgpt, gemini, etc.)
            chunk_size: Number of messages per chunk
            
        Returns:
            List of distilled memory entries
        """
        await self.initialize()
        
        # Load chat data
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.endswith('.json'):
                chat_data = json.load(f)
            else:
                # HTML - would need parsing
                logger.warning("HTML parsing not implemented")
                return []
        
        # Extract messages
        messages = self._extract_messages(chat_data, source)
        
        # Chunk messages
        chunks = self._create_chunks(messages, chunk_size)
        
        # Process each chunk
        all_memories = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            
            memories = await self._distill_chunk(chunk, source)
            all_memories.extend(memories)
            
            # Small delay between chunks
            await asyncio.sleep(0.5)
        
        return all_memories
    
    def _extract_messages(self, data: Dict[str, Any], source: str) -> List[Dict[str, str]]:
        """Extract messages from chat data"""
        messages = []
        
        if source == "chatgpt":
            # ChatGPT JSON format
            for item in data.get("mapping", {}).values():
                if "message" in item:
                    msg = item["message"]
                    if msg.get("author", {}).get("role"):
                        role = msg["author"]["role"]
                        content = msg.get("content", {})
                        
                        if isinstance(content, dict):
                            parts = content.get("parts", [])
                            text = " ".join(str(p) for p in parts)
                        else:
                            text = str(content)
                        
                        if text:
                            messages.append({"role": role, "content": text})
        
        elif source == "gemini":
            # Gemini format
            for msg in data.get("messages", []):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})
        
        else:
            # Generic format
            messages = data.get("messages", [])
        
        return messages
    
    def _create_chunks(self, messages: List[Dict[str, str]], chunk_size: int) -> List[str]:
        """Create text chunks from messages"""
        chunks = []
        
        for i in range(0, len(messages), chunk_size):
            chunk_messages = messages[i:i + chunk_size]
            chunk_text = "\n".join(
                f"{msg['role']}: {msg['content'][:500]}"  # Limit length
                for msg in chunk_messages
            )
            chunks.append(chunk_text)
        
        return chunks
    
    async def _distill_chunk(self, chunk_text: str, source: str) -> List[Dict[str, Any]]:
        """Distill memories from a single chunk"""
        if not self._llm_client:
            return []
        
        try:
            response = await self._llm_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a memory distillation assistant."},
                    {"role": "user", "content": DISTILLATION_PROMPT.format(
                        max_entries=5,
                        chunk=chunk_text
                    )}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content
            
            # Extract JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            memories = json.loads(result_text)
            
            # Add source to each memory
            for mem in memories:
                mem["source"] = source
                mem["timestamp"] = datetime.utcnow().isoformat()
            
            return memories
            
        except Exception as e:
            logger.error(f"Chunk distillation error: {e}")
            return []
    
    async def synthesize_profile(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Synthesize user profile from memories"""
        if not self._llm_client or not memories:
            return []
        
        try:
            memories_text = json.dumps(memories[:20])  # Limit to 20
            
            response = await self._llm_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a profile synthesis assistant."},
                    {"role": "user", "content": PROFILE_SYNTHESIS_PROMPT.format(
                        memories=memories_text
                    )}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content
            
            # Extract JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            profile = json.loads(result_text)
            return profile if isinstance(profile, list) else [profile]
            
        except Exception as e:
            logger.error(f"Profile synthesis error: {e}")
            return []
    
    async def extract_playbooks(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract playbooks from memories"""
        if not self._llm_client or not memories:
            return []
        
        try:
            memories_text = json.dumps(memories[:20])
            
            response = await self._llm_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a playbook extraction assistant."},
                    {"role": "user", "content": PLAYBOOK_EXTRACTION_PROMPT.format(
                        memories=memories_text
                    )}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content
            
            # Extract JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            playbooks = json.loads(result_text)
            return playbooks if isinstance(playbooks, list) else []
            
        except Exception as e:
            logger.error(f"Playbook extraction error: {e}")
            return []
    
    async def store_memories(self, memories: List[Dict[str, Any]]):
        """Store distilled memories in memory service"""
        try:
            from services.memory.service import get_memory_service
            memory_service = get_memory_service()
            
            for mem in memories:
                await memory_service.update(
                    memory_type=mem.get("type", "insight"),
                    text=mem.get("text", ""),
                    metadata={"source": mem.get("source"), "importance": mem.get("importance", 5)},
                    importance=mem.get("importance", 5)
                )
            
            logger.info(f"Stored {len(memories)} memories")
            
        except Exception as e:
            logger.error(f"Store memories error: {e}")
    
    async def store_profile(self, profile: List[Dict[str, Any]]):
        """Store profile in memory service"""
        try:
            from services.memory.service import get_memory_service
            memory_service = get_memory_service()
            
            for entry in profile:
                await memory_service.add_profile_entry(
                    key=entry.get("key", "unknown"),
                    value=entry.get("value_text", ""),
                    confidence=entry.get("confidence", 5)
                )
            
            logger.info(f"Stored {len(profile)} profile entries")
            
        except Exception as e:
            logger.error(f"Store profile error: {e}")
    
    async def store_playbooks(self, playbooks: List[Dict[str, Any]]):
        """Store playbooks in memory service"""
        try:
            from services.memory.service import get_memory_service
            memory_service = get_memory_service()
            
            for playbook in playbooks:
                await memory_service.add_playbook(
                    name=playbook.get("name", "Unnamed"),
                    description=playbook.get("description", ""),
                    steps=playbook.get("steps", []),
                    tags=playbook.get("tags", [])
                )
            
            logger.info(f"Stored {len(playbooks)} playbooks")
            
        except Exception as e:
            logger.error(f"Store playbooks error: {e}")


async def main():
    """Main entry point for distillation"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.distill_memory <chat_export_file> [source]")
        print("Sources: chatgpt, gemini, perplexity, grok")
        sys.exit(1)
    
    file_path = sys.argv[1]
    source = sys.argv[2] if len(sys.argv) > 2 else "chatgpt"
    
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    distiller = MemoryDistiller()
    
    print(f"Distilling memories from {file_path} (source: {source})")
    
    # Distill memories
    memories = await distiller.distill_chat_file(file_path, source)
    print(f"Distilled {len(memories)} memories")
    
    # Store memories
    await distiller.store_memories(memories)
    
    # Synthesize profile
    profile = await distiller.synthesize_profile(memories)
    print(f"Synthesized {len(profile)} profile entries")
    
    await distiller.store_profile(profile)
    
    # Extract playbooks
    playbooks = await distiller.extract_playbooks(memories)
    print(f"Extracted {len(playbooks)} playbooks")
    
    await distiller.store_playbooks(playbooks)
    
    print("Distillation complete!")


if __name__ == "__main__":
    asyncio.run(main())
