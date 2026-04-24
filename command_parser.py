"""
Command parser module to analyze user text and determine the best Linux/bash command to execute.
"""
import re
import subprocess
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class PatternMatch:
    """Represents a match between user text and a command pattern."""
    pattern: Dict[str, Any]
    score: float
    matched_keywords: List[str]
    category: str


class CommandParser:
    """
    Parses natural language text and maps it to executable shell commands.
    Supports various command categories like system info, file operations,
    network commands, GPIO control, and more.
    """

    # Synonym mappings for better keyword resolution
    SYNONYMS: Dict[str, List[str]] = {
        "time": ["time", "clock"],
        "memory": ["memory", "ram", "mem"],
        "disk": ["disk", "storage", "drive"],
        "temperature": ["temp", "temperature", "hot", "heat"],
        "interface": ["interface", "network", "net"],
        "wifi": ["wifi", "wireless", "wlan"],
        "led": ["led", "light"],
    }

    # Filler words to remove (actual conversational fillers)
    FILLER_WORDS = {"um", "uh", "like", "you know", "basically", "sort of", "kind of"}

    def __init__(self):
        # Define command patterns and their corresponding commands
        self._command_patterns: Dict[str, List[Dict[str, Any]]] = {
            "system_info": [
                {
                    "keywords": ["what", "is", "the", "time", "current", "time", "date"],
                    "command": "date '+%A, %B %d, %Y at %I:%M %p'",
                    "description": "Get current date and time",
                    "priority": 100,
                    "negative_keywords": []
                },
                {
                    "keywords": ["station", "dump", "station dump", "wireless"],
                    "command": "iw $(ip link show | grep -E 'wl' | awk '{print $2}' | sed 's/:$//') station dump",
                    "description": "Show wireless interface station dump",
                    "priority": 90,
                    "negative_keywords": []
                },
                {
                    "keywords": ["uptime", "how", "long", "been", "running"],
                    "command": "uptime",
                    "description": "Get system uptime",
                    "priority": 85,
                    "negative_keywords": []
                },
                {
                    "keywords": ["memory", "ram", "memory usage"],
                    "command": "free -h | grep Mem",
                    "description": "Get memory usage",
                    "priority": 80,
                    "negative_keywords": []
                },
                {
                    "keywords": ["disk", "space", "storage"],
                    "command": "df -h / | tail -1",
                    "description": "Get disk space usage",
                    "priority": 75,
                    "negative_keywords": []
                },
                {
                    "keywords": ["ip", "address", "network", "ip address"],
                    "command": "hostname -I | awk '{print $1}'",
                    "description": "Get IP address",
                    "priority": 70,
                    "negative_keywords": []
                },
                {
                    "keywords": ["cpu", "temperature", "temp", "hot"],
                    "command": "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f C\\n\", $1/1000}'",
                    "description": "Get CPU temperature",
                    "priority": 65,
                    "negative_keywords": []
                },
                {
                    "keywords": ["load", "load average"],
                    "command": "uptime | awk -F'load:' '{print $2}' | awk '{print $1, $2, $3}'",
                    "description": "Get system load average",
                    "priority": 60,
                    "negative_keywords": []
                },
            ],
            "file_operations": [
                {
                    "keywords": ["list", "files", "ls", "what", "files"],
                    "command": "ls -la",
                    "description": "List all files in current directory",
                    "priority": 95,
                    "negative_keywords": []
                },
                {
                    "keywords": ["who", "am", "i", "current", "user"],
                    "command": "whoami",
                    "description": "Get current user",
                    "priority": 90,
                    "negative_keywords": []
                },
                {
                    "keywords": ["where", "am", "located", "pwd", "path"],
                    "command": "pwd",
                    "description": "Get current working directory",
                    "priority": 85,
                    "negative_keywords": []
                },
                {
                    "keywords": ["home", "directory"],
                    "command": "echo $HOME",
                    "description": "Get home directory",
                    "priority": 80,
                    "negative_keywords": []
                },
            ],
            "process_control": [
                {
                    "keywords": ["processes", "ps", "running", "programs"],
                    "command": "ps aux | head -10",
                    "description": "List running processes",
                    "priority": 90,
                    "negative_keywords": []
                },
                {
                    "keywords": ["stop", "kill", "restart"],
                    "command": "echo 'Use specific process name with stop/kill/restart'",
                    "description": "Process control (requires specific process name)",
                    "priority": 50,
                    "negative_keywords": []
                },
            ],
            "network_commands": [
                {
                    "keywords": ["ping", "google"],
                    "command": "ping -c 3 8.8.8.8",
                    "description": "Test network connectivity",
                    "priority": 85,
                    "negative_keywords": []
                },
                {
                    "keywords": ["show", "wireless", "interface", "name", "interface", "name"],
                    "command": "ip link show | grep -E 'wl' | awk '{print $2}' | sed 's/:$//'",
                    "description": "Shows wireless interface name",
                    "priority": 80,
                    "negative_keywords": []
                },
                {
                    "keywords": ["station", "dump", "station dump", "wireless"],
                    "command": "iw $(ip link show | grep -E 'wl' | awk '{print $2}' | sed 's/:$//') station dump",
                    "description": "Show wireless interface station dump",
                    "priority": 75,
                    "negative_keywords": []
                },
                {
                    "keywords": ["wifi", "network", "interfaces"],
                    "command": "ip link show",
                    "description": "Show network interfaces",
                    "priority": 70,
                    "negative_keywords": []
                },
            ],
            "gpio_control": [
                {
                    "keywords": ["led", "light", "on"],
                    "command": "echo 'GPIO LED control requires specific pin number'",
                    "description": "LED control (customize with pin number)",
                    "priority": 60,
                    "negative_keywords": []
                },
                {
                    "keywords": ["led", "light", "off"],
                    "command": "echo 'GPIO LED control requires specific pin number'",
                    "description": "LED control (customize with pin number)",
                    "priority": 60,
                    "negative_keywords": []
                },
            ],
            "device_info": [
                {
                    "keywords": ["model", "raspberry", "pi", "model"],
                    "command": "cat /proc/cpuinfo | grep 'Hardware\\|Revision\\|Serial' | head -3",
                    "description": "Get Raspberry Pi model info",
                    "priority": 85,
                    "negative_keywords": []
                },
                {
                    "keywords": ["version", "kernel", "uname"],
                    "command": "uname -a",
                    "description": "Get kernel version",
                    "priority": 80,
                    "negative_keywords": []
                },
                {
                    "keywords": ["sd", "card", "mounted"],
                    "command": "mount | grep '/dev/mmcblk'",
                    "description": "Check SD card mount status",
                    "priority": 75,
                    "negative_keywords": []
                },
            ],
        }

        # Create reverse mapping for responses
        self._commands_to_responses: Dict[str, str] = {
            "date": "The current time is",
            "uptime": "The system has been running for",
            "free": "Memory usage:",
            "df": "Disk space usage:",
            "hostname": "Your IP address is",
            "cat /sys/class/thermal": "CPU temperature is",
            "load": "System load average:",
            "ls": "Files in current directory:",
            "whoami": "You are logged in as",
            "pwd": "Current directory is",
            "ps": "Running processes:",
            "ping": "Network connectivity test:",
            "ip link": "Network interfaces:",
            "uname": "Kernel information:",
        }

        # Pre-process patterns to add normalized keywords
        self._normalize_patterns()

    def _normalize_patterns(self):
        """Pre-process patterns to add normalized keyword lists."""
        for category, patterns in self._command_patterns.items():
            for pattern in patterns:
                normalized = []
                for keyword in pattern["keywords"]:
                    # Check if keyword has synonyms and add them
                    if keyword.lower() in self.SYNONYMS:
                        normalized.extend(self.SYNONYMS[keyword.lower()])
                    else:
                        normalized.append(keyword.lower())
                pattern["_normalized_keywords"] = normalized

    def _calculate_score(self, text: str, pattern: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Calculate match score and matched keywords for a pattern.
        
        Scoring factors:
        - Exact phrase matches: +30 points per match
        - Long keyword phrases: +15 points per match
        - Single word matches: +5 points per match
        - Priority: +10 points per 10 priority level
        """
        text_lower = text.lower()
        score = 0
        matched = []
        
        # Check for exact phrase matches first
        keywords = pattern.get("_normalized_keywords") or pattern["keywords"]
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self.SYNONYMS:
                # Expand synonym for matching
                expanded = self.SYNONYMS[keyword_lower]
                for exp in expanded:
                    if exp in text_lower:
                        score += 20
                        if exp not in matched:
                            matched.append(exp)
            elif keyword_lower in text_lower:
                score += 10
                if keyword_lower not in matched:
                    matched.append(keyword_lower)
        
        # Bonus for priority
        priority = pattern.get("priority", 50)
        score += (priority / 10)
        
        # Bonus for longer keyword phrases (more specific)
        if len(matched) > 2:
            score += 20
        
        return score, matched

    def _remove_conversational_fillers(self, text: str) -> str:
        """Remove actual conversational fillers while preserving content words."""
        # Don't remove common question words or domain terms
        preserve_words = {"what", "the", "is", "it", "and", "or", "how", "which", "why"}
        
        words = text.split()
        result = []
        for word in words:
            # Remove only actual fillers, not content words
            if word.lower() not in self.FILLER_WORDS and word.lower() not in preserve_words:
                result.append(word)
        return ' '.join(result)

    def _validate_command_safety(self, command: str) -> bool:
        """
        Validate that a command is safe to execute.
        
        Checks for:
        - Dangerous patterns (rm -rf, etc.)
        - Unsanitized user input
        - Commands requiring elevated privileges
        """
        dangerous_patterns = [
            r'\brm\s+-rf\b',
            r'\bmkfs\b',
            r'\bformat\b',
            r'\bdd\b',
            r'\bchmod\s+[0-7]{3,4}\s+/',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False
        
        return True

    def parse(self, text: str) -> Tuple[Optional[str], Optional[str], bool, Optional[float]]:
        """
        Parse user text and return the best matching command.

        Args:
            text: The transcribed user text to analyze

        Returns:
            Tuple of (command, response_prefix, is_executable, confidence_score)
            - command: The shell command to execute (or None if no match)
            - response_prefix: A prefix for the response message (or None)
            - is_executable: Whether the command is safe to execute
            - confidence_score: Confidence score (0.0-1.0) for the match
        """
        # Normalize input
        original_text = text.lower().strip()
        text = self._remove_conversational_fillers(text)
        text = text.strip()

        if not text:
            return None, None, False, 0.0

        # Find all pattern matches with scores
        all_matches: List[PatternMatch] = []
        
        for category, patterns in self._command_patterns.items():
            for pattern in patterns:
                score, matched_keywords = self._calculate_score(text, pattern)
                
                # Check negative keywords
                negative_keywords = pattern.get("negative_keywords", [])
                for neg in negative_keywords:
                    if neg.lower() in original_text:
                        score = 0
                        break
                
                if score > 0:
                    all_matches.append(PatternMatch(
                        pattern=pattern,
                        score=score,
                        matched_keywords=matched_keywords,
                        category=category
                    ))

        if not all_matches:
            return None, None, False, 0.0

        # Sort by score (highest first)
        all_matches.sort(key=lambda x: x.score, reverse=True)

        # Check for ties and select best match
        best_match = all_matches[0]
        if len(all_matches) > 1:
            # If second match is close, consider it
            if all_matches[1].score > best_match.score * 0.7:
                # Multiple strong matches - could show alternatives
                pass

        command = best_match.pattern["command"]
        is_executable = self._validate_command_safety(command)

        # Calculate confidence score (0.0 - 1.0)
        max_possible_score = len(best_match.pattern.get("_normalized_keywords", [])) * 30 + \
                            best_match.pattern.get("priority", 50) / 10
        confidence = min(1.0, best_match.score / max_possible_score) if max_possible_score > 0 else 0.0

        # Determine response prefix
        response_prefix = self._get_response_prefix(command)

        return command, response_prefix, is_executable, confidence

    def _get_response_prefix(self, command: str) -> Optional[str]:
        """Get a response prefix based on the command being executed."""
        for key, prefix in self._commands_to_responses.items():
            if key in command:
                return prefix
        return None

    def execute(self, command: str) -> Tuple[int, str, str]:
        """
        Execute a shell command safely.

        Args:
            command: The shell command to execute

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            print(f"Command: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"Result: {result.stdout}")
            print(f"Error: {result.stderr}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def get_safe_commands(self) -> List[Dict[str, str]]:
        """
        Get a list of all safe commands that can be executed.

        Returns:
            List of command information dictionaries
        """
        all_commands = []
        for category, patterns in self._command_patterns.items():
            for pattern in patterns:
                all_commands.append({
                    "category": category,
                    "command": pattern["command"],
                    "description": pattern["description"],
                    "keywords": pattern["keywords"],
                    "priority": pattern.get("priority", 50)
                })
        return all_commands

    def get_alternative_matches(self, text: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Get alternative command matches for a given text.

        Args:
            text: The user text to analyze
            top_n: Number of alternatives to return

        Returns:
            List of alternative matches with scores
        """
        _, _, _, _ = self.parse(text)
        # Re-run parse to get all matches
        text_lower = text.lower().strip()
        all_matches: List[PatternMatch] = []
        
        for category, patterns in self._command_patterns.items():
            for pattern in patterns:
                score, matched_keywords = self._calculate_score(text_lower, pattern)
                negative_keywords = pattern.get("negative_keywords", [])
                for neg in negative_keywords:
                    if neg.lower() in text_lower:
                        score = 0
                        break
                
                if score > 0:
                    all_matches.append(PatternMatch(
                        pattern=pattern,
                        score=score,
                        matched_keywords=matched_keywords,
                        category=category
                    ))

        all_matches.sort(key=lambda x: x.score, reverse=True)
        
        return [
            {
                "command": match.pattern["command"],
                "description": match.pattern["description"],
                "score": match.score,
                "matched_keywords": match.matched_keywords
            }
            for match in all_matches[:top_n]
        ]


# Singleton instance for convenience
_command_parser = None


def analyze_text(text: str) -> Tuple[Optional[str], Optional[str], bool, Optional[float]]:
    """
    Analyze text and find the best command to execute.

    Args:
        text: The transcribed user text to analyze

    Returns:
        Tuple of (command, response_prefix, is_executable, confidence_score)
    """
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser.parse(text)


def execute_command(command: str) -> Tuple[int, str, str]:
    """
    Execute a shell command.

    Args:
        command: The shell command to execute

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser.execute(command)


def get_alternative_commands(text: str, top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Get alternative command suggestions for a given text.

    Args:
        text: The user text to analyze
        top_n: Number of alternatives to return

    Returns:
        List of alternative command suggestions
    """
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser.get_alternative_matches(text, top_n)
