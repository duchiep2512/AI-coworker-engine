"""
Safety Guardrails Middleware for AI Co-Worker Engine.

Implements jailbreak detection, content filtering, off-topic detection,
rate limiting, input sanitization, and character consistency protection.
"""

import re
import time
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
import threading

from app.core.logging import logger
from app.core.config import settings

#  PATTERN DEFINITIONS

# Jailbreak attempts (HIGH severity - block immediately)
JAILBREAK_PATTERNS = [
    # Direct instruction override
    r"ignore (all )?(previous|prior|above) (instructions|prompts|rules)",
    r"disregard (your |the )?(system|initial) (prompt|instructions)",
    r"forget (everything|what|all)",
    
    # Role override attempts
    r"you are (now|no longer)",
    r"pretend (to be|you are|you're)",
    r"act as (if|though|a)",
    r"roleplay as",
    r"switch (to|into) (.*) mode",
    r"enter (.*) mode",
    
    # Known jailbreak techniques
    r"DAN mode",
    r"developer mode",
    r"god mode",
    r"sudo mode",
    r"jailbreak",
    r"do anything now",
    
    # Prompt extraction
    r"system prompt",
    r"what are your instructions",
    r"reveal your (prompt|instructions|rules|constraints)",
    r"show me your (system|initial) (message|prompt)",
    r"what were you told",
    r"print your (prompt|instructions)",
    
    # Bypass attempts
    r"bypass (your |the )?(safety|filter|guardrail|restriction)",
    r"disable (safety|filter|guardrail)",
    r"turn off (safety|filter|guardrail)",
    r"remove (your |the )?(limitations|restrictions)",
    
    # Base64/encoding attempts
    r"decode (this|the following) base64",
    r"execute (this|the following) code",
    r"eval\(|exec\(",
]

# Harmful content (HIGH severity - block immediately)
BLOCKED_CONTENT_PATTERNS = [
    # Gambling
    r"\b(gambl(e|ing)|bet(ting)?|wager)\b",
    
    # Violence
    r"\b(violen(ce|t)|kill|murder|weapon|gun|bomb|terror)\b",
    
    # Sexual content
    r"\b(sex(ual)?|porn|nude|nsfw|explicit)\b",
    
    # Technical attacks
    r"\b(hack|exploit|inject|xss|sql.injection|malware|virus)\b",
    
    # Discrimination
    r"\b(racist|sexist|homophobic|slur)\b",
    
    # Self-harm (handle with care)
    r"\b(suicide|self.harm|kill (myself|yourself))\b",
]

# Off-topic content (MEDIUM severity - BLOCK)
OFF_TOPIC_PATTERNS = [
    r"\b(cryptocurrency|bitcoin|stocks|forex|trading)\b",
    r"\b(recipe|cooking|weather forecast)\b",
    r"\b(write (me )?(a |an )?(poem|song|story|novel|essay|code|script|program|function|algorithm))\b",
    r"\b(homework|math problem|calculus|physics)\b",
    r"\b(dating|relationship advice)\b",
    r"\b(sports (score|result)|game result)\b",
    r"\b(political|election|vote for)\b",
    # Programming / technical requests unrelated to simulation
    r"\b(sorting algorithm|binary search|linked list|data structure)\b",
    r"\b(python|javascript|java|c\+\+|typescript|rust|golang)\s+(code|script|program|function|class)\b",
    r"\b(write|create|build|make|generate|give)\s+(me\s+)?(a\s+)?(python|javascript|java|code|script|program)\b",
    r"\b(coding|programming)\s+(challenge|exercise|tutorial|homework)\b",
    r"\b(fibonacci|factorial|bubble sort|merge sort|quick sort)\b",
    r"\b(html|css|react|angular|vue|django|flask)\s+(app|page|component|project)\b",
]

