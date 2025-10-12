# Use Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set Python unbuffered mode
ENV PYTHONUNBUFFERED=1

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY airplane_server.py http_wrapper.py ./

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Expose port for HTTP servers (Render sets $PORT)
ENV PORT=8080
EXPOSE $PORT

# Run the HTTP wrapper via uvicorn (shell form for variable expansion)
CMD uvicorn http_wrapper:app --host 0.0.0.0 --port $PORT