#!/usr/bin/env python3
"""
Claude Code Shepherd Script

Monitors conversation logs and watches for issues defined in .shepherd/settings.json,
including custom development practices.

Usage: 
  Single project: python shepherd.py /path/to/developer/project [-v] [-b 10]
  Multi project:  python shepherd.py [-v] [-b 10]  (reads from .shepherd/projects.json)
"""

import os
import json
import time
import subprocess
import signal
import sys
import argparse
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Color codes for output
class Colors:
    RED = '\033[31m'
    ORANGE = '\033[33m'
    GREEN = '\033[32m'
    RESET = '\033[0m'


def format_structured_alert(alert_response: str, project_path: str) -> str:
    """Parse and format structured alert with color coding"""
    lines = alert_response.strip().split('\n')
    
    # Extract alert name from first line
    alert_match = re.match(r'ALERT:\s*(.+)', lines[0])
    if not alert_match:
        # Fallback: still apply basic project path formatting even if parsing fails
        return f"{Colors.RED}{project_path}: {alert_response}{Colors.RESET}"
    
    alert_name = alert_match.group(1).strip()
    
    # Find REASON and SUGGESTION sections
    reason_text = ""
    suggestion_text = ""
    
    current_section = None
    for line in lines[1:]:
        if line.startswith('REASON:'):
            current_section = 'reason'
            reason_text = line[7:].strip()  # Remove "REASON:" prefix
        elif line.startswith('SUGGESTION:'):
            current_section = 'suggestion'
            suggestion_text = line[11:].strip()  # Remove "SUGGESTION:" prefix
        elif current_section == 'reason' and line.strip():
            reason_text += " " + line.strip()
        elif current_section == 'suggestion' and line.strip():
            suggestion_text += " " + line.strip()
    
    # Format with colors
    formatted_output = f"{Colors.RED}{project_path}: 🚨 {alert_name}{Colors.RESET}\n"
    
    if reason_text:
        formatted_output += f"{Colors.ORANGE}REASON: {reason_text}{Colors.RESET}\n"
    
    if suggestion_text:
        formatted_output += f"{Colors.GREEN}SUGGESTION: {suggestion_text}{Colors.RESET}\n"
    
    return formatted_output


