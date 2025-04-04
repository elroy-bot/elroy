# How to run benchmark

1. download tar file [here](https://drive.google.com/file/d/1zJgtYRFhOh5zDQzzatiddfjYhFSnyQ80/view)
1. Extract to [data dir](./data)
1. Set any desired Elroy params as env vars
1. If running with tracing, run `phoenix serve` (if so ensure to set`ELROY_ENABLE_TRACING=1`)
3. run with `./run.py {PATH_TO_DATA_JSON} {OPTIONAL_RUN_ID}`

for example,
```bash
export ELROY_CHAT_MODEL=azure/gpt-4o-mini
export ELROY_EMBEDDING_MODEL=azure/text-embedding-3-small
export ELROY_ENABLE_TRACING=1
export ELROY_LOG_LEVEL=WARN
export ELROY_TRACING_APP_NAME="elroy-benchmark"
export ELROY_CHAT_MODEL=azure/gpt-4o-mini
export ELROY_EMBEDDING_MODEL=azure/text-embedding-3-small
./run.py ./data/longmemeval_s.json # to run with a fresh session
```

Run ID can be used to resume an interrupted run:

```bash
./run.py data/longmemeval_s.json run_1742589794
```

Elroy will run off a `elroy.db` sqlite. Elroy's answers, along with actual answers, are in `ANSWER` table.

*Expect to consume roughly 1m tokens / question*



TODO:
- add running of scoring script
- add token use efficiency optimizations
- add session metadata.




The following is an exceprt from the source data readme:

## 📜 Dataset Format (via [LongMemEvalReadme](https://github.com/xiaowu0162/LongMemEval/blob/main/README.md))

Three files are included in the data package:
* `longmemeval_s.json`: The LongMemEval_S introduced in the paper. Concatenating all the chat history roughly consumes 115k tokens (~40 history sessions) for Llama 3.
* `longmemeval_m.json`: The LongMemEval_M introduced in the paper. Each chat history contains roughly 500 sessions.
* `longmemeval_oracle.json`: LongMemEval with oracle retrieval. Only the evidence sessions are included in the history.

Within each file, there are 500 evaluation instances, each of which contains the following fields:
* `question_id`: the unique id for each question.
* `question_type`: one of `single-session-user`, `single-session-assistant`, `single-session-preference`, `temporal-reasoning`, `knowledge-update`, and `multi-session`. If `question_id` ends with `_abs`, then the question is an `abstention` question.
* `question`: the question content.
* `answer`: the expected answer from the model.
* `question_date`: the date of the question.
* `haystack_session_ids`: a list of the ids of the history sessions (sorted by timestamp for `longmemeval_s.json` and `longmemeval_m.json`; not sorted for `longmemeval_oracle.json`).
* `haystack_dates`: a list of the timestamps of the history sessions.
* `haystack_sessions`: a list of the actual contents of the user-assistant chat history sessions. Each session is a list of turns. Each turn is a direct with the format `{"role": user/assistant, "content": message content}`. For the turns that contain the required evidence, an additional field `has_answer: true` is provided. This label is used for turn-level memory recall accuracy evaluation.
* `answer_session_ids`: a list of session ids that represent the evidence sessions. This is used for session-level memory recall accuracy evaluation.
