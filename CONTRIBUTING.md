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

### Branching Strategy (GitFlow)

- `main` always reflects the latest production release. It only receives merges from release or hotfix branches.
- `develop` is the integration branch for the next release cycle (currently 0.2.4). All feature work targets `develop`.
- `feature/<issue-id>-short-description` branches are created from `develop`, rebased frequently, and merged back via PRs.
- `release/x.y.z` branches are cut from `develop` once the feature set is ready. Use these branches to bump versions, finalize docs, and run the hardening/test pass before merging to `main` and back to `develop`.
- `hotfix/<issue>` branches fork from `main` to patch urgent production issues; merge them into both `main` and `develop` after verification.

Branch lifecycle example for 0.2.3:

```bash
git checkout main && git pull
git checkout develop || git checkout -b develop
git checkout -b feature/issue-123-honor-union-select develop
# ... work, PR into develop ...
git checkout develop && git pull && git checkout -b release/0.2.3
# version bumps + QA, then merge release/0.2.3 -> main, tag, and back-merge into develop
```

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

### Workflow Overview

For the 0.2.3 cycle we followed GitFlow (0.2.4 on this branch follows the same pattern):

1. Keep `develop` in sync with `origin/develop`; all feature PRs must target it until the 0.2.3 release branch is cut.
2. When the backlog for 0.2.3 is ready, branch `release/0.2.3` from `develop`.
3. On the release branch:
   - Bump versions
   - Update changelog/docs
   - Run the full QA/test suite and fix regressions directly on the branch
4. Merge `release/0.2.3` into `main`, tag `v0.2.3`, and push.
5. Merge the same release branch back into `develop` so future work inherits the release-only commits.
6. Delete the release branch when finished. Repeat for the next version (0.2.4, etc.).

Hotfixes fork from `main` (e.g., `hotfix/0.2.3-connection-leak`) and land back into both `main` and `develop` after tagging.

### Version Bumping

- Update `pyproject.toml`
- Update documentation references
- Update `src/igloo_mcp/__init__.py`
- Write release notes in `CHANGELOG.md`
- Tag the merge commit (`git tag v0.2.3 && git push origin v0.2.3`)

### Release Checklist

- [ ] `release/x.y.z` branch created from `develop`
- [ ] Ruff, mypy, and pytest succeed
- [ ] Documentation and changelog updated
- [ ] Version numbers consistent across code/docs
- [ ] Release notes committed
- [ ] Tag pushed and branch merged back into `develop`

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
