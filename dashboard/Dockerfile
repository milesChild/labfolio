FROM python:3.11-slim

WORKDIR /dashboard

# copy and install dependencies
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy application code
COPY dashboard/ .
COPY common/ common/

# expose dashboard port
EXPOSE 8501

# run dashboard locally
CMD ["streamlit", "run", "dashboard.py", "--server.address", "0.0.0.0"]
