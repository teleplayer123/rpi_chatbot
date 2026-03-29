"""
Command parser module to analyze user text and determine the best Linux/bash command to execute.
"""
import re
import subprocess
from typing import Optional, Tuple, List, Dict, Any


class CommandParser:
    """
    Parses natural language text and maps it to executable shell commands.
    Supports various command categories like system info, file operations,
    network commands, GPIO control, and more.
    """

    def __init__(self):
        # Define command patterns and their corresponding commands
        self._command_patterns: Dict[str, List[Dict[str, Any]]] = {
            "system_info": [
                {
                    "keywords": ["what", "is", "the", "time", "current", "time", "date"],
                    "command": "date '+%A, %B %d, %Y at %I:%M %p'",
                    "description": "Get current date and time"
                },
                {
                    "keywords": ["uptime", "how", "long", "been", "running"],
                    "command": "uptime",
                    "description": "Get system uptime"
                },
                {
                    "keywords": ["memory", "ram", "memory usage"],
                    "command": "free -h | grep Mem",
                    "description": "Get memory usage"
                },
                {
                    "keywords": ["disk", "space", "storage"],
                    "command": "df -h / | tail -1",
                    "description": "Get disk space usage"
                },
                {
                    "keywords": ["ip", "address", "network", "ip address"],
                    "command": "hostname -I | awk '{print $1}'",
                    "description": "Get IP address"
                },
                {
                    "keywords": ["cpu", "temperature", "temp", "hot"],
                    "command": "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f C\\n\", $1/1000}'",
                    "description": "Get CPU temperature"
                },
                {
                    "keywords": ["load", "load average"],
                    "command": "uptime | awk -F'load:' '{print $2}' | awk '{print $1, $2, $3}'",
                    "description": "Get system load average"
                },
            ],
            "file_operations": [
                {
                    "keywords": ["list", "files", "ls", "what", "files"],
                    "command": "ls -la",
                    "description": "List all files in current directory"
                },
                {
                    "keywords": ["who", "am", "i", "current", "user"],
                    "command": "whoami",
                    "description": "Get current user"
                },
                {
                    "keywords": ["where", "am", "located", "pwd", "path"],
                    "command": "pwd",
                    "description": "Get current working directory"
                },
                {
                    "keywords": ["home", "directory"],
                    "command": "echo $HOME",
                    "description": "Get home directory"
                },
            ],
            "process_control": [
                {
                    "keywords": ["processes", "ps", "running", "programs"],
                    "command": "ps aux | head -10",
                    "description": "List running processes"
                },
                {
                    "keywords": ["stop", "kill", "restart"],
                    "command": "echo 'Use specific process name with stop/kill/restart'",
                    "description": "Process control (requires specific process name)"
                },
            ],
            "network_commands": [
                {
                    "keywords": ["ping", "google"],
                    "command": "ping -c 3 8.8.8.8",
                    "description": "Test network connectivity"
                },
                {
                    "keywords": ["wifi", "network", "interfaces"],
                    "command": "ip link show",
                    "description": "Show network interfaces"
                },
            ],
            "gpio_control": [
                {
                    "keywords": ["led", "light", "on"],
                    "command": "echo 'GPIO LED control requires specific pin number'",
                    "description": "LED control (customize with pin number)"
                },
                {
                    "keywords": ["led", "light", "off"],
                    "command": "echo 'GPIO LED control requires specific pin number'",
                    "description": "LED control (customize with pin number)"
                },
            ],
            "device_info": [
                {
                    "keywords": ["model", "raspberry", "pi", "model"],
                    "command": "cat /proc/cpuinfo | grep 'Hardware\\|Revision\\|Serial' | head -3",
                    "description": "Get Raspberry Pi model info"
                },
                {
                    "keywords": ["version", "kernel", "uname"],
                    "command": "uname -a",
                    "description": "Get kernel version"
                },
                {
                    "keywords": ["sd", "card", "mounted"],
                    "command": "mount | grep '/dev/mmcblk'",
                    "description": "Check SD card mount status"
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

    def parse(self, text: str) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Parse user text and return the best matching command.

        Args:
            text: The transcribed user text to analyze

        Returns:
            Tuple of (command, response_prefix, is_executable)
            - command: The shell command to execute (or None if no match)
            - response_prefix: A prefix for the response message (or None)
            - is_executable: Whether the command is safe to execute
        """
        # Normalize input
        text = text.lower().strip()

        # Remove common filler words and questions
        text = re.sub(r'\b(what|the|a|an)\b', '', text)
        text = text.strip()

        # Pattern to extract dynamic parameters (e.g., "restart nginx")
        param_match = re.search(r'(stop|start|restart|kill)\s+(\w+)', text)
        if param_match:
            action, process_name = param_match.groups()
            return f"sudo systemctl {action} {process_name}", f"Initiating {action} for {process_name}", True

        # Search through all command categories
        for category, patterns in self._command_patterns.items():
            for pattern in patterns:
                keywords = pattern["keywords"]
                if any(keyword in text for keyword in keywords):
                    command = pattern["command"]
                    # Determine response prefix based on command
                    response_prefix = self._get_response_prefix(command)
                    return command, response_prefix, True

        # No match found
        return None, None, False

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
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
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
                    "keywords": pattern["keywords"]
                })
        return all_commands


# Singleton instance for convenience
_command_parser = None


def analyze_text(text: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Analyze text and find the best command to execute.

    Args:
        text: The transcribed user text to analyze

    Returns:
        Tuple of (command, response_prefix, is_executable)
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