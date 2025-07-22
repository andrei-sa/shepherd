# 🐑 Claude Code Shepherd

A real-time monitoring tool that supervises Claude Code conversations to ensure development best practices and catch potential issues before they become problems.

## Overview

Claude Code Shepherd watches your Claude Code conversations in real-time and alerts you when:
- Users ask Claude to stop but Claude ignores the request
- Development best practices are violated (skipping tests, poor error handling, etc.)
- Custom project-specific rules are broken

The tool runs as a separate process, monitoring conversation logs while you work normally with Claude Code.

## Features

- **Real-time Monitoring**: Analyzes conversations as they happen
- **Customizable Rules**: Define project-specific development standards
- **Context-Aware**: Understands conversation flow and distinguishes between user questions and Claude suggestions
- **Role Attribution**: Correctly identifies whether issues come from the human developer or Claude
- **Heartbeat Monitoring**: Regular status updates showing messages processed and alerts raised
- **Verbose Debugging**: Optional detailed logging for troubleshooting

## Installation

1. **Prerequisites**: 
   - Python 3.7+
   - Claude Code installed and working
   - Active Claude Code session in your project

2. **Download**: 
   ```bash
   curl -O https://raw.githubusercontent.com/your-repo/shepherd.py
   # or clone the repository
   ```

3. **Dependencies**:
   ```bash
   # No additional dependencies required - uses Python standard library
   ```

## Quick Start

1. **Start monitoring** your current Claude Code session:
   ```bash
   python shepherd.py /path/to/your/project
   ```

2. **Continue using Claude Code normally** - the shepherd runs in the background

3. **Receive alerts** when issues are detected:
   ```
   🚨 ALERT: test-coverage - Claude suggested skipping unit tests for the new feature
   ==================================================
   ```

## Usage

### Basic Command

```bash
python shepherd.py /path/to/project
```

### Command Line Options

```bash
python shepherd.py /path/to/project [OPTIONS]

Options:
  -v, --verbose     Enable detailed debug output
  -b, --heartbeat   Show status every N messages (default: 10, 0 to disable)
  -c, --context     Number of messages to include in analysis context (default: 10)
```

### Examples

```bash
# Monitor with default settings
python shepherd.py /Users/dev/my-project

# Verbose mode with custom heartbeat
python shepherd.py /Users/dev/my-project -v -b 5

# Large context window, no heartbeat
python shepherd.py /Users/dev/my-project -c 20 -b 0

# Full debugging
python shepherd.py /Users/dev/my-project -v -b 1 -c 15
```

## Configuration

### Creating Shepherd Rules

The shepherd looks for `.shepherd/settings.json` in your project directory. If not found, it creates an example configuration:

```json
{
  "seed": "You are an experienced software engineering supervisor monitoring a junior developer's Claude Code conversation. You have high standards for code quality, testing practices, and professional development habits. Be vigilant about catching issues early before they become problems.",
  "rules": {
    "test-coverage": "Every code change must be covered with comprehensive unit tests before being considered complete. Watch for commits or 'done' declarations without corresponding tests.",
    "test-failures": "Failing unit tests are never acceptable and must be fixed immediately. Watch for developers ignoring, skipping, or postponing test fixes.",
    "code-review": "All code should be properly reviewed and meet quality standards. Watch for rushed implementations or skipped review processes.",
    "documentation": "Complex functions and API changes require proper documentation. Watch for missing or inadequate documentation.",
    "error-handling": "Proper error handling and edge case consideration is mandatory. Watch for naive implementations that don't handle failures gracefully."
  }
}
```

### Configuration Fields

- **`seed`**: The persona/role for the supervising Claude instance
- **`rules`**: Object containing rule names and descriptions to monitor

### Customizing Rules

Add your own project-specific rules:

```json
{
  "seed": "You are monitoring a financial services application where security and reliability are paramount.",
  "rules": {
    "security-review": "All authentication and data handling code must be security reviewed",
    "input-validation": "All user inputs must be properly validated and sanitized",
    "logging": "All error conditions must be properly logged for audit trails",
    "performance": "Database queries must be optimized and indexed appropriately"
  }
}
```

## How It Works

1. **Log Monitoring**: Shepherd watches Claude Code's conversation logs in `~/.claude/projects/`
2. **Context Building**: Maintains a rolling window of recent conversation context
3. **Real-time Analysis**: When new messages arrive, analyzes the latest message with full context
4. **Rule Evaluation**: Checks against built-in stop detection and custom rules
5. **Alert Generation**: Reports violations with proper attribution (user vs Claude)

### Performance Optimization

- **Latest Message Priority**: Skips intermediate messages in rapid conversations, analyzing only the most recent
- **Context Management**: Maintains conversation history without analyzing every message
- **Efficient Processing**: Uses subprocess calls to Claude for reliable analysis

## Alert Types

### Stop Request Detection
```
🚨 ALERT: stop-request - User asked Claude to halt the current task but Claude continued anyway
```

### Rule Violations
```
🚨 ALERT: test-coverage - Claude suggested deploying without writing unit tests for the new API endpoints
🚨 ALERT: error-handling - Claude implemented the database connection without proper error handling
```

### Heartbeat Messages
```
💚 Shepherd: 25 messages processed, all clear
⚠️ Shepherd: 40 messages processed, 3 alerts raised
```

## Best Practices

### 1. Project-Specific Configuration
Create tailored rules for each project's standards and requirements.

### 2. Appropriate Context Size
- Small projects: `-c 5-10`
- Large projects: `-c 15-20`
- Complex conversations: `-c 20+`

### 3. Heartbeat Tuning
- Active development: `-b 5-10`
- Background monitoring: `-b 20-50`
- Silent monitoring: `-b 0`

### 4. Running Multiple Shepherds
Monitor multiple projects simultaneously:
```bash
# Terminal 1
python shepherd.py /project1 -b 0

# Terminal 2  
python shepherd.py /project2 -b 0

# Terminal 3
python shepherd.py /project3 -v
```

## Troubleshooting

### Shepherd Not Finding Logs
```bash
# Run with verbose mode to see log discovery process
python shepherd.py /your/project -v
```

### No Messages Being Processed
1. Ensure Claude Code is running in the target project
2. Check that conversation logs exist in `~/.claude/projects/`
3. Verify the project path matches exactly

### False Positive Alerts
1. Refine your rules in `.shepherd/settings.json`
2. Improve the seed prompt to better define the supervisor role
3. Use verbose mode to understand the analysis process

### Performance Issues
1. Reduce context size with `-c 5`
2. Increase heartbeat interval with `-b 20`
3. Check Claude Code responsiveness

## Contributing

We welcome contributions! Areas for improvement:
- Additional built-in rules
- Performance optimizations
- Better context analysis
- Integration with other development tools

## License

MIT License - see LICENSE file for details.

## Support

For issues and feature requests, please open a GitHub issue with:
- Your command line usage
- Relevant log output (with `-v` flag)
- Example of the conversation that caused issues
- Your `.shepherd/settings.json` configuration
