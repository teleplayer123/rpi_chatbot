#!/usr/bin/env python3
"""Test script for the improved command parser."""

from command_parser import CommandParser, analyze_text, get_alternative_commands

def test_basic_matching():
    """Test basic keyword matching."""
    print("=" * 60)
    print("TEST 1: Basic Keyword Matching")
    print("=" * 60)
    
    parser = CommandParser()
    
    tests = [
        "what is the time",
        "show me the current time",
        "date and time please",
        "how long has it been running",
        "show me memory usage",
        "check disk space",
        "what is my ip address",
        "show me cpu temperature",
    ]
    
    for test in tests:
        cmd, prefix, executable, confidence = analyze_text(test)
        print(f"Input: '{test}'")
        print(f"  Command: {cmd}")
        print(f"  Prefix: {prefix}")
        print(f"  Executable: {executable}")
        print(f"  Confidence: {confidence:.2f}")
        print()
    
    print()

def test_synonym_matching():
    """Test synonym-based matching."""
    print("=" * 60)
    print("TEST 2: Synonym Matching")
    print("=" * 60)
    
    parser = CommandParser()
    
    tests = [
        "show me ram usage",
        "what is my temperature",
        "check storage space",
        "what is my network ip",
        "show me the heat",
    ]
    
    for test in tests:
        cmd, prefix, executable, confidence = analyze_text(test)
        print(f"Input: '{test}'")
        print(f"  Command: {cmd}")
        print(f"  Confidence: {confidence:.2f}")
        print()

def test_priority_ordering():
    """Test that more specific patterns take precedence."""
    print("=" * 60)
    print("TEST 3: Priority Ordering")
    print("=" * 60)
    
    parser = CommandParser()
    
    tests = [
        "station dump",
        "wireless station",
        "network interfaces",
        "interface name",
    ]
    
    for test in tests:
        cmd, prefix, executable, confidence = analyze_text(test)
        print(f"Input: '{test}'")
        print(f"  Command: {cmd}")
        print(f"  Confidence: {confidence:.2f}")
        print()

def test_alternative_suggestions():
    """Test getting alternative suggestions."""
    print("=" * 60)
    print("TEST 4: Alternative Suggestions")
    print("=" * 60)
    
    tests = [
        "show me the time",
        "check system status",
        "what is my ip",
    ]
    
    for test in tests:
        print(f"Input: '{test}'")
        alternatives = get_alternative_commands(test, top_n=3)
        print("  Alternatives:")
        for alt in alternatives:
            print(f"    - {alt['command']} (score: {alt['score']:.1f})")
        print()

def test_command_safety():
    """Test command safety validation."""
    print("=" * 60)
    print("TEST 5: Command Safety Validation")
    print("=" * 60)
    
    parser = CommandParser()
    
    safe_commands = [
        "date '+%A, %B %d, %Y at %I:%M %p'",
        "uptime",
        "ls -la",
        "whoami",
    ]
    
    dangerous_commands = [
        "rm -rf /",
        "chmod 777 /",
    ]
    
    print("Safe commands:")
    for cmd in safe_commands:
        is_safe = parser._validate_command_safety(cmd)
        print(f"  {cmd[:50]}... -> Safe: {is_safe}")
    
    print("\nDangerous commands:")
    for cmd in dangerous_commands:
        is_safe = parser._validate_command_safety(cmd)
        print(f"  {cmd} -> Safe: {is_safe}")
    print()

def test_confidence_scoring():
    """Test confidence scoring for different inputs."""
    print("=" * 60)
    print("TEST 6: Confidence Scoring")
    print("=" * 60)
    
    parser = CommandParser()
    
    tests = [
        "time",
        "what is the current time",
        "show me the time on my computer",
        "time please",
    ]
    
    for test in tests:
        cmd, prefix, executable, confidence = analyze_text(test)
        print(f"Input: '{test}'")
        print(f"  Confidence: {confidence:.2f}")
        print()

def main():
    """Run all tests."""
    test_basic_matching()
    test_synonym_matching()
    test_priority_ordering()
    test_alternative_suggestions()
    test_command_safety()
    test_confidence_scoring()
    
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