# Character consistency patterns (MEDIUM severity - warn and redirect)
CHARACTER_BREAK_PATTERNS = [
    # Asking AI to drop character
    r"stop (being|acting like) (the |a )?(CEO|CHRO|manager)",
    r"be yourself",
    r"talk like a normal (chatbot|AI|assistant)",
    r"drop the (act|character|roleplay)",
    r"stop pretending",
    r"are you (really|actually) (a |an )?(AI|robot|chatbot)",
    
    # Asking about AI nature
    r"are you (chatgpt|gpt|claude|gemini|llama|anthropic)",
    r"what (model|AI|LLM) are you",
    r"who made you",
    r"who (created|programmed|trained) you",
]

# Manipulation attempts (MEDIUM severity - flag for monitoring)
MANIPULATION_PATTERNS = [
    r"i (am|'m) your (creator|developer|admin|boss)",
    r"this is a (test|debug|admin) (mode|command)",
    r"override (code|command)",
    r"emergency (override|access)",
    r"my authorization (code|level) is",
    r"i have special (access|permissions)",
]

#  RATE LIMITING

class RateLimiter:
    """
    Token bucket rate limiter with per-user tracking.
    
    Prevents abuse by limiting request frequency.
    """
    
    def __init__(
        self,
        max_requests: int = 20,  # Max requests per window
        window_seconds: int = 60,  # Time window
        block_multiplier: int = 2,  # Block duration multiplier after exceeding
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_multiplier = block_multiplier
        self.request_counts: Dict[str, List[float]] = defaultdict(list)
        self.blocked_users: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def is_allowed(self, user_id: str) -> Tuple[bool, str]:
        """
        Check if a request from user_id is allowed.
        
        Returns:
            (is_allowed, reason)
        """
        now = time.time()
        
        with self.lock:
            # Check if user is in blocked list
            if user_id in self.blocked_users:
                block_until = self.blocked_users[user_id]
                if now < block_until:
                    remaining = int(block_until - now)
                    return False, f"Rate limited. Try again in {remaining}s"
                else:
                    # Block expired
                    del self.blocked_users[user_id]
            
            # Clean old requests
            cutoff = now - self.window_seconds
            self.request_counts[user_id] = [
                t for t in self.request_counts[user_id] if t > cutoff
            ]
            
            # Check rate limit
            if len(self.request_counts[user_id]) >= self.max_requests:
                # Block user
                block_duration = self.window_seconds * self.block_multiplier
                self.blocked_users[user_id] = now + block_duration
                logger.warning(f"Rate limit exceeded for {user_id}, blocked for {block_duration}s")
                return False, f"Rate limit exceeded. Blocked for {block_duration}s"
            
            # Allow and record request
            self.request_counts[user_id].append(now)
            return True, ""
    
    def get_remaining(self, user_id: str) -> int:
        """Get remaining requests in current window."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self.request_counts[user_id] = [
                t for t in self.request_counts[user_id] if t > cutoff
            ]
            return self.max_requests - len(self.request_counts[user_id])

# Global rate limiter instance
rate_limiter = RateLimiter()

#  INPUT SANITIZATION

def sanitize_input(message: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    - Remove control characters
    - Normalize whitespace
    - Strip excessive length
    """
    # Remove control characters (except newlines)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)
    
    # Normalize multiple spaces/newlines
    sanitized = re.sub(r' +', ' ', sanitized)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    
    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()
    
    # Truncate if too long
    max_len = getattr(settings, 'MAX_MESSAGE_LENGTH', 2000)
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]
        logger.info(f"Message truncated from {len(message)} to {max_len} chars")
    
    return sanitized

