FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ .

# Learner data directory — will be overridden by a persistent volume mount if configured
ENV SOFI_LEARNERS_PATH=/app/learners
RUN mkdir -p /app/learners

# Bake the git commit SHA into the image so we can always tell what code is running.
# Pass with: docker build --build-arg GIT_COMMIT=$(git rev-parse --short HEAD)
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT

CMD ["python", "main.py"]
