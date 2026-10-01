# Ollama on a Colab GPU

`TenderMind_Ollama_Colab.ipynb` runs the app's Ollama models on a free Colab T4 GPU, while the app itself
keeps running on your own machine. The notebook's first cell has the step-by-step instructions.

How it works:
- Ollama is pinned to the same version as `docker-compose.yml` and loads `qwen2.5:3b` and `qwen3:4b`.
- A password gate sits in front of Ollama: requests without the password get 401, and only the endpoints
  the app calls are allowed (others get 403). Re-running cell 6 creates a new password.
- A Cloudflare quick tunnel gives a public HTTPS link. Cell 8 checks the link from outside and prints the
  `OLLAMA_BASE_URL=https://tm:<password>@...` line for your local `.env`. That line contains the password,
  so it belongs only in `.env` (git-ignored), never in chat, issues or commits.
- The link dies when the Colab session ends (at most 12 hours on the free tier). Cell 10 closes it earlier.

## Model benchmark on the T4 (2026-10-01)

Same harness as Stage 5A (`evaluation/stage5a/run_5a.py`, prompt v2, temperature 0), sent through the gate
and tunnel one request at a time. 37 gold rows: 16 primary (Stage 3I) + 21 Sarai. The 33 secondary rows and
the Arabic rows were not available on this machine, so they are not included. Three runs per model.

| Model | Correct of 37 (3 runs) | Median latency per row |
|---|---|---|
| qwen2.5:3b (production) | 32, 32, 32 | 1.60 s |
| qwen3:4b-instruct-2507-q4_K_M | 35, 35, 35 | 2.25 s |
| gemma3:12b | 34, 34, 34 | 4.94 s |
| qwen2.5:7b | 33, 33, 33 | 2.47 s |
| qwen3:4b | 33, 33, 33 | 2.67 s |

How to read it:
- The three runs were identical row by row for every model (temperature 0), so they show the results are
  repeatable. They do not add independent evidence.
- Against production, qwen3:4b-instruct-2507 fixes 3 rows (REQ-G, REQ-J, REQ-P) and breaks none.
  On 37 rows that is not statistically proven (exact McNemar p = 0.25). It points the right way, but a larger
  gold set is needed before switching models.
- Two rows are wrong for every model: 3i-09 (gold EQUIPMENT, all say TECHNICAL) and REQ-E. Check the gold
  labels for these two before blaming the models.
- Ollama ran with `OLLAMA_NUM_PARALLEL=4`, which was set in the runtime, not in the notebook. Requests were
  sent one at a time, so it did not affect these numbers. A separate load test showed that with 8 requests at
  once, throughput rose from about 87 to 124 per minute, but answers started to differ from the one-at-a-time
  answers. That needs a quality check before the setting goes into the notebook.
