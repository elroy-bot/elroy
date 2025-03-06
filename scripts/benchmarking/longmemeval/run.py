import logging
import os
import sys

from answer_processors import ANSWER_FUNCS
from evaluate import create_answer, get_db_url, get_engine, get_or_create_message_cursor
from freezegun import freeze_time
from litellm import completion
from message_processors import get_message_func
from messages import get_messages
from questions import QUESTIONS, Question
from sqlmodel import Session

from elroy.api import Elroy
from elroy.core.constants import USER

from ....elroy.messenger.error_recovery import retry_completion_api_return

MESSAGES_BETWEEN_MEMORY = 20

# Configure root logger to output to stdout
logging.basicConfig(
    level=logging.INFO,  # Set appropriate level
    format="%(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Get a logger for this module
logger = logging.getLogger("benchmark")
logger.setLevel(logging.INFO)  # Adjust level as needed


def main(token: str, message_func_name: str):
    question_idx = 0
    ai = Elroy(
        token=token + "__" + message_func_name,
        database_url=get_db_url(),
        check_db_migration=False,
        show_tool_calls=False,
        messages_between_memory=MESSAGES_BETWEEN_MEMORY,
    )
    logger.info(f"Running with user token: {token + '__' + message_func_name}")

    with Session(get_engine()) as session:
        message_func = get_message_func(message_func_name)
        cursor = get_or_create_message_cursor(session=session, token=token, message_fn=message_func)
        cursor_id = cursor.id
        assert cursor_id
        messages = get_messages()[cursor.message_idx :]

        for idx, message in enumerate(messages):
            current_question = QUESTIONS[question_idx]
            while message.session_datetime > current_question.question_date:
                logger.info(
                    f"Answering question {current_question.question} with date {current_question.question_date} at message index {idx} / ({len(messages)}) ({message.session_datetime})"
                )
                ai.context_refresh()
                ai.reset_messages()
                with freeze_time(current_question.question_date):
                    for answer_func in ANSWER_FUNCS:
                        elroy_answer = answer_func(ai, message.content)
                        create_answer(
                            session=session,
                            answer_fn=answer_func,
                            elroy_answer=elroy_answer,
                            question=current_question,
                            cursor_id=cursor_id,
                            is_correct=eval_answer(current_question, elroy_answer),
                            judge="",
                        )
                question_idx += 1
                current_question = QUESTIONS[question_idx]
            logger.info(f"Processing messages {idx} / {len(messages)}")
            with freeze_time(message.session_datetime):
                message_func(ai, message)
            cursor.message_idx += 1
            session.add(cursor)
            session.commit()
            session.refresh(cursor)

        logger.info("Run is complete")


# @retry_completion_api_return
def eval_answer(question: Question, elroy_answer: str) -> bool:
    # via https://github.com/xiaowu0162/LongMemEval/blob/main/src/evaluation/evaluate_qa.py#L20

    if not question.is_abstention:
        if question.question_type in ["single-session-user", "single-session-assistant", "multi-session"]:
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question.question, question.answer, elroy_answer)
        elif question.question_type == "temporal-reasoning":
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's response is still correct. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question.question, question.answer, elroy_answer)
        elif question.question_type == "knowledge-update":
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question.question, question.answer, elroy_answer)
        elif question.question_type == "single-session-preference":
            template = "I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question.question, question.answer, elroy_answer)
        else:
            raise NotImplementedError
    else:
        template = "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only."
        prompt = template.format(question.question, question.answer, elroy_answer)

    resp: str = (
        completion(
            model=os.environ["ELROY_BENCHMARK_JUDGE_MODEL"],
            messages=[{"role": USER, "content": prompt}],
            temperature=0,
            max_tokens=10,
            stream=False,
        )
        .choices[0]  # type: ignore
        .message.content.strip()  # type: ignore
    )  # type: ignore

    is_correct = "yes" in resp.lower()
    return is_correct


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the benchmarking script.")
    parser.add_argument(
        "--token",
        type=str,
        required=True,
        help="The token to use for the benchmarking.",
    )
    parser.add_argument(
        "--message_func",
        type=str,
        required=True,
        help="The message function to use for the benchmarking.",
    )

    args = parser.parse_args()
    main(args.token, args.message_func)
