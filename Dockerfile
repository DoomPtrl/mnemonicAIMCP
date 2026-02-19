FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the code/artifacts needed at runtime (avoid huge dataset exports)
COPY lexicon ./lexicon
COPY artifacts ./artifacts
COPY openai-chatkit-starter-app ./openai-chatkit-starter-app
COPY app.py ./app.py

# Cloud Run injects PORT (defaults to 8080 locally)
ENV PORT=8080
EXPOSE 8080

# Use your real module:app below (examples: main:app, app:app, server:app)
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
