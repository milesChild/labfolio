FROM python:3.11-slim

WORKDIR /api

# copy and install dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy application code
COPY api/ .
COPY common/ common/

# expose API port
EXPOSE 8000

# run API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
