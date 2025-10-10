# Contributing Guide

Thank you for your interest in contributing to Igloo MCP! This guide will help you get started with development and submitting contributions.

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Git
- Snowflake account (for testing)

### Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/Evan-Kim2028/igloo-mcp.git
   cd igloo-mcp
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

4. **Verify installation**:
   ```bash
   # Check MCP server is available
   uv run igloo-mcp --help
   # Should show: igloo-mcp MCP Server
   
   # Verify Python package
   python -c "import igloo_mcp; print(igloo_mcp.__version__)"
   ```

## Making Changes

### Branching Strategy

- Create feature branches from `main`
- Use descriptive branch names: `feature/add-new-tool`, `fix/authentication-bug`
- Keep branches focused on a single feature or fix

### Code Style

We use automated formatting and linting:

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Type checking
uv run mypy src/
```

### Testing

Run the test suite:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/igloo_mcp

# Run specific test file
uv run pytest tests/test_specific.py
```

### Documentation

- Update relevant documentation for any user-facing changes
- Follow the existing documentation style
- Include examples for new features
- Update API documentation for new tools or parameters

## Pull Requests

### Before Submitting

1. **Run all checks**:
   ```bash
   uv run ruff check .
   uv run mypy src/
   uv run pytest
   ```

2. **Test your changes**:
   - Test with real Snowflake connections
   - Verify MCP interface and Python API work
   - Test error scenarios and edge cases

3. **Update documentation**:
   - Update relevant docs
   - Add examples if applicable
   - Update version numbers if needed

### PR Process

1. **Create a pull request** with a clear description
2. **Link any related issues**
3. **Include testing instructions** for reviewers
4. **Request review** from maintainers

### PR Description Template

```markdown
## Description
Brief description of changes

## Changes
- List of specific changes made
- New features added
- Bugs fixed

## Testing
- How to test the changes
- What scenarios were tested
- Any known limitations

## Documentation
- What documentation was updated
- Any new examples added

## Related Issues
Closes #123
```

## Development Guidelines

### Architecture

- Follow the service layer pattern (see `src/igloo_mcp/service_layer/`)
- Keep MCP interface as thin wrapper around services
- Use dependency injection for testability
- Maintain backward compatibility when possible
- MCP-only architecture since v2.0.0

### Error Handling

- Use structured error messages
- Include helpful context in errors
- Follow MCP protocol standards
- Provide actionable error messages

### Performance

- Use async/await for I/O operations
- Implement proper timeouts
- Optimize for large datasets
- Consider memory usage

## Release Process

### Version Bumping

- Update version in `pyproject.toml`
- Update version references in documentation
- Update `__version__` in `src/igloo_mcp/__init__.py`
- Create release notes in CHANGELOG.md

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] Version numbers consistent
- [ ] Release notes prepared
- [ ] Changelog updated

## Getting Help

- **Issues**: Use GitHub Issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check existing docs first
- **Code Review**: Ask questions during PR review

## Code of Conduct

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming environment for all contributors.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Igloo MCP! 🐻‍❄️
