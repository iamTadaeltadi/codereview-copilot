# Third-party content in data/

The code in this repository is Apache-2.0 (see `LICENSE` and `NOTICE`). The
benchmark files in `data/` also contain excerpts of other projects' source
code: definitions, callers, diffs and short windows around them, taken at the
commit recorded in each task. **Those excerpts are not relicensed.** Each one
remains under the license of the repository it came from, listed below. They
are included only so that the experiments can be reproduced. Licenses were
read from each repository on 2 October 2026.

## Source repositories

| Repository | License | Appears in |
|---|---|---|
| Avaiga/taipy | Apache-2.0 | regressions |
| OpenMined/PySyft | Apache-2.0 | benchmark |
| PostHog/posthog | MIT, except `ee/` (PostHog EE license) | benchmark |
| Textualize/rich | MIT | foreign snippets |
| ansible/ansible | GPL-3.0 | benchmark |
| apache/airflow | Apache-2.0 | benchmark |
| bridgecrewio/checkov | Apache-2.0 | benchmark |
| certbot/certbot | Apache-2.0 (see repository) | regressions |
| conan-io/conan | MIT | benchmark |
| dask/dask | BSD-3-Clause | benchmark |
| dbt-labs/dbt-core | Apache-2.0 | regressions |
| deepset-ai/haystack | Apache-2.0 | benchmark |
| dmlc/dgl | Apache-2.0 | benchmark |
| frappe/frappe | MIT | benchmark |
| geldata/gel | Apache-2.0 | benchmark |
| getsentry/sentry | FSL-1.1-Apache-2.0 | benchmark |
| gradio-app/gradio | Apache-2.0 | benchmark |
| home-assistant/core | Apache-2.0 | benchmark |
| hpcaitech/ColossalAI | Apache-2.0 | benchmark |
| huggingface/datasets | Apache-2.0 | benchmark |
| huggingface/diffusers | Apache-2.0 | benchmark |
| hummingbot/hummingbot | Apache-2.0 | regressions |
| letta-ai/letta | Apache-2.0 | regressions |
| localstack/localstack | Apache-2.0 | benchmark |
| marimo-team/marimo | Apache-2.0 | benchmark |
| matplotlib/matplotlib | Matplotlib License (PSF-based) | benchmark |
| microsoft/autogen | MIT for code (`LICENSE-CODE`), CC-BY-4.0 for docs | benchmark |
| mlflow/mlflow | Apache-2.0 | benchmark |
| modin-project/modin | Apache-2.0 | benchmark |
| netbox-community/netbox | Apache-2.0 | benchmark |
| networkx/networkx | BSD-3-Clause | benchmark |
| numba/numba | BSD-2-Clause | benchmark |
| pallets/click | BSD-3-Clause | foreign snippets |
| pandas-dev/pandas | BSD-3-Clause | benchmark |
| psf/requests | Apache-2.0 | foreign snippets |
| pydantic/pydantic | MIT | benchmark |
| python-telegram-bot/python-telegram-bot | LGPL-3.0 | regressions |
| python/mypy | MIT | benchmark |
| pytorch/vision | BSD-3-Clause | benchmark |
| ray-project/ray | Apache-2.0 | benchmark |
| reflex-dev/reflex | Apache-2.0 | benchmark |
| scikit-learn/scikit-learn | BSD-3-Clause | benchmark |
| scipy/scipy | BSD-3-Clause | benchmark |
| sqlfluff/sqlfluff | MIT | benchmark |
| sympy/sympy | BSD-3-Clause | benchmark |
| tobymao/sqlglot | MIT | benchmark |
| voxel51/fiftyone | Apache-2.0 | benchmark |
| xorbitsai/inference | Apache-2.0 | benchmark |

"benchmark" means `crossfile*.jsonl`, the twins and the chains; "regressions"
means `regressions*.jsonl`; "foreign snippets" means `foreign-snippets.jsonl`.

## c-CRAB

`stage3_testgen_verified.jsonl`, `testgen_combined.zip` and
`preprocess_dataset.jsonl` come from c-CRAB, Zhang et al., *Code Review Agent
Benchmark*, arXiv:2603.23448, published at
https://github.com/c-CRAB-Benchmark/dataset (`results_preprocessed/` and
`raw_results_compressed/`); c-CRAB itself builds on SWE-CARE pull requests.
The c-CRAB repository had no license file on 2 October 2026. The files are included unmodified, with attribution, so
the c-CRAB results in the paper can be reproduced; please cite the c-CRAB paper
if you use them. If the c-CRAB authors prefer these files not to be
redistributed here, they will be removed and replaced by a download script.

## Removal

If you maintain one of these projects and want an excerpt removed, open an
issue on this repository.
