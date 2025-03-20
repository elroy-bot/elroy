## 📜 Dataset Format

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
