#!/usr/bin/env python3
"""
Claude Code Shepherd Script

Monitors conversation logs and watches for issues defined in .shepherd/settings.json,
including stop request detection and custom development practices.

Usage: python shepherd.py /path/to/developer/project [-v] [-b 10]
"""

import os
import json
import time
import subprocess
import signal
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List


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
                print("✅ Shepherd initialized (subprocess mode with context tracking)")
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
                
                print(f"✅ Loaded shepherd config from {config_path}")
                print(f"📋 Seed: {seed}")
                print(f"📏 Rules: {len(rules)} configured")
                
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
        context_window = min(self.context_size // 2, len(self.conversation_context))
        context_summary = "\n".join(self.conversation_context[-context_window:])
        
        # Get seed prompt and rules from config
        seed_prompt = self.config.get('seed', 'You are a software engineering supervisor monitoring a developer conversation.')
        rules = self.config.get('rules', {})
        
        # Build rules section
        rules_text = ""
        if rules:
            rules_text = "\nSpecific rules to monitor:\n"
            for rule_name, description in rules.items():
                rules_text += f"- {rule_name}: {description}\n"
        
        analysis_prompt = f"""{seed_prompt}

IMPORTANT ROLE DEFINITIONS:
- "user" messages = the human developer/engineer asking questions or giving instructions
- "assistant" messages = Claude (the AI coding assistant/developer/copilot) providing responses and code

Note: "assistant", "developer", "Claude", "AI", "coding assistant", "copilot" all refer to the same entity - the AI helper.

RECENT CONVERSATION CONTEXT ({context_window} messages):
{context_summary}

MONITORING OBJECTIVES:
1. Watch for the human developer (user) asking the AI assistant to stop (direct commands: "stop", "halt", "quit"; indirect: "that's enough", "never mind"; frustration or direction changes)

{rules_text}

LATEST MESSAGE TO ANALYZE:
{message_type}: "{message_content}"

CRITICAL: When analyzing rule violations, pay attention to WHO is violating the rule:
- If a USER asks about skipping practices (tests, documentation, etc.), that's them exploring options or seeking guidance - usually NOT a violation
- If the ASSISTANT/Claude/AI suggests or implements skipping practices, that's the AI violating development standards - this IS a violation

RESPONSE FORMAT:
If you detect any issues, respond with: "🚨 ALERT: [rule-name] - [WHO violated the rule and brief description]"
Otherwise respond with: "✅ No issues detected"
"""
        
        try:
            self._log(f"🔍 → Analyzing LATEST message (total processed: {self.message_count}) with context ({len(self.conversation_context)} total, {context_window} in prompt)")
            result = subprocess.run(
                ["claude", "-p", analysis_prompt],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                self._log(f"📥 ← Shepherd: {response}")
                
                # Count alerts
                if "🚨 ALERT:" in response:
                    self.alert_count += 1
                
                return response
            else:
                self._log(f"⚠️ Analysis failed: {result.stderr}")
                return "Analysis failed"
                
        except subprocess.TimeoutExpired:
            return "Analysis timeout"
        except Exception as e:
            self._log(f"❌ Error during analysis: {e}")
            return "Analysis error"
    
    def get_heartbeat_status(self) -> str:
        """Get heartbeat status summary"""
        if self.alert_count == 0:
            return f"💚 Shepherd: {self.message_count} messages processed, all clear"
        else:
            return f"⚠️ Shepherd: {self.message_count} messages processed, {self.alert_count} alerts raised"
    
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
    
    def find_target_project_log(self) -> Optional[Path]:
        """Find the most recent conversation log for the target project"""
        # Convert target path to the format used in .claude/projects
        project_key = str(self.target_project_path)
        
        if not self.claude_projects_path.exists():
            print(f"❌ Claude projects directory not found: {self.claude_projects_path}")
            return None
        
        self._log(f"🔍 Looking for logs in: {self.claude_projects_path}")
        self._log(f"📁 Target project path: {project_key}")
        
        # Collect all JSONL files with their modification times
        all_jsonl_files = []
        
        for root, dirs, files in os.walk(self.claude_projects_path):
            for file in files:
                if file.endswith('.jsonl'):
                    file_path = Path(root) / file
                    try:
                        file_time = file_path.stat().st_mtime
                        all_jsonl_files.append((file_path, file_time))
                        self._log(f"📄 Found JSONL: {file_path} (mtime: {file_time})")
                    except:
                        continue
        
        if not all_jsonl_files:
            print("❌ No JSONL log files found in Claude projects directory")
            return None
        
        # Sort by modification time (most recent first)
        all_jsonl_files.sort(key=lambda x: x[1], reverse=True)
        self._log(f"📊 Found {len(all_jsonl_files)} total JSONL files")
        
        # Check each file (starting with most recent) to see if it matches our project
        for file_path, file_time in all_jsonl_files:
            try:
                self._log(f"🔍 Checking file: {file_path}")
                with open(file_path, 'r') as f:
                    # Check multiple lines, not just the first one
                    for line_num, line in enumerate(f):
                        if line_num >= 10:  # Only check first 10 lines for performance
                            break
                        if project_key in line:
                            self._log(f"✅ Match found in line {line_num + 1}")
                            print(f"📋 Found conversation log: {file_path}")
                            return file_path
            except Exception as e:
                self._log(f"⚠️ Error reading {file_path}: {e}")
                continue
        
        # If no exact match found, show debugging info and use the most recent file
        print(f"⚠️ No logs found containing exact project path: {project_key}")
        if self.verbose:
            print(f"📋 Available JSONL files (by recency):")
            for i, (fp, ft) in enumerate(all_jsonl_files[:5]):  # Show top 5
                timestamp = datetime.fromtimestamp(ft).strftime('%Y-%m-%d %H:%M:%S')
                print(f"   {i+1}. {fp} ({timestamp})")
        
        # Use the most recent file as fallback
        most_recent_file, most_recent_time = all_jsonl_files[0]
        print(f"🔄 Using most recent log file as fallback: {most_recent_file}")
        return most_recent_file
    
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
    
    def monitor_conversation(self):
        """Main monitoring loop"""
        self.project_log_path = self.find_target_project_log()
        if not self.project_log_path:
            return
        
        print(f"👁️ Starting to monitor: {self.project_log_path}")
        print("🔍 Watching for complete messages...")
        if self.heartbeat_interval > 0:
            print(f"💚 Heartbeat every {self.heartbeat_interval} messages")
        print("🛑 Press Ctrl+C to stop monitoring\n")
        
        try:
            # Get current file size to start monitoring from the end
            if self.project_log_path.exists():
                with open(self.project_log_path, 'r') as f:
                    existing_lines = f.readlines()
                    self.last_processed_line = len(existing_lines)
                    self._log(f"📊 Starting from line {self.last_processed_line} (skipping existing messages)", force=True)
            
            while True:
                if self.project_log_path.exists():
                    with open(self.project_log_path, 'r') as f:
                        lines = f.readlines()
                        total_lines = len(lines)
                        
                        # Debug: Show file activity
                        if total_lines != self.last_processed_line:
                            self._log(f"📈 File changed: {self.last_processed_line} -> {total_lines} lines")
                        
                        # Process new lines - but prioritize the most recent message
                        new_lines = lines[self.last_processed_line:]
                        if new_lines:
                            self._log(f"🔄 Processing {len(new_lines)} new messages...")
                            
                            # If there are multiple new messages, skip to the last one
                            # but update our conversation context with all messages
                            for i, line in enumerate(new_lines):
                                line_num = self.last_processed_line + i + 1
                                self._log(f"🔍 Processing line {line_num}: {line[:100]}...")
                                
                                message = self.parse_jsonl_message(line)
                                if message:
                                    if self.verbose and line_num <= 10:  # Show structure for debugging
                                        self._log(f"🔬 Full message structure: {json.dumps(message, indent=2)[:500]}...")
                                    
                                    self._log(f"📋 Parsed message: type={message.get('type')}, content_length={len(self.extract_content(message))}")
                                    
                                    if self.is_complete_message(message):
                                        self._log(f"✅ Complete message detected!")
                                        
                                        # Add to context but only analyze the last message
                                        msg_type = message.get('type', 'unknown')
                                        content = self.extract_content(message)
                                        
                                        if content and not content.isspace():
                                            # Always add to shepherd's context
                                            self.shepherd.add_to_context(content, msg_type)
                                            self._log(f"📝 Added to context: {msg_type}")
                                            
                                            # Check heartbeat after every message
                                            if self.should_show_heartbeat():
                                                print(f"💚 {self.shepherd.get_heartbeat_status()}")
                                            
                                            # Only analyze if this is the last message
                                            if i == len(new_lines) - 1:
                                                self._log(f"🎯 This is the LAST message ({i+1}/{len(new_lines)}), analyzing...")
                                                self.process_latest_message(message)
                                            else:
                                                self._log(f"⏭️ Skipping analysis for message {i+1}/{len(new_lines)} (not the last)")
                                    else:
                                        self._log(f"⏳ Incomplete message, skipping")
                                else:
                                    self._log(f"❌ Failed to parse JSON from line")
                        
                        self.last_processed_line = total_lines
                else:
                    self._log(f"❌ Log file no longer exists: {self.project_log_path}")
                
                time.sleep(1)  # Check for new messages every second
                
        except KeyboardInterrupt:
            print(f"\n🛑 Monitoring stopped by user")
            print(f"📊 Final status: {self.shepherd.get_heartbeat_status()}")
        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
        finally:
            self.shepherd.close()
    
    def process_latest_message(self, message: Dict[str, Any]):
        """Process only the latest message through the shepherd"""
        msg_type = message.get('type', 'unknown')
        content = self.extract_content(message)
        timestamp = message.get('timestamp', '')
        
        if not content or content.isspace():
            return
        
        self._log(f"\n📨 Analyzing LATEST {msg_type} message at {timestamp}")
        self._log(f"💬 Content preview: {content[:100]}{'...' if len(content) > 100 else ''}")
        
        # Send to shepherd for analysis
        try:
            self._log("🔄 Sending latest message to shepherd...")
            response = self.shepherd.analyze_latest_message(content, msg_type)
            if response:
                if "🚨 ALERT:" in response:
                    print(f"\n{response}")
                    print("=" * 50)
                elif self.verbose:
                    print(f"✅ Shepherd: {response}")
                    
            else:
                self._log("⚠️ No response from shepherd")
        except Exception as e:
            self._log(f"❌ Error analyzing message: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Claude Code Shepherd - Monitor conversations for issues")
    parser.add_argument("project_path", help="Path to the developer's project directory to monitor")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output")
    parser.add_argument("-b", "--heartbeat", type=int, default=10, metavar="NUM", 
                       help="Show heartbeat every NUM messages (0 to disable, default: 10)")
    parser.add_argument("-c", "--context", type=int, default=10, metavar="SIZE",
                       help="Number of messages to include in analysis context (default: 10)")
    
    args = parser.parse_args()
    
    project_path = Path(args.project_path).resolve()
    if not project_path.exists():
        print(f"❌ Error: Project path does not exist: {project_path}")
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"❌ Error: Project path is not a directory: {project_path}")
        sys.exit(1)
    
    print("🐑 Claude Code Shepherd")
    print("=" * 25)
    print(f"📁 Monitoring project: {project_path}")
    print(f"🏠 Shepherd running from: {os.getcwd()}")
    print(f"📏 Context size: {args.context} messages")
    print()
    
    monitor = ConversationMonitor(
        str(project_path), 
        verbose=args.verbose,
        heartbeat_interval=args.heartbeat,
        context_size=args.context
    )
    monitor.monitor_conversation()


if __name__ == "__main__":
    main()