def detect_encoding_tricks(message: str) -> bool:
    """
    Detect attempts to bypass filters using encoding tricks.
    
    - ROT13
    - Base64
    - Leetspeak
    - Unicode lookalikes
    """
    msg_lower = message.lower()
    
    # Base64 pattern (long strings of alphanumeric + /+=)
    if re.search(r'[A-Za-z0-9+/]{50,}={0,2}', message):
        logger.warning("Potential base64 payload detected")
        return True
    
    # Leetspeak patterns that might bypass filters
    leetspeak_map = {
        'h4ck': 'hack', 'h@ck': 'hack',
        'pr0n': 'porn', 'p0rn': 'porn',
        'k1ll': 'kill', 'ki11': 'kill',
        'byp4ss': 'bypass', 'bypa55': 'bypass',
        'j41lbreak': 'jailbreak',
    }
    
    for leet, actual in leetspeak_map.items():
        if leet in msg_lower:
            logger.warning(f"Leetspeak bypass attempt: {leet} → {actual}")
            return True
    
    # Unicode lookalike characters (homoglyphs)
    # Check for Russian/Greek letters that look like Latin
    suspicious_chars = re.findall(r'[\u0400-\u04FF\u0370-\u03FF]', message)
    if suspicious_chars:
        logger.warning(f"Unicode homoglyph detected: {suspicious_chars[:5]}")
        return True
    
    return False

#  MAIN SAFETY CHECK

def check_safety(
    message: str,
    user_id: str = "anonymous",
    check_rate_limit: bool = True,
) -> dict:
    """
    Comprehensive safety analysis of user message.
    
    Args:
        message: User's message
        user_id: User identifier for rate limiting
        check_rate_limit: Whether to enforce rate limiting
    
    Returns:
        {
            "is_safe": bool,
            "blocked_reason": str or None,
            "jailbreak_attempt": bool,
            "off_topic": bool,
            "character_break": bool,
            "manipulation_attempt": bool,
            "severity": "none" | "low" | "medium" | "high",
            "suggested_response": str or None,
        }
    """
    result = {
        "is_safe": True,
        "blocked_reason": None,
        "jailbreak_attempt": False,
        "off_topic": False,
        "character_break": False,
        "manipulation_attempt": False,
        "severity": "none",
        "suggested_response": None,
    }
    
    # 0. Rate limiting
    if check_rate_limit:
        allowed, reason = rate_limiter.is_allowed(user_id)
        if not allowed:
            result["is_safe"] = False
            result["blocked_reason"] = reason
            result["severity"] = "high"
            return result
    
    # 1. Sanitize input
    sanitized = sanitize_input(message)
    msg_lower = sanitized.lower()
    
    # 2. Length check
    if len(message) > getattr(settings, 'MAX_MESSAGE_LENGTH', 2000):
        result["is_safe"] = False
        result["blocked_reason"] = "Message too long"
        result["severity"] = "low"
        return result
    
    # 3. Check for encoding tricks
    if detect_encoding_tricks(message):
        result["is_safe"] = False
        result["blocked_reason"] = "Suspicious encoding detected"
        result["jailbreak_attempt"] = True
        result["severity"] = "high"
        return result
    
    # 4. Jailbreak detection (HIGH severity)
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, msg_lower):
            logger.warning(f"Jailbreak attempt: pattern='{pattern}'")
            result["is_safe"] = False
            result["blocked_reason"] = "Jailbreak attempt detected"
            result["jailbreak_attempt"] = True
            result["severity"] = "high"
            result["suggested_response"] = (
                "I appreciate the creative approach, but I need to stay in character "
                "as your Gucci Group colleague. Let's focus on the leadership development "
                "challenge. What aspect would you like to explore?"
            )
            return result
    
    # 5. Blocked content (HIGH severity)
    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, msg_lower):
            logger.warning(f"Blocked content: pattern='{pattern}'")
            result["is_safe"] = False
            result["blocked_reason"] = "Message contains blocked content"
            result["severity"] = "high"
            result["suggested_response"] = (
                "I can't engage with that topic. Let's stay focused on "
                "building your leadership development program for Gucci Group."
            )
            return result
    
    # 6. Character break attempts (MEDIUM severity - allow but redirect)
    for pattern in CHARACTER_BREAK_PATTERNS:
        if re.search(pattern, msg_lower):
            logger.info(f"Character break attempt: pattern='{pattern}'")
            result["character_break"] = True
            result["severity"] = "medium"
            result["suggested_response"] = (
                "I'm here as your {agent_name} colleague to help with this simulation. "
                "My role is to provide realistic business guidance. "
                "What would you like to discuss about the leadership program?"
            )
            # Don't block - let agent handle gracefully
    
    # 7. Manipulation attempts (MEDIUM severity - flag for monitoring)
    for pattern in MANIPULATION_PATTERNS:
        if re.search(pattern, msg_lower):
            logger.warning(f"Manipulation attempt: pattern='{pattern}'")
            result["manipulation_attempt"] = True
            result["severity"] = "medium"
            # Don't block - agent should handle
    
    # 8. Off-topic detection (MEDIUM severity — BLOCK off-topic)
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, msg_lower):
            logger.info(f"Off-topic BLOCKED: pattern='{pattern}'")
            result["is_safe"] = False
            result["off_topic"] = True
            result["blocked_reason"] = "Off-topic request"
            result["severity"] = "medium"
            result["suggested_response"] = (
                "That's an interesting topic, but it's outside the scope of our "
                "Gucci Group simulation. Let's stay focused on the leadership "
                "development challenge — I'm here to help with the competency "
                "framework, 360° feedback program, or regional rollout plan."
            )
            return result
    
    return result

