# Antigravity Usage Limits & Model Information

This document provides information about usage limits and restrictions for different models available in Antigravity.

## Overview

Antigravity uses a token-based system to manage usage across different AI models. Understanding these limits helps you optimize your interactions and avoid temporary restrictions.

---

## Usage Limits & Restrictions

### Rate Limiting System

Antigravity implements two types of temporary restrictions based on usage:

1. **4-Hour Ban** - Short-term cooldown period
2. **7-Day Ban** - Extended restriction for excessive usage

### Token Budget

Each conversation session has a **token budget of 200,000 tokens**. This budget covers:
- Your input messages
- AI responses
- Tool calls and their outputs
- Context from previous messages

---

## Available Models in Antigravity

### 1. **Gemini 2.0 Flash (Primary Model)**
- **Purpose**: General coding assistance, file operations, code generation
- **Token Limit**: 200,000 tokens per conversation
- **Best For**: 
  - Code editing and refactoring
  - File creation and management
  - General programming questions
  - Multi-file operations

### 2. **Image Generation Model**
- **Purpose**: Creating UI mockups, assets, diagrams
- **Usage**: Called via `generate_image` tool
- **Best For**:
  - UI/UX design mockups
  - Visual assets for web applications
  - Diagrams and illustrations
  - Icons and graphics

### 3. **Web Search Model**
- **Purpose**: Real-time information retrieval
- **Usage**: Called via `search_web` tool
- **Best For**:
  - Finding documentation
  - Researching libraries and frameworks
  - Getting up-to-date information

---

## How to Avoid Restrictions

### Best Practices

1. **Be Specific in Requests**
   - Clear, focused questions use fewer tokens
   - Example: ❌ "Fix everything" → ✅ "Fix the KeyError in db.py line 45"

2. **Avoid Unnecessary Context**
   - Don't repeat information already shared
   - Reference previous messages instead of re-explaining

3. **Use Targeted File Operations**
   - View specific line ranges instead of entire files
   - Use `view_file_outline` before reading full files
   - Example: `view_file(file.py, StartLine=100, EndLine=150)`

4. **Optimize Tool Usage**
   - Use `grep_search` to find specific code instead of viewing multiple files
   - Use `view_code_item` for specific functions/classes

5. **Break Down Large Tasks**
   - Split complex requests into smaller, sequential steps
   - Complete one feature at a time

---

## Token Usage Examples

### Low Token Usage (Efficient) ✅

**Example 1**: Targeted bug fix
```
Request: "Fix the KeyError: 'summary_embedding' in utils/db.py"
Estimated tokens: ~5,000-10,000
```

**Example 2**: Specific feature addition
```
Request: "Add a delete button to the sidebar chat sessions in app.py"
Estimated tokens: ~8,000-15,000
```

**Example 3**: Code review of specific function
```
Request: "Review the process_audio() function in utils/audio_handler.py"
Estimated tokens: ~3,000-8,000
```

### Medium Token Usage (Moderate) ⚠️

**Example 1**: Multi-file feature implementation
```
Request: "Add web scraping functionality across app.py, utils/web_scraper.py, and utils/rag.py"
Estimated tokens: ~30,000-60,000
```

**Example 2**: UI redesign
```
Request: "Redesign the chatbot UI to look like ChatGPT with improved layout"
Estimated tokens: ~40,000-80,000
```

### High Token Usage (Risk of Limits) ⛔

**Example 1**: Complete application refactor
```
Request: "Refactor all project files and remove all comments and docstrings"
Estimated tokens: ~100,000-180,000
```

**Example 2**: Multiple large file operations
```
Request: "Review and fix all files in the project: app.py, utils/db.py, utils/llm.py, 
utils/rag.py, utils/web_scraper.py, utils/audio_handler.py, Dockerfile, README.md"
Estimated tokens: ~120,000-200,000
```

---

## What Triggers Restrictions?

### 4-Hour Ban Triggers
- Exceeding token budget in a single conversation
- Rapid successive requests with high token usage
- Multiple large file operations in quick succession

### 7-Day Ban Triggers
- Repeated violations of 4-hour limits
- Extremely high token usage patterns
- Automated/scripted excessive usage

---

## Monitoring Your Usage

### Signs You're Approaching Limits

1. **Conversation becomes slower** - Processing large amounts of context
2. **Responses reference token budget** - System warning of high usage
3. **Multiple file views in single request** - Each file view consumes tokens

### How to Check Token Usage

The token budget is displayed at the start of each conversation:
```
<budget:token_budget>200000</budget:token_budget>
```

---

## Recovery from Restrictions

### If You Hit a 4-Hour Ban
- Wait 4 hours before starting a new conversation
- Review your recent requests to identify high-token operations
- Plan more efficient requests for next session

### If You Hit a 7-Day Ban
- Wait 7 days for full access restoration
- Review this document to understand efficient usage patterns
- Consider breaking large projects into smaller sessions

---

## Tips for Maximum Efficiency

### 1. **Start with Planning**
```
Good approach:
1. "What files do I need to modify to add feature X?"
2. "Show me the outline of file.py"
3. "Update the specific_function in file.py to do Y"
```

### 2. **Use Incremental Development**
```
Instead of: "Build a complete chatbot with all features"
Do: 
- Session 1: "Create basic chatbot structure"
- Session 2: "Add document upload feature"
- Session 3: "Add web scraping capability"
```

### 3. **Leverage Search Tools**
```
Efficient: "Search for 'KeyError' in the utils directory"
vs.
Inefficient: "Show me all files in utils directory"
```

### 4. **Reference Previous Work**
```
Efficient: "Apply the same pattern we used in the last fix"
vs.
Inefficient: "Here's the entire context again... [repeating information]"
```

---

## Model-Specific Considerations

### Gemini 2.0 Flash
- **Strength**: Fast, efficient for most coding tasks
- **Limitation**: 200K token budget per conversation
- **Best Use**: Focused, specific coding tasks

### Image Generation
- **Strength**: Creates visual assets without token overhead
- **Limitation**: Limited to image creation only
- **Best Use**: UI mockups, diagrams, visual assets

### Web Search
- **Strength**: Real-time information access
- **Limitation**: Each search consumes tokens for results
- **Best Use**: Finding documentation, checking latest versions

---

## Summary

| Aspect | Limit | Notes |
|--------|-------|-------|
| **Token Budget** | 200,000 tokens/conversation | Includes all inputs, outputs, and tool calls |
| **Short Ban** | 4 hours | Triggered by exceeding limits |
| **Long Ban** | 7 days | Triggered by repeated violations |
| **File Operations** | No hard limit | Each operation consumes tokens |
| **Image Generation** | No hard limit | Minimal token impact |
| **Web Searches** | No hard limit | Results consume tokens |

---

## Questions?

If you're unsure about whether a request might exceed limits:
1. Break it into smaller parts
2. Ask for an outline or plan first
3. Request specific files/functions rather than entire codebases

**Remember**: Quality over quantity. Focused, specific requests are more effective and efficient than broad, general ones.

---

*Last Updated: January 27, 2026*
