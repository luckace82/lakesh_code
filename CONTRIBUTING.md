# Contributing to Lakesh

Thank you for your interest in contributing to Lakesh! This document provides guidelines for contributing to the project.

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/lakesh_code.git`
3. Navigate to the project: `cd lakesh_code`
4. Create a virtual environment: `python3 -m venv venv`
5. Activate the virtual environment:
   - Linux/macOS: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
6. Install dependencies: `pip install -r requirements.txt`
7. Copy environment file: `cp .env.example .env`
8. Configure `.env` as needed

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and concise
- Remove excessive comments (code should be self-documenting)

## Project Structure

```
lakesh_code/
├── analyzer/          # Code analysis tools
│   ├── parser.py     # AST-based Python parser
│   └── extractor.py  # Graph extraction
├── lakesh            # Main CLI script
├── lakesh_server.py  # HTTP server
├── agent.py          # Agent logic
├── indexer.py        # Codebase indexer
├── tools.py          # Tool definitions
├── gpu_setup.sh      # GPU configuration (Linux)
├── gpu_ram_split.sh  # GPU/RAM split (Linux)
└── requirements.txt  # Python dependencies
```

## Making Changes

1. Create a new branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Test thoroughly on your local system
4. Commit with clear messages: `git commit -m "Add: description of change"`
5. Push to your fork: `git push origin feature/your-feature-name`
6. Open a pull request

## Platform Compatibility

- Ensure changes work on Linux, macOS, and Windows
- Use relative paths (no hardcoded absolute paths)
- Add platform detection for OS-specific features
- Test on multiple platforms if possible

## Testing

- Test the CLI: `./lakesh "your test query"`
- Test the server: `uvicorn lakesh_server:app --port 8765`
- Test GPU setup scripts on Linux
- Verify cross-platform compatibility

## Documentation

- Update README.md for user-facing changes
- Add inline comments for complex logic only
- Keep documentation concise and clear
- Update .env.example if adding new environment variables

## Pull Request Guidelines

- Describe what your PR does
- Link to related issues
- Include screenshots for UI changes
- Ensure all tests pass
- Request review from maintainers

## Questions?

Feel free to open an issue for questions or discussion.
