# CodeBase Agent - Automated code refactoring

An intelligent multi-agent system powered by CrewAI that automatically analyzes, refactors, and tests Python code using language models.


## Installation

1. **Clone/Setup the project:**
   ```bash
   cd c:\Users\Youssef\Desktop\projects\codebase_agent
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up API key:**
   ```bash
   # Add to .env file
   GROQ_API_KEY=your_api_key_here
   ```


## Key features

### Feature 1: Configuration file (`config.yaml`)
Instead of hard-coding settings, change behavior with a YAML file:

```yaml
# Adjust these without touching code:
processing:
  files:
    - "target_repo/bad_code.py"
    - "src/module.py"  # Add more files!
  refactoring_level: "aggressive"
  backup_originals: true
```

### Feature 2: CLI arguments
Override config on the command line:

```bash
# Process a different file
python main.py --file my_file.py

# Use a different config
python main.py --config config.conservative.yaml

# Clone your approach (conservative or aggressive)
python main.py --conservative
python main.py --aggressive
```

### Feature 3: logging system
Automatic logging to file + console:

```bash
# View logs after running
cat logs/codebase_agent.log

# Or on Windows
type logs\codebase_agent.log
```

**Logs include:**
- Backup confirmations
- Processing progress
- Rate limit notifications
- Error details
- Timestamps for all events

### Feature 4: HTML reports
After each run, check:
```bash
open reports/refactoring_report.html  # macOS
xdg-open reports/refactoring_report.html  # Linux
start reports/refactoring_report.html  # Windows
```

**Reports show:**
- Total files processed
- Success/failure count
- Backup locations
- Per-file status

### Feature 5: Auto backups
Originals are backed up to timestamped folders (`YYYYMMDD_HHMMSS`):

```
backups/
├── 20260304_143015/
│   └── bad_code.py
├── 20260304_150345/
│   └── bad_code.py
└── 20260304_152812/
    └── bad_code.py
```

Restore a backup:
```bash
cp backups/20260304_143015/bad_code.py target_repo/bad_code.py
```

## Common use cases

### Use case 1: Single file
```bash
python main.py --file src/my_module.py
```
- Uses default config
- Creates backup
- Logs to console + file
- Generates HTML report

### Use case 2: Batch process multiple files
Edit `config.yaml`:
```yaml
processing:
  files:
    - "src/module1.py"
    - "src/module2.py"
    - "utils/helpers.py"
```

Then run:
```bash
python main.py
```

### Use case 3: Conservative approach for production code
```bash
python main.py --config config.conservative.yaml
```
- Only 1 iteration per agent
- Sequential process only
- Minimal changes

### Use case 4: Aggressive refactoring for internal code
```bash
python main.py --aggressive
```
- Up to 3 iterations per agent
- Hierarchical process (manager-coordinated)
- Extensive refactoring

## File structure created by phase 1

After running, you'll see:

```
codebase_agent/
├── logs/                           
│   └── codebase_agent.log
├── reports/                        
│   └── refactoring_report.html
├── backups/                        
│   └── 20260304_143015/
│       └── bad_code.py
```

All auto-created! No manual setup needed.


## Project Structure

```
codebase_agent/
├── main.py              # CLI entry point
├── tools.py             # CrewAI tool definitions
├── config.yaml          
├── requirements.txt     
├── README.md           
├── target_repo/
│   ├── bad_code.py      # Example code to refactor
│   └── test_bad_code.py # Tests
├── logs/                # Log files (auto-created)
├── reports/             # HTML reports (auto-created)
├── backups/             # File backups (auto-created)
└── __pycache__/
```

