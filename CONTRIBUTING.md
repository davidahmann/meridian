# Contributing to Meridian

We love your input! We want to make contributing to Meridian as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Setup

Meridian uses `uv` for dependency management and `make` for common tasks.

### 1. Prerequisites
- Python 3.9+
- [uv](https://github.com/astral-sh/uv) (for fast dependency management)
- Node.js 18+ (for the Next.js UI)

### 2. Setup
Fork the repo, then:

```bash
git clone https://github.com/<your-username>/meridian.git
cd meridian

# Create virtualenv and install dependencies
make setup
```

### 3. Common Commands

We have a comprehensive `Makefile` to make development easy:

- **`make test`**: Run the test suite (pytest).
- **`make lint`**: Run formatters and linters (ruff, mypy).
- **`make ui`**: Run the Next.js UI locally.
- **`make serve`**: Run the API server with Terminal UI.
- **`make build`**: Build the Python distribution (wheel/sdist).
- **`make docker-up`**: Start local Postgres/Redis stack.

### 4. Pull Request Process
1.  Ensure `make test` and `make lint` pass locally.
2.  If you added a new feature, add a test case.
3.  Open a PR against the `main` branch.

## Any contributions you make will be under the Apache 2.0 Software License

In short, when you submit code changes, your submissions are understood to be under the same [Apache 2.0 License](http://www.apache.org/licenses/LICENSE-2.0) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issue tracker](https://github.com/davidahmann/meridian/issues)

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
    - Be specific!
    - Give sample code if you can.
- What you expected would happen
- What actually happened
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## License

By contributing, you agree that your contributions will be licensed under its Apache 2.0 License.