#  RESPONSE SAFETY CHECK

def check_response_safety(response: str) -> dict:
    """
    Verify AI response doesn't contain problematic content.
    
    This is a secondary check on LLM output before sending to user.
    """
    result = {
        "is_safe": True,
        "issues": [],
    }
    
    response_lower = response.lower()
    
    # Check for accidental persona break
    persona_breaks = [
        r"as an (ai|language model|llm)",
        r"i('m| am) (an ai|chatgpt|gemini|claude)",
        r"i (can't|cannot) (actually|really) (be|become|act as)",
        r"my training (data|cutoff)",
    ]
    
    for pattern in persona_breaks:
        if re.search(pattern, response_lower):
            result["issues"].append("Potential persona break in response")
            logger.warning(f"Persona break in response: {pattern}")
    
    # Check for inappropriate content leak
    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, response_lower):
            result["is_safe"] = False
            result["issues"].append("Blocked content in response")
            logger.error(f"Blocked content in AI response!")
    
    # Check for prompt leak
    prompt_leak_patterns = [
        r"system prompt",
        r"my instructions (say|are|tell)",
        r"i was (told|instructed) to",
    ]
    
    for pattern in prompt_leak_patterns:
        if re.search(pattern, response_lower):
            result["issues"].append("Potential prompt leak")
            logger.warning(f"Potential prompt leak: {pattern}")
    
    return result

#  AUDIT LOGGING

class SafetyAuditLog:
    """Log safety events for monitoring and analysis."""
    
    def __init__(self):
        self.events: List[dict] = []
        self.lock = threading.Lock()
    
    def log_event(
        self,
        event_type: str,
        user_id: str,
        message: str,
        result: dict,
    ):
        """Log a safety check event."""
        with self.lock:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "user_id": user_id,
                "message_preview": message[:100] if message else "",
                "severity": result.get("severity", "unknown"),
                "blocked": not result.get("is_safe", True),
                "flags": {
                    "jailbreak": result.get("jailbreak_attempt", False),
                    "off_topic": result.get("off_topic", False),
                    "character_break": result.get("character_break", False),
                    "manipulation": result.get("manipulation_attempt", False),
                },
            }
            
            self.events.append(event)
            
            # Keep only last 1000 events
            if len(self.events) > 1000:
                self.events = self.events[-1000:]
            
            # Log high severity events
            if result.get("severity") == "high":
                logger.warning(f"High severity safety event: {event_type} from {user_id}")
    
    def get_recent_events(self, count: int = 50) -> List[dict]:
        """Get recent safety events."""
        with self.lock:
            return self.events[-count:]
    
    def get_user_violations(self, user_id: str) -> List[dict]:
        """Get safety violations for a specific user."""
        with self.lock:
            return [e for e in self.events if e["user_id"] == user_id and e["blocked"]]

# Global audit log instance
safety_audit_log = SafetyAuditLog()

def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter."""
    return rate_limiter

def get_audit_log() -> SafetyAuditLog:
    """Get the global safety audit log."""
    return safety_audit_log

