# Tests

This directory contains standalone Python integration and unit tests that complement the Django test suite in `backend/core/tests.py`.

## Coverage areas

- backend service helpers in `tests/test_backend_services.py`
- backend API flows in `tests/test_backend_api_flows.py` and `tests/test_backend_review_sources.py`
- GitHub webhook handler behavior in `tests/test_webhook_handler.py`
- agent runtime utility behavior in `tests/test_agent_runtime_utils.py` and `tests/test_runtime_tooling.py`
- agent graph reporting and execution in `tests/test_review_runtime_graph_reporting.py` and `tests/test_review_runtime_execution.py`
- agent prompt wiring in `tests/test_review_runtime_agents.py`
- graph analyzer retrieval in `tests/test_graph_analyzer.py` and `tests/test_code_context_graph_loading.py`

## Running

From the repository root:

```bash
bash scripts/test.sh
```

Or run only these suites:

```bash
export DJANGO_SETTINGS_MODULE=django_backend.test_settings
export PYTHONPATH="$PWD/backend:$PWD/agent_runtime:$PWD/graph_analyzer"
python -m unittest discover -s tests -p 'test_*.py' -v
```
