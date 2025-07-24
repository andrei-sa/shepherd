#!/usr/bin/env python3
"""
Shepherd Hook Script for Claude Code UserPromptSubmit

This script is called by Claude Code's UserPromptSubmit hook to inject
shepherd suggestions at the beginning of user prompts.

Input: JSON from Claude Code containing prompt and context information
Output: Suggestion text (if any) that gets prepended to the user prompt
"""

import json
import sys
from pathlib import Path


def get_project_id_from_path(cwd: str) -> str:
    """Convert working directory path to Claude's project ID format"""
    # Claude uses path with / replaced by - for project IDs
    return str(Path(cwd)).replace('/', '-')


def read_suggestion_file(project_id: str) -> str:
    """Read suggestion from project-specific file, return empty string if none"""
    try:
        # Look for suggestion file in shepherd directory (absolute path)
        shepherd_dir = Path(__file__).parent
        suggestions_dir = shepherd_dir / ".shepherd" / "suggestions"
        
        if not suggestions_dir.exists():
            return ""
        
        suggestion_file = suggestions_dir / f"{project_id}.md"
        
        if suggestion_file.exists() and suggestion_file.stat().st_size > 0:
            suggestion = suggestion_file.read_text().strip()
            return suggestion
        
        return ""
    
    except Exception:
        # Silently fail - don't break the user's workflow
        return ""


def delete_suggestion_file(project_id: str):
    """Delete the suggestion file after reading it"""
    try:
        # Use absolute path to shepherd directory
        shepherd_dir = Path(__file__).parent
        suggestions_dir = shepherd_dir / ".shepherd" / "suggestions"
        suggestion_file = suggestions_dir / f"{project_id}.md"
        
        if suggestion_file.exists():
            suggestion_file.unlink()
    
    except Exception:
        # Silently fail - don't break the user's workflow
        pass


def main():
    """Main hook entry point"""
    try:
        # Read JSON input from Claude Code
        input_data = json.loads(sys.stdin.read())
        
        # Extract working directory to identify project
        cwd = input_data.get('cwd', '')
        if not cwd:
            # No working directory - can't identify project
            return
        
        # Generate project ID using Claude's format
        project_id = get_project_id_from_path(cwd)
        
        # Check for shepherd suggestion
        suggestion = read_suggestion_file(project_id)
        
        if suggestion:
            # Print suggestion - this gets prepended to the user's prompt
            print(f"{suggestion}\n")
            
            # Delete the suggestion file so it doesn't repeat
            delete_suggestion_file(project_id)
    
    except Exception:
        # Silently fail - never break the user's Claude Code experience
        pass


if __name__ == "__main__":
    main()