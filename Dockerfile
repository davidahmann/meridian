FROM python:3.9-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

COPY examples/ examples/

# Install dependencies and project
RUN uv pip install --system .[ui]

# Expose port
EXPOSE 8000

# Default command
CMD ["meridian", "serve", "examples/basic_features.py", "--host", "0.0.0.0", "--port", "8000"]
