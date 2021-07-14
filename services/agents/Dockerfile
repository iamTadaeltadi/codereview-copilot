FROM langchain/langgraph-api:3.11

RUN pip install poetry==2.1.3

WORKDIR /app/agent_runtime
ADD ./ ./
RUN poetry self add poetry-plugin-export
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes
RUN pip install -r requirements.txt

ENV LANGSERVE_GRAPHS='{"review": "/app/agent_runtime/parallel_review_pipeline.py:graph","feedback": "/app/agent_runtime/feedback_pipeline.py:graph"}'
