"""
OS Operator - Desktop automation and control layer
"""
import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("jarvis.os_operator")

# Try to import optional dependencies
try:
    import pyautogui
    import pygetwindow as gw
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("PyAutoGUI not available - OS control disabled")


class OSOperator:
    """OS automation and control service"""
    
    def __init__(self):
        self.config = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize OS operator"""
        if self._initialized:
            return
        
        from core.config import get_config
        self.config = get_config().os_operator
        
        if PYAUTOGUI_AVAILABLE:
            # Configure PyAutoGUI
            pyautogui.PAUSE = self.config.default_delay
            pyautogui.FAILSAFE = True
            
            # Create screenshot directory
            Path(self.config.screenshot_dir).mkdir(parents=True, exist_ok=True)
            
            logger.info("OS Operator initialized")
        
        self._initialized = True
    
    async def execute_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute a list of OS actions
        
        Args:
            actions: List of action dictionaries
            
        Returns:
            List of results
        """
        await self.initialize()
        
        if not PYAUTOGUI_AVAILABLE:
            return [{"success": False, "error": "PyAutoGUI not available"}]
        
        results = []
        
        for action in actions:
            result = await self._execute_single_action(action)
            results.append(result)
            
            # Small delay between actions
            await asyncio.sleep(0.05)
        
        return results
    
    async def _execute_single_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single OS action"""
        action_type = action.get("type")
        
        try:
            if action_type == "move_mouse":
                return await self._move_mouse(action)
            elif action_type == "click":
                return await self._click(action)
            elif action_type == "scroll":
                return await self._scroll(action)
            elif action_type == "type_text":
                return await self._type_text(action)
            elif action_type == "hotkey":
                return await self._hotkey(action)
            elif action_type == "key":
                return await self._key(action)
            elif action_type == "open_app":
                return await self._open_app(action)
            elif action_type == "focus_app":
                return await self._focus_app(action)
            elif action_type == "screenshot":
                return await self._screenshot(action)
            elif action_type == "get_active_window":
                return await self._get_active_window()
            else:
                return {"success": False, "error": f"Unknown action type: {action_type}"}
        
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _move_mouse(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Move mouse to position"""
        x = action.get("x", 0)
        y = action.get("y", 0)
        duration = action.get("duration", 0.0)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: pyautogui.moveTo(x, y, duration=duration)
        )
        
        return {"success": True, "action": "move_mouse", "x": x, "y": y}
    
    async def _click(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Click mouse button"""
        button = action.get("button", "left")
        clicks = action.get("clicks", 1)
        x = action.get("x")
        y = action.get("y")
        
        loop = asyncio.get_event_loop()
        
        if x is not None and y is not None:
            await loop.run_in_executor(
                None,
                lambda: pyautogui.click(x, y, clicks=clicks, button=button)
            )
        else:
            await loop.run_in_executor(
                None,
                lambda: pyautogui.click(clicks=clicks, button=button)
            )
        
        return {"success": True, "action": "click", "button": button, "clicks": clicks}
    
    async def _scroll(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Scroll mouse"""
        amount = action.get("amount", 0)
        x = action.get("x")
        y = action.get("y")
        
        loop = asyncio.get_event_loop()
        
        if x is not None and y is not None:
            await loop.run_in_executor(
                None,
                lambda: pyautogui.scroll(amount, x=x, y=y)
            )
        else:
            await loop.run_in_executor(
                None,
                lambda: pyautogui.scroll(amount)
            )
        
        return {"success": True, "action": "scroll", "amount": amount}
    
    async def _type_text(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Type text"""
        text = action.get("text", "")
        interval = action.get("interval", 0.0)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: pyautogui.write(text, interval=interval)
        )
        
        return {"success": True, "action": "type_text", "length": len(text)}
    
    async def _hotkey(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Press hotkey combination"""
        keys = action.get("keys", [])
        
        if not keys:
            return {"success": False, "error": "No keys specified"}
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: pyautogui.hotkey(*keys)
        )
        
        return {"success": True, "action": "hotkey", "keys": keys}
    
    async def _key(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Press single key"""
        key = action.get("key", "")
        
        if not key:
            return {"success": False, "error": "No key specified"}
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: pyautogui.press(key)
        )
        
        return {"success": True, "action": "key", "key": key}
    
    async def _open_app(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Open application"""
        app_name = action.get("app_name", "")
        arguments = action.get("arguments")
        
        if not app_name:
            return {"success": False, "error": "No app name specified"}
        
        try:
            cmd = [app_name]
            if arguments:
                cmd.append(arguments)
            
            subprocess.Popen(cmd, shell=True)
            await asyncio.sleep(1)  # Wait for app to start
            
            return {"success": True, "action": "open_app", "app": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _focus_app(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Focus existing application"""
        app_name = action.get("app_name", "")
        
        if not app_name:
            return {"success": False, "error": "No app name specified"}
        
        try:
            windows = gw.getWindowsWithTitle(app_name)
            
            if windows:
                window = windows[0]
                window.activate()
                await asyncio.sleep(0.2)
                return {"success": True, "action": "focus_app", "app": app_name}
            else:
                return {"success": False, "error": f"Window not found: {app_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _screenshot(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Take screenshot"""
        region = action.get("region")
        save_path = action.get("save_path")
        
        if not save_path:
            timestamp = int(time.time())
            save_path = f"{self.config.screenshot_dir}/screenshot_{timestamp}.png"
        
        try:
            loop = asyncio.get_event_loop()
            
            if region:
                img = await loop.run_in_executor(
                    None,
                    lambda: pyautogui.screenshot(region=(region["x"], region["y"], region["width"], region["height"]))
                )
            else:
                img = await loop.run_in_executor(
                    None,
                    pyautogui.screenshot
                )
            
            img.save(save_path)
            
            return {"success": True, "action": "screenshot", "path": save_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_active_window(self) -> Dict[str, Any]:
        """Get active window info"""
        try:
            window = gw.getActiveWindow()
            
            if window:
                return {
                    "success": True,
                    "action": "get_active_window",
                    "title": window.title,
                    "process": window.processName,
                    "position": {"x": window.left, "y": window.top},
                    "size": {"width": window.width, "height": window.height}
                }
            else:
                return {"success": False, "error": "No active window"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_os_operator: Optional[OSOperator] = None


def get_os_operator() -> OSOperator:
    """Get OS operator singleton"""
    global _os_operator
    if _os_operator is None:
        _os_operator = OSOperator()
    return _os_operator
