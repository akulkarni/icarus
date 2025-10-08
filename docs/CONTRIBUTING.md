# Contributing to Icarus

Thank you for your interest in contributing to the Icarus Trading System! This guide will help you get started with development.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Project Architecture](#project-architecture)
- [Adding New Features](#adding-new-features)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive experience for everyone. We expect all contributors to:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

### Our Standards

**Encouraged behaviors**:
- Demonstrating empathy and kindness
- Being respectful of differing opinions
- Giving and gracefully accepting constructive feedback
- Taking responsibility and apologizing for mistakes
- Focusing on what's best for the overall community

**Unacceptable behaviors**:
- Trolling, insulting comments, or personal attacks
- Public or private harassment
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

Before you begin, ensure you have:
- Python 3.11 or higher
- Git
- Tiger Cloud account (for database)
- Basic understanding of async Python
- Familiarity with trading concepts (helpful but not required)

### Fork and Clone

1. **Fork the repository** on GitHub
2. **Clone your fork**:
```bash
git clone https://github.com/YOUR_USERNAME/icarus.git
cd icarus
```

3. **Add upstream remote**:
```bash
git remote add upstream https://github.com/ORIGINAL_OWNER/icarus.git
```

## Development Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Install main dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

**Development dependencies include**:
- pytest
- pytest-asyncio
- pytest-cov
- black (code formatter)
- flake8 (linter)
- mypy (type checker)
- pre-commit (git hooks)

### 3. Setup Pre-commit Hooks

```bash
pre-commit install
```

This will automatically run code quality checks before each commit.

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Tiger Cloud credentials
```

### 5. Initialize Database

```bash
./sql/deploy_schema.sh
```

### 6. Verify Setup

```bash
# Run tests
pytest tests/

# Run the system
python src/main.py
```

If everything works, you're ready to contribute!

## Development Workflow

### 1. Create Feature Branch

```bash
# Fetch latest changes from upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/my-awesome-feature
```

**Branch naming conventions**:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Adding tests
- `chore/` - Maintenance tasks

### 2. Make Changes

Make your changes following the [Code Standards](#code-standards) below.

### 3. Test Your Changes

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agents/test_meta_strategy.py

# Run with coverage
pytest --cov=src tests/

# Check coverage report
pytest --cov=src --cov-report=html tests/
open htmlcov/index.html
```

### 4. Format and Lint

```bash
# Format code with Black
black src/ tests/

# Check linting with flake8
flake8 src/ tests/

# Type checking with mypy
mypy src/
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with conventional commit message
git commit -m "feat: add awesome new feature"
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/my-awesome-feature
```

Then create a Pull Request on GitHub.

## Code Standards

### Python Style Guide

We follow [PEP 8](https://peps.python.org/pep-0008/) with some modifications:

#### Formatting
- Use **Black** for automatic formatting
- Maximum line length: **100 characters**
- Use **double quotes** for strings
- Use **trailing commas** in multi-line structures

#### Naming Conventions
- **Classes**: PascalCase (`class MetaStrategyAgent`)
- **Functions/Methods**: snake_case (`def calculate_allocation()`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_POSITION_SIZE`)
- **Private**: Leading underscore (`_internal_method()`)

#### Type Hints

Always use type hints:

```python
def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.02
) -> float:
    """Calculate Sharpe ratio from returns."""
    # implementation
```

#### Docstrings

Use Google-style docstrings:

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of function.

    More detailed description if needed. Can span
    multiple lines and include examples.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param2 is negative

    Example:
        >>> my_function("test", 42)
        True
    """
    pass
```

### Code Organization

#### Imports

Organize imports in three groups:
1. Standard library
2. Third-party packages
3. Local application imports

```python
# Standard library
import asyncio
import logging
from typing import Optional

# Third-party
import asyncpg
from pydantic import BaseModel

# Local
from src.core.event_bus import EventBus
from src.models.events import MarketTickEvent
```

Use `isort` to automatically organize imports:
```bash
isort src/ tests/
```

#### Module Structure

```python
"""
Module docstring explaining purpose.
"""

# Imports

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Type aliases
ConfigDict = dict[str, Any]

# Classes and functions

# Module-level code (if any)
```

### Async/Await

- Use async/await for all I/O operations
- Use `async with` for context managers
- Avoid blocking operations in async code
- Use `asyncio.create_task()` for concurrent operations

**Good**:
```python
async def fetch_data():
    async with get_db_connection() as conn:
        result = await conn.fetch("SELECT * FROM trades")
    return result
```

**Bad**:
```python
def fetch_data():
    conn = get_db_connection_sync()  # Blocking!
    result = conn.fetch("SELECT * FROM trades")
    return result
```

### Error Handling

- Use specific exception types
- Always log errors
- Provide context in error messages
- Clean up resources in `finally` blocks

```python
async def risky_operation():
    try:
        result = await perform_operation()
    except asyncpg.PostgresError as e:
        logger.error(f"Database error in risky_operation: {e}")
        raise
    except ValueError as e:
        logger.warning(f"Invalid value in risky_operation: {e}")
        return None
    finally:
        await cleanup()

    return result
```

## Testing

### Test Organization

```
tests/
├── test_agents/
│   ├── test_market_data.py
│   ├── test_meta_strategy.py
│   └── test_strategies/
│       ├── test_momentum.py
│       └── test_macd.py
├── test_core/
│   ├── test_event_bus.py
│   └── test_database.py
└── test_models/
    └── test_events.py
```

### Writing Tests

#### Test Structure

```python
import pytest
from src.agents.meta_strategy import MetaStrategyAgent

@pytest.mark.asyncio
async def test_meta_strategy_allocation():
    """Test that meta-strategy allocates capital correctly."""
    # Arrange
    agent = MetaStrategyAgent(config)
    strategies = ["momentum", "macd"]

    # Act
    allocations = await agent.calculate_allocations(strategies)

    # Assert
    assert sum(allocations.values()) == 100.0
    assert all(0 <= v <= 100 for v in allocations.values())
```

#### Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
async def event_bus():
    """Create event bus for testing."""
    bus = EventBus()
    yield bus
    await bus.close()

@pytest.fixture
async def mock_database():
    """Create mock database connection."""
    # Setup
    db = MockDatabase()
    await db.connect()

    yield db

    # Teardown
    await db.disconnect()
```

#### Mocking

Use unittest.mock or pytest-mock:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_market_data_with_mock():
    """Test market data agent with mocked WebSocket."""
    mock_ws = AsyncMock()
    mock_ws.recv.return_value = '{"symbol":"BTCUSDT","price":50000}'

    with patch('websockets.connect', return_value=mock_ws):
        agent = MarketDataAgent()
        await agent.start()
        # assertions
```

### Test Coverage

Aim for **>80% code coverage**:

```bash
# Run with coverage
pytest --cov=src tests/

# Generate HTML report
pytest --cov=src --cov-report=html tests/

# View report
open htmlcov/index.html
```

### Test Requirements

- All new features must include tests
- All bug fixes must include regression tests
- Tests must be independent and idempotent
- Tests should be fast (mock external services)
- Critical paths should have 100% coverage

## Documentation

### Code Documentation

- All public modules, classes, functions need docstrings
- Use Google-style docstrings
- Include examples in docstrings when helpful
- Document exceptions that can be raised

### User Documentation

When adding features that affect users:

1. Update relevant docs in `docs/`:
   - `USER_GUIDE.md` - User-facing features
   - `ARCHITECTURE.md` - Architecture changes
   - `API.md` - API changes
   - `TROUBLESHOOTING.md` - New common issues

2. Update `README.md` if it's a major feature

3. Add comments in `config/app.yaml` for new config options

### Example Documentation

```python
class AwesomeStrategy(StrategyAgent):
    """
    Strategy that does awesome things.

    This strategy uses the Awesome Indicator to generate signals
    when market conditions are favorable.

    Configuration (config/app.yaml):
        strategies:
          awesome:
            enabled: true
            symbol: BTCUSDT
            awesome_period: 14
            awesome_threshold: 0.5

    Attributes:
        awesome_period: Lookback period for indicator
        awesome_threshold: Signal threshold

    Example:
        >>> strategy = AwesomeStrategy(config)
        >>> await strategy.start()
    """

    def __init__(self, config: dict):
        """
        Initialize the Awesome Strategy.

        Args:
            config: Strategy configuration from app.yaml
        """
        super().__init__(config)
```

## Pull Request Process

### Before Submitting

Checklist:
- [ ] Tests pass (`pytest tests/`)
- [ ] Code is formatted (`black src/ tests/`)
- [ ] Linting passes (`flake8 src/ tests/`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Documentation is updated
- [ ] Commit messages follow conventions
- [ ] Branch is up to date with main

### Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

**Format**:
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(strategies): add Bollinger Bands strategy

Implements Bollinger Bands mean reversion strategy with
configurable periods and deviation multipliers.

Closes #42
```

```
fix(execution): handle slippage calculation correctly

Previously slippage was applied in wrong direction for
sell orders. Now correctly reduces fill price.

Fixes #87
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested these changes.

## Checklist
- [ ] Tests pass
- [ ] Code formatted (black)
- [ ] Linting passes (flake8)
- [ ] Documentation updated
- [ ] Commit messages follow convention

## Related Issues
Closes #123
Related to #456
```

### Review Process

1. **Automated Checks**: CI will run tests and linting
2. **Code Review**: Maintainer will review code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, PR will be merged
5. **Clean Up**: Delete your feature branch after merge

### Getting Your PR Merged

Tips for faster reviews:
- Keep PRs focused and small
- Write clear descriptions
- Add tests for new code
- Follow code standards
- Respond promptly to feedback
- Be patient and respectful

## Project Architecture

### Core Principles

1. **Event-Driven**: All communication through event bus
2. **Async/Await**: Non-blocking I/O throughout
3. **Type Safety**: Use type hints everywhere
4. **Testability**: Design for testing (dependency injection, mocking)
5. **SOLID Principles**: Single responsibility, open/closed, etc.

### Key Components

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

## Adding New Features

### Adding a New Strategy

1. **Create strategy file**:
```bash
touch src/agents/strategies/my_strategy.py
```

2. **Implement strategy**:
```python
from src.agents.strategy import StrategyAgent
from src.models.events import MarketTickEvent, TradingSignalEvent

class MyStrategy(StrategyAgent):
    """My awesome new strategy."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.my_param = config.get('my_param', 10)

    async def analyze(self, event: MarketTickEvent) -> TradingSignalEvent | None:
        """Analyze market data and generate signal."""
        # Your logic here
        pass
```

3. **Add tests**:
```bash
touch tests/test_agents/test_strategies/test_my_strategy.py
```

4. **Update configuration**:
```yaml
# config/app.yaml
strategies:
  my_strategy:
    enabled: true
    symbol: BTCUSDT
    my_param: 20
```

5. **Register strategy**:
```python
# src/agents/strategies/__init__.py
from .my_strategy import MyStrategy

__all__ = ['MyStrategy']
```

6. **Update documentation**:
- Add strategy to README.md
- Document in USER_GUIDE.md
- Add examples

### Adding a New Agent

1. **Create agent file**:
```bash
touch src/agents/my_agent.py
```

2. **Implement agent**:
```python
from src.agents.base import EventDrivenAgent
from src.models.events import MyEvent

class MyAgent(EventDrivenAgent):
    """My custom agent."""

    async def handle_event(self, event: MyEvent):
        """Handle incoming events."""
        pass
```

3. **Add to main**:
```python
# src/main.py
from src.agents.my_agent import MyAgent

agents.append(MyAgent(config))
```

4. **Add tests and documentation**

## Questions?

- **General Questions**: Open a GitHub Discussion
- **Bug Reports**: Open a GitHub Issue
- **Feature Requests**: Open a GitHub Issue with feature template
- **Security Issues**: Email security@example.com (do not open public issue)

## Recognition

Contributors will be recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- Project documentation

Thank you for contributing to Icarus! 🚀