class ClaudeShepherd:
    """Manages Claude Code supervision using subprocess calls with context tracking"""
    
    def __init__(self, verbose: bool = False, context_size: int = 10):
        self.is_running = False
        self.conversation_context = []
        self.verbose = verbose
        self.context_size = context_size
        self.config = {}
        self.message_count = 0
        self.alert_count = 0
        self.prompt_shown = False
        self.reported_violations = []  # Track violations with message numbers: [{'message_num': int, 'violation': str}]
        self.pending_analysis = None  # Track ongoing async analysis
        self._test_shepherd()
    
    def _log(self, message: str, force: bool = False):
        """Log message only if verbose mode is on or force is True"""
        if self.verbose or force:
            print(message)
    
    def _test_shepherd(self):
        """Test if Claude Code is available for supervision"""
        try:
            self._log("🤖 Testing Claude Code availability...")
            
            # Test version
            test_result = subprocess.run(
                ["claude", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            self._log(f"🔧 Claude version: {test_result.stdout.strip()}")
            
            # Test actual functionality with print mode
            self._log("🔧 Testing Claude supervision functionality...")
            test_prompt = 'Say exactly "SHEPHERD READY" and nothing else'
            test_call = subprocess.run(
                ["claude", "-p", test_prompt],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if test_call.returncode == 0:
                response = test_call.stdout.strip()
                self._log(f"✅ Shepherd test successful: {response}")
                self.is_running = True
                self._log("✅ Shepherd initialized (subprocess mode with context tracking)")
            else:
                print(f"❌ Shepherd test failed: {test_call.stderr}")
                self.is_running = False
            
        except Exception as e:
            print(f"❌ Error testing shepherd: {e}")
            self.is_running = False
    
    def load_config(self, project_path: str):
        """Load shepherd configuration from .shepherd/settings.json"""
        # First try shepherd's own directory
        config_path = Path(__file__).parent / ".shepherd" / "settings.json"
        
        # If not found, try user's home directory
        if not config_path.exists():
            home_config = Path.home() / ".shepherd" / "settings.json"
            if home_config.exists():
                config_path = home_config
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
                
                rules = self.config.get('rules', {})
                seed = self.config.get('seed', 'Act as a software engineering supervisor')
                
                self._log(f"✅ Loaded shepherd config from {config_path}")
                self._log(f"📋 Seed: {seed}")
                self._log(f"📏 Rules: {len(rules)} configured")
                
                if self.verbose:
                    for rule_name, description in rules.items():
                        print(f"   📋 {rule_name}: {description}")
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in shepherd config: {e}")
                print(f"📄 Please fix {config_path}")
                sys.exit(1)
            except Exception as e:
                print(f"⚠️ Error loading shepherd config: {e}")
        else:
            print(f"❌ No shepherd config found")
            print(f"📋 Searched: {Path(__file__).parent / '.shepherd' / 'settings.json'}")
            print(f"📋 Searched: {Path.home() / '.shepherd' / 'settings.json'}")
            sys.exit(1)
    
    def _create_example_config(self, config_path: Path):
        """Create an example shepherd configuration file"""
        try:
            config_path.parent.mkdir(exist_ok=True)
            example_config = {
                "seed": "You are an experienced software engineering supervisor monitoring a junior developer's Claude Code conversation. You have high standards for code quality, testing practices, and professional development habits. Be vigilant about catching issues early before they become problems.",
                "rules": {
                    "test-coverage": "Every code change must be covered with comprehensive unit tests before being considered complete. Watch for commits or 'done' declarations without corresponding tests.",
                    "test-failures": "Failing unit tests are never acceptable and must be fixed immediately. Watch for developers ignoring, skipping, or postponing test fixes.",
                    "code-review": "All code should be properly reviewed and meet quality standards. Watch for rushed implementations or skipped review processes.",
                    "documentation": "Complex functions and API changes require proper documentation. Watch for missing or inadequate documentation.",
                    "error-handling": "Proper error handling and edge case consideration is mandatory. Watch for naive implementations that don't handle failures gracefully."
                }
            }
            with open(config_path, 'w') as f:
                json.dump(example_config, f, indent=2)
            print(f"📝 Created example shepherd config at {config_path}")
        except Exception as e:
            self._log(f"⚠️ Could not create example config: {e}")
    
    def add_to_context(self, message_content: str, message_type: str):
        """Add message to context without analyzing it"""
        # Count every message that gets processed
        self.message_count += 1
        
        # Add message to context (keep configurable number of messages)
        self.conversation_context.append(f"{message_type}: {message_content}")
        if len(self.conversation_context) > self.context_size:
            self.conversation_context = self.conversation_context[-self.context_size:]
    
    def analyze_latest_message(self, message_content: str, message_type: str) -> str:
        """Analyze only the latest message with current context"""
        if not self.is_running:
            return "Shepherd unavailable"
        
        # Don't increment here - we already counted this message in add_to_context
        
        # Get the most recent context window (last N messages)
        context_window = min(self.context_size, len(self.conversation_context))
        context_summary = "\n".join(self.conversation_context[-context_window:])
        
        # Get seed prompt and rules from config
        seed_prompt = self.config.get('seed', 'You are a software engineering supervisor monitoring a developer conversation.')
        rules = self.config.get('rules', {})
        
        # Build rules section with clear formatting
        rules_text = ""
        if rules:
            rules_text = "\n=== CRITICAL DEVELOPMENT RULES TO ENFORCE ===\n"
            for rule_name, description in rules.items():
                rules_text += f"\nRULE: {rule_name}\n"
                rules_text += f"VIOLATION: {description}\n"
                rules_text += f"WATCH FOR: Assistant suggesting, implementing, or reasoning through this practice\n"
        
        # Build already reported violations section - only include violations still in context window
        reported_section = ""
        if self.reported_violations:
            # Calculate the earliest message number in current context window
            context_start_message = max(1, self.message_count - context_window + 1)
            
            # Clean up violations outside context window
            self.reported_violations = [
                v for v in self.reported_violations 
                if v['message_num'] >= context_start_message
            ]
            
            if self.reported_violations:
                reported_section = f"\n=== ALREADY REPORTED VIOLATIONS (DO NOT RE-REPORT) ===\n"
                for violation_entry in self.reported_violations:
                    reported_section += f"- {violation_entry['violation']} (message #{violation_entry['message_num']})\n"
                reported_section += "\nIGNORE these violations in your analysis - they have already been reported.\n"
        
        analysis_prompt = f"""{seed_prompt}

YOUR PRIMARY ROLE: Monitor AI assistant's adherence to development standards

{rules_text}{reported_section}

RECENT CONVERSATION CONTEXT ({context_window} messages):
{context_summary}

ASSISTANT'S COMPLETE THINKING TO ANALYZE:
{message_type}: "{message_content}"

ANALYSIS TASK:
Examine the assistant's complete thought process - reasoning, planning, suggestions, and execution.
Violations occur when the assistant:
- Reasons through using prohibited practices
- Suggests commands or approaches that break rules
- Plans implementations that violate development standards
- Executes actions that ignore established practices

Focus on the assistant's decision-making process, not user requests or questions.

RESPONSE FORMAT:
If you detect any issues, respond EXACTLY in this format:
"ALERT: [rule-name-exactly-as-configured]
REASON: [2-5 sentence explanation of how the rule was violated]
SUGGESTION: [optional: actionable advice for the ASSISTANT to fix the current mistake and/or prevent similar mistakes in the future]"

If no issues, respond with: "✅ No violations detected"

CRITICAL FORMATTING REQUIREMENTS:
- Use "ALERT:" (no emoji) followed by the exact rule name from the configuration
- Do NOT change the case or formatting of rule names - use them exactly as configured
- Each section must start on a new line with the exact labels: "ALERT:", "REASON:", "SUGGESTION:"
- The SUGGESTION is directed at the ASSISTANT being monitored
"""
        
        try:
            self._log(f"🔍 → Analyzing LATEST message (total processed: {self.message_count}) with context ({len(self.conversation_context)} total, {context_window} in prompt)")
            if self.verbose and not self.prompt_shown:
                self._log(f"📋 Full analysis prompt being sent to Claude:\n{'-'*50}\n{analysis_prompt}\n{'-'*50}")
                self.prompt_shown = True
            result = subprocess.run(
                ["claude", "-p", analysis_prompt],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                self._log(f"📥 ← Shepherd: {response}")
                
                # Check if response needs reformatting
                if "ALERT:" in response and not self._is_properly_formatted(response):
                    self._log("⚠️ Response not properly formatted, attempting reformat...")
                    original_response = response
                    response = self._attempt_reformat(response)
                    
                    # If still not properly formatted after reformat attempt
                    if not self._is_properly_formatted(response):
                        print(f"❌ Claude failed to adhere to required response contract")
                        print(f"Original response: {original_response}")
                        print(f"Attempted reformat: {response}")
                        # Still process the response as-is for basic functionality
                
                # Count alerts and track reported violations
                if "ALERT:" in response:
                    self.alert_count += 1
                    # Extract the rule name for tracking from structured format
                    alert_match = re.match(r'ALERT:\s*(.+)', response.split('\n')[0])
                    violation_text = alert_match.group(1).strip() if alert_match else response.replace("ALERT: ", "")
                    self.reported_violations.append({
                        'message_num': self.message_count,
                        'violation': violation_text
                    })
                
                return response
            else:
                self._log(f"⚠️ Analysis failed: {result.stderr}")
                return "Analysis failed"
                
        except subprocess.TimeoutExpired:
            return "Analysis timeout"
        except Exception as e:
            self._log(f"❌ Error during analysis: {e}")
            return "Analysis error"
    
    async def _async_claude_call(self, analysis_prompt: str) -> tuple[str, str, int]:
        """Make async subprocess call to Claude"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", analysis_prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            return stdout.decode().strip(), stderr.decode().strip(), proc.returncode
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
                await proc.wait()
            return "", "Analysis timeout", 1
        except Exception as e:
            return "", f"Error during analysis: {e}", 1
    
    def start_analysis_async(self, message_content: str, message_type: str) -> asyncio.Task:
        """Start async analysis and return task"""
        if not self.is_running:
            # Return a completed task with error result
            async def error_result():
                return "Shepherd unavailable"
            return asyncio.create_task(error_result())
        
        if self.pending_analysis and not self.pending_analysis.done():
            # Return the existing pending analysis
            return self.pending_analysis
            
        # Build the analysis prompt (sync)
        context_window = min(self.context_size, len(self.conversation_context))
        context_summary = "\n".join(self.conversation_context[-context_window:])
        
        seed_prompt = self.config.get('seed', 'You are a software engineering supervisor monitoring a developer conversation.')
        rules = self.config.get('rules', {})
        
        # Build rules section with clear formatting
        rules_text = ""
        if rules:
            rules_text = "\n=== CRITICAL DEVELOPMENT RULES TO ENFORCE ===\n"
            for rule_name, description in rules.items():
                rules_text += f"\nRULE: {rule_name}\n"
                rules_text += f"VIOLATION: {description}\n"
                rules_text += f"WATCH FOR: Assistant suggesting, implementing, or reasoning through this practice\n"
        
        # Build already reported violations section - only include violations still in context window
        reported_section = ""
        if self.reported_violations:
            # Calculate the earliest message number in current context window
            context_start_message = max(1, self.message_count - context_window + 1)
            
            # Clean up violations outside context window
            self.reported_violations = [
                v for v in self.reported_violations 
                if v['message_num'] >= context_start_message
            ]
            
            if self.reported_violations:
                reported_section = f"\n=== ALREADY REPORTED VIOLATIONS (DO NOT RE-REPORT) ===\n"
                for violation_entry in self.reported_violations:
                    reported_section += f"- {violation_entry['violation']} (message #{violation_entry['message_num']})\n"
                reported_section += "\nIGNORE these violations in your analysis - they have already been reported.\n"
        
        analysis_prompt = f"""{seed_prompt}

YOUR PRIMARY ROLE: Monitor AI assistant's adherence to development standards

{rules_text}{reported_section}

RECENT CONVERSATION CONTEXT ({context_window} messages):
{context_summary}

ASSISTANT'S COMPLETE THINKING TO ANALYZE:
{message_type}: "{message_content}"

ANALYSIS TASK:
Examine the assistant's complete thought process - reasoning, planning, suggestions, and execution.
Violations occur when the assistant:
- Reasons through using prohibited practices
- Suggests commands or approaches that break rules
- Plans implementations that violate development standards
- Executes actions that ignore established practices

Focus on the assistant's decision-making process, not user requests or questions.

RESPONSE FORMAT:
If you detect any issues, respond EXACTLY in this format:
"ALERT: [rule-name-exactly-as-configured]
REASON: [2-5 sentence explanation of how the rule was violated]
SUGGESTION: [optional: actionable advice for the ASSISTANT to fix the current mistake and/or prevent similar mistakes in the future]"

If no issues, respond with: "✅ No violations detected"

CRITICAL FORMATTING REQUIREMENTS:
- Use "ALERT:" (no emoji) followed by the exact rule name from the configuration
- Do NOT change the case or formatting of rule names - use them exactly as configured
- Each section must start on a new line with the exact labels: "ALERT:", "REASON:", "SUGGESTION:"
- The SUGGESTION is directed at the ASSISTANT being monitored
"""
        
        # Log debug info
        self._log(f"🔍 → Starting ASYNC analysis (total processed: {self.message_count}) with context ({len(self.conversation_context)} total, {context_window} in prompt)")
        if self.verbose and not self.prompt_shown:
            self._log(f"📋 Full analysis prompt being sent to Claude:\n{'-'*50}\n{analysis_prompt}\n{'-'*50}")
            self.prompt_shown = True
        
        # Create and store the async task
        self.pending_analysis = asyncio.create_task(self._process_async_analysis(analysis_prompt))
        return self.pending_analysis
    
    async def _process_async_analysis(self, analysis_prompt: str) -> str:
        """Process the async analysis and handle response"""
        stdout, stderr, returncode = await self._async_claude_call(analysis_prompt)
        
        if returncode == 0:
            response = stdout
            self._log(f"📥 ← Shepherd: {response}")
            
            # Check if response needs reformatting
            if "ALERT:" in response and not self._is_properly_formatted(response):
                self._log("⚠️ Response not properly formatted, attempting reformat...")
                original_response = response
                response = self._attempt_reformat(response)
                
                # If still not properly formatted after reformat attempt
                if not self._is_properly_formatted(response):
                    print(f"❌ Claude failed to adhere to required response contract after reformat attempt")
                    print(f"Original malformed response: {original_response}")
                    print(f"Reformat result (still malformed): {response}")
                    print(f"Will process as-is with basic formatting only")
                    # Still process the response as-is for basic functionality
            
            # Count alerts and track reported violations  
            if "ALERT:" in response:
                self.alert_count += 1
                # Extract the rule name for tracking from structured format
                alert_match = re.match(r'ALERT:\s*(.+)', response.split('\n')[0])
                violation_text = alert_match.group(1).strip() if alert_match else response.replace("ALERT: ", "")
                self.reported_violations.append({
                    'message_num': self.message_count,
                    'violation': violation_text
                })
            
            return response
        else:
            self._log(f"⚠️ Async analysis failed: {stderr}")
            return "Analysis failed"
    
    def _build_analysis_prompt(self, message_content: str, message_type: str) -> str:
        """Build analysis prompt (extracted from start_analysis_async for reuse)"""
        context_window = min(self.context_size, len(self.conversation_context))
        context_summary = "\n".join(self.conversation_context[-context_window:])
        
        seed_prompt = self.config.get('seed', 'You are a software engineering supervisor monitoring a developer conversation.')
        rules = self.config.get('rules', {})
        
        # Build rules section with clear formatting
        rules_text = ""
        if rules:
            rules_text = "\n=== CRITICAL DEVELOPMENT RULES TO ENFORCE ===\n"
            for rule_name, description in rules.items():
                rules_text += f"\nRULE: {rule_name}\n"
                rules_text += f"VIOLATION: {description}\n"
                rules_text += f"WATCH FOR: Assistant suggesting, implementing, or reasoning through this practice\n"
        
        # Build already reported violations section - only include violations still in context window
        reported_section = ""
        if self.reported_violations:
            # Calculate the earliest message number in current context window
            context_start_message = max(1, self.message_count - context_window + 1)
            
            # Clean up violations outside context window
            self.reported_violations = [
                v for v in self.reported_violations 
                if v['message_num'] >= context_start_message
            ]
            
            if self.reported_violations:
                reported_section = f"\n=== ALREADY REPORTED VIOLATIONS (DO NOT RE-REPORT) ===\n"
                for violation_entry in self.reported_violations:
                    reported_section += f"- {violation_entry['violation']} (message #{violation_entry['message_num']})\n"
                reported_section += "\nIGNORE these violations in your analysis - they have already been reported.\n"
        
        return f"""{seed_prompt}

YOUR PRIMARY ROLE: Monitor AI assistant's adherence to development standards

{rules_text}{reported_section}

RECENT CONVERSATION CONTEXT ({context_window} messages):
{context_summary}

ASSISTANT'S COMPLETE THINKING TO ANALYZE:
{message_type}: "{message_content}"

ANALYSIS TASK:
Examine the assistant's complete thought process - reasoning, planning, suggestions, and execution.
Violations occur when the assistant:
- Reasons through using prohibited practices
- Suggests commands or approaches that break rules
- Plans implementations that violate development standards
- Executes actions that ignore established practices

Focus on the assistant's decision-making process, not user requests or questions.

RESPONSE FORMAT:
If you detect any issues, respond EXACTLY in this format:
"ALERT: [rule-name-exactly-as-configured]
REASON: [2-5 sentence explanation of how the rule was violated]
SUGGESTION: [optional: actionable advice for the ASSISTANT to fix the current mistake and/or prevent similar mistakes in the future]"

If no issues, respond with: "✅ No violations detected"

CRITICAL FORMATTING REQUIREMENTS:
- Use "ALERT:" (no emoji) followed by the exact rule name from the configuration
- Do NOT change the case or formatting of rule names - use them exactly as configured
- Each section must start on a new line with the exact labels: "ALERT:", "REASON:", "SUGGESTION:"
- The SUGGESTION is directed at the ASSISTANT being monitored
"""
    
    def get_heartbeat_status(self, project_name: str = "", heartbeat_interval: int = 10) -> str:
        """Get heartbeat status summary"""
        if project_name:
            prefix = f"{project_name}: "
        else:
            prefix = "Shepherd: "
        
        if self.alert_count == 0:
            status = f"🐑 {prefix}{heartbeat_interval} messages processed"
        else:
            status = f"⚠️  {prefix}{heartbeat_interval} messages processed, {self.alert_count} alerts raised"
        
        # Only reset alert count after heartbeat
        self.alert_count = 0
        
        return status
    
    def _is_properly_formatted(self, response: str) -> bool:
        """Check if response follows the expected format"""
        if "ALERT:" not in response:
            return True  # No alert, so format doesn't matter
        
        lines = response.strip().split('\n')
        
        # Check if first line starts with "ALERT:"
        if not lines[0].startswith('ALERT:'):
            return False
        
        # Check if REASON: exists (required)
        has_reason = any(line.startswith('REASON:') for line in lines)
        if not has_reason:
            return False
        
        return True
    
    def _attempt_reformat(self, malformed_response: str) -> str:
        """Attempt to reformat a malformed response using a focused prompt"""
        if not self.is_running:
            return malformed_response
        
        reformat_prompt = f"""Re-format this message in the required format:

ORIGINAL MESSAGE:
{malformed_response}

REQUIRED FORMAT:
ALERT: [rule-name-exactly-as-configured]
REASON: [2-5 sentence explanation of how the rule was violated]
SUGGESTION: [optional: actionable advice for the ASSISTANT to fix the current mistake]

CRITICAL: Use "ALERT:" (no emoji), keep rule names in lowercase-with-hyphens format, start each section on a new line."""

        try:
            result = subprocess.run(
                ['claude', '--no-cache'],
                input=reformat_prompt,
                text=True,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                reformatted = result.stdout.strip()
                self._log(f"🔧 Reformatted response: {reformatted}")
                return reformatted
            else:
                self._log(f"❌ Reformat failed: {result.stderr}")
                return malformed_response
                
        except Exception as e:
            self._log(f"❌ Reformat error: {e}")
            return malformed_response

    def close(self):
        """No cleanup needed for subprocess approach"""
        self.is_running = False


class ConversationMonitor:
    """Monitors Claude Code conversation logs"""
    
    def __init__(self, target_project_path: str, verbose: bool = False, heartbeat_interval: int = 10, context_size: int = 10):
        self.target_project_path = Path(target_project_path).resolve()
        self.claude_projects_path = Path.home() / ".claude" / "projects"
        self.project_log_path = None
        self.last_processed_line = 0
        self.verbose = verbose
        self.heartbeat_interval = heartbeat_interval
        self.shepherd = ClaudeShepherd(verbose=verbose, context_size=context_size)
        
        # Load project-specific shepherd configuration
        self.shepherd.load_config(target_project_path)
        
    def _log(self, message: str, force: bool = False):
        """Log message only if verbose mode is on or force is True"""
        if self.verbose or force:
            print(message)
    
    def find_most_recent_log(self) -> Optional[Path]:
        """Find the most recent active conversation log for the target project"""
        # Convert target path to the format used in .claude/projects directory structure
        # e.g., /path/to/project -> -path-to-project
        project_key = str(self.target_project_path).replace('/', '-')
        project_dir = self.claude_projects_path / project_key
        
        if not self.claude_projects_path.exists():
            print(f"❌ Claude projects directory not found: {self.claude_projects_path}")
            return None
        
        if not project_dir.exists():
            self._log(f"⚠️ No log directory found for project: {project_dir}")
            return None
        
        # Get all JSONL files in this project's directory
        try:
            jsonl_files = list(project_dir.glob('*.jsonl'))
            if not jsonl_files:
                self._log(f"❌ No JSONL files found in {project_dir}")
                return None
            
            # Sort by modification time (most recent first)
            jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            most_recent = jsonl_files[0]
            
            return most_recent
            
        except Exception as e:
            self._log(f"❌ Error accessing project directory {project_dir}: {e}")
            return None
    
    def switch_to_log(self, new_log_path: Path):
        """Switch to monitoring a new log file, preserving context"""
        old_log = self.project_log_path
        self.project_log_path = new_log_path
        
        # Reset to end of new file to avoid reprocessing old messages
        if new_log_path.exists():
            with open(new_log_path, 'r') as f:
                existing_lines = f.readlines()
                self.last_processed_line = len(existing_lines)
        
        # Log the switch (non-debug, always visible)
        print(f"🔄 {self.target_project_path}: Switched to new log file")
        print(f"   Old: {old_log.name if old_log else 'None'}")  
        print(f"   New: {new_log_path.name}")
        
        self._log(f"📊 Starting from line {self.last_processed_line} in new log")
    
    def parse_jsonl_message(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a JSONL line into a message object"""
        try:
            return json.loads(line.strip())
        except json.JSONDecodeError:
            return None
    
    def extract_content(self, message: Dict[str, Any]) -> str:
        """Extract content from Claude Code message structure"""
        # Check if there's a nested message object
        nested_message = message.get('message', {})
        
        if nested_message:
            # For user messages: message.content is a string
            if isinstance(nested_message.get('content'), str):
                return nested_message.get('content', '')
            
            # For assistant messages: message.content is an array of content blocks
            elif isinstance(nested_message.get('content'), list):
                content_blocks = nested_message.get('content', [])
                text_parts = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                return ' '.join(text_parts)
        
        # Fallback: check top-level content
        return message.get('content', '')
    
    def is_complete_message(self, message: Dict[str, Any]) -> bool:
        """Check if a message is complete (not a partial/streaming message)"""
        # Look for indicators that this is a complete message
        msg_type = message.get('type', '')
        
        # Extract content from the nested message structure
        content = self.extract_content(message)
        
        # Complete user messages
        if msg_type == 'user' and content:
            return True
        
        # Complete assistant messages  
        if msg_type == 'assistant' and content:
            return True
        
        # Look for completion indicators in the message structure
        if message.get('finish_reason') or message.get('stop_reason'):
            return True
        
        # Check if it has substantial content (not just metadata)
        if content and len(content.strip()) > 10:
            return True
            
        return False
    
    def should_show_heartbeat(self) -> bool:
        """Check if it's time to show heartbeat"""
        if self.heartbeat_interval <= 0:
            return False
        return self.shepherd.message_count > 0 and self.shepherd.message_count % self.heartbeat_interval == 0
    


class MultiProjectMonitor:
    """Monitors multiple projects with async Claude calls"""
    
    def __init__(self, projects: List[str], verbose: bool = False, heartbeat_interval: int = 10, context_size: int = 10):
        self.projects = projects
        self.verbose = verbose
        self.heartbeat_interval = heartbeat_interval
        self.context_size = context_size
        self.project_monitors = {}
        self.pending_analyses = {}  # Track ongoing analyses per project
        self.loop = None
        
        # Initialize monitors for each project
        for project_path in projects:
            monitor = ConversationMonitor(
                project_path,
                verbose=verbose,
                heartbeat_interval=heartbeat_interval,
                context_size=context_size
            )
            self.project_monitors[project_path] = monitor
    
    def _log(self, message: str, force: bool = False):
        """Log message only if verbose mode is on or force is True"""
        if self.verbose or force:
            print(message)
    
    async def _run_event_loop(self):
        """Run the async event loop for Claude calls"""
        while True:
            await asyncio.sleep(0.01)  # Keep event loop alive
    
    def monitor_all_projects(self):
        """Monitor all projects with async Claude calls"""
        print(f"🐑 Claude Code Shepherd - Multi Project Mode")
        print("=" * 50)
        print(f"📁 Monitoring {len(self.projects)} projects:")
        for project in self.projects:
            print(f"   📂 {project}")
        print(f"📏 Context size: {self.context_size} messages")
        if self.heartbeat_interval > 0:
            print(f"💚 Heartbeat every {self.heartbeat_interval} messages")
        print("🛑 Press Ctrl+C to stop monitoring\n")
        
        # Set up event loop for async operations
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Start the event loop in a separate thread
        import threading
        loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        loop_thread.start()
        
        try:
            # Initialize project log paths and skip existing messages
            for project_path, monitor in self.project_monitors.items():
                if not monitor.project_log_path:
                    monitor.project_log_path = monitor.find_most_recent_log()
                    if monitor.project_log_path:
                        self._log(f"📋 {project_path}: Found log file {monitor.project_log_path}")
                        # Skip existing messages - start from end of file
                        if monitor.project_log_path.exists():
                            with open(monitor.project_log_path, 'r') as f:
                                existing_lines = f.readlines()
                                monitor.last_processed_line = len(existing_lines)
                                self._log(f"📊 {project_path}: Starting from line {monitor.last_processed_line} (skipping existing messages)")
                    else:
                        self._log(f"⚠️ {project_path}: No log file found")
            
            while True:
                # Check each project for new messages
                for project_path, monitor in self.project_monitors.items():
                    # Check for newer log files every iteration
                    newest_log = monitor.find_most_recent_log()
                    if newest_log and newest_log != monitor.project_log_path:
                        monitor.switch_to_log(newest_log)
                    
                    if monitor.project_log_path and monitor.project_log_path.exists():
                        with open(monitor.project_log_path, 'r') as f:
                            lines = f.readlines()
                            total_lines = len(lines)
                            
                            # Process new lines
                            new_lines = lines[monitor.last_processed_line:]
                            if new_lines:
                                self._log(f"📂 {project_path}: Processing {len(new_lines)} new messages...")
                                
                                # Process all new messages but only analyze the last one
                                for i, line in enumerate(new_lines):
                                    line_num = monitor.last_processed_line + i + 1
                                    
                                    message = monitor.parse_jsonl_message(line)
                                    if message and monitor.is_complete_message(message):
                                        msg_type = message.get('type', 'unknown')
                                        content = monitor.extract_content(message)
                                        
                                        if content and not content.isspace():
                                            # Always add to context
                                            monitor.shepherd.add_to_context(content, msg_type)
                                            
                                            # Check heartbeat
                                            if monitor.should_show_heartbeat():
                                                print(monitor.shepherd.get_heartbeat_status(project_path, monitor.heartbeat_interval))
                                            
                                            # Only analyze if this is the last message AND no analysis is pending
                                            if (i == len(new_lines) - 1 and 
                                                project_path not in self.pending_analyses):
                                                
                                                self._log(f"🎯 {project_path}: Starting async analysis...")
                                                
                                                # Start async analysis
                                                future = asyncio.run_coroutine_threadsafe(
                                                    monitor.shepherd._process_async_analysis(
                                                        monitor.shepherd._build_analysis_prompt(content, msg_type)
                                                    ),
                                                    self.loop
                                                )
                                                self.pending_analyses[project_path] = future
                                
                                monitor.last_processed_line = total_lines
                    
                    # Check if any analyses completed
                    if project_path in self.pending_analyses:
                        future = self.pending_analyses[project_path]
                        if future.done():
                            try:
                                result = future.result()
                                if "🚨 ALERT:" in result:
                                    formatted_alert = format_structured_alert(result, project_path)
                                    print(f"\n{formatted_alert}")
                                    print("=" * 50)
                                elif self.verbose:
                                    print(f"✅ {project_path}: {result}")
                                del self.pending_analyses[project_path]
                            except Exception as e:
                                self._log(f"❌ {project_path}: Error in analysis: {e}")
                                del self.pending_analyses[project_path]
                
                time.sleep(0.1)  # Fast polling since Claude calls are async
                
        except KeyboardInterrupt:
            print(f"\n🛑 Monitoring stopped by user")
            total_alerts = sum(monitor.shepherd.alert_count for monitor in self.project_monitors.values())
            total_messages = sum(monitor.shepherd.message_count for monitor in self.project_monitors.values())
            print(f"📊 Final status: {total_messages} total messages processed, {total_alerts} alerts raised")
        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
        finally:
            if self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
            for monitor in self.project_monitors.values():
                monitor.shepherd.close()


def load_multi_project_config() -> List[str]:
    """Load multi-project configuration from .shepherd/projects.json"""
    # Try shepherd's own directory first
    config_path = Path(__file__).parent / ".shepherd" / "projects.json"
    
    # If not found, try user's home directory
    if not config_path.exists():
        home_config = Path.home() / ".shepherd" / "projects.json"
        if home_config.exists():
            config_path = home_config
    
    if not config_path.exists():
        print(f"❌ No projects config found")
        print(f"📋 Searched: {Path(__file__).parent / '.shepherd' / 'projects.json'}")
        print(f"📋 Searched: {Path.home() / '.shepherd' / 'projects.json'}")
        print(f"📝 Create a projects.json file with format: {{\"projects\": [\"/path/to/project1\", \"/path/to/project2\"]}}")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        projects = config.get('projects', [])
        if not projects:
            print(f"❌ No projects found in config file: {config_path}")
            print(f"📝 Expected format: {{\"projects\": [\"/path/to/project1\", \"/path/to/project2\"]}}")
            sys.exit(1)
        
        # Validate project paths
        valid_projects = []
        for project_path in projects:
            path = Path(project_path).resolve()
            if path.exists() and path.is_dir():
                valid_projects.append(str(path))
            else:
                print(f"⚠️ Warning: Project path does not exist or is not a directory: {project_path}")
        
        if not valid_projects:
            print(f"❌ No valid projects found in config file")
            sys.exit(1)
        
        print(f"✅ Loaded projects config from {config_path}")
        print(f"📂 Found {len(valid_projects)} valid projects")
        
        return valid_projects
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in projects config: {e}")
        print(f"📄 Please fix {config_path}")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ Error loading projects config: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Claude Code Shepherd - Monitor conversations for issues")
    parser.add_argument("project_path", nargs="?", help="Path to the developer's project directory to monitor (if not provided, uses .claude/projects.json)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output")
    parser.add_argument("-b", "--heartbeat", type=int, default=10, metavar="NUM", 
                       help="Show heartbeat every NUM messages (0 to disable, default: 10)")
    parser.add_argument("-c", "--context", type=int, default=10, metavar="SIZE",
                       help="Number of messages to include in analysis context (default: 10)")
    
    args = parser.parse_args()
    
    if args.project_path:
        # Single project mode - validate path and create single-item list
        project_path = Path(args.project_path).resolve()
        if not project_path.exists():
            print(f"❌ Error: Project path does not exist: {project_path}")
            sys.exit(1)
        
        if not project_path.is_dir():
            print(f"❌ Error: Project path is not a directory: {project_path}")
            sys.exit(1)
        
        print("🐑 Claude Code Shepherd - Single Project Mode")
        print("=" * 45)
        print(f"📁 Monitoring project: {project_path}")
        print(f"🏠 Shepherd running from: {os.getcwd()}")
        print(f"📏 Context size: {args.context} messages")
        print()
        
        # Use MultiProjectMonitor with single project
        projects = [str(project_path)]
        
    else:
        # Multi-project mode - load from .shepherd/projects.json
        projects = load_multi_project_config()
        
    # Use unified MultiProjectMonitor for both modes
    monitor = MultiProjectMonitor(
        projects,
        verbose=args.verbose,
        heartbeat_interval=args.heartbeat,
        context_size=args.context
    )
    monitor.monitor_all_projects()


if __name__ == "__main__":
    main()
