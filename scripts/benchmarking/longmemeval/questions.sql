-- always correct
select question_id from (

SELECT
     question_id,
     question_type,
     round(COUNT(CASE WHEN is_correct = TRUE THEN 1 END) * 1.0 / count(*), 2) as ratio_correct,
    --  COUNT(CASE WHEN is_correct = FALSE THEN 1 END) AS times_answered_incorrect,
     BOOL_OR(CASE WHEN is_active = TRUE THEN is_correct ELSE NULL END) AS is_most_recent_answer_correct
 FROM
     public.answer
 WHERE
     is_correct IS NOT NULL
 GROUP BY
     question_id, question_type
 ORDER BY
     question_type, 3 desc
) t where ratio_correct >= 1 and question_id not ilike '%_abs';


-- has been correct, most recent is correct
select question_id from (

SELECT
     question_id,
     question_type,
     round(COUNT(CASE WHEN is_correct = TRUE THEN 1 END) * 1.0 / count(*), 2) as ratio_correct,
    --  COUNT(CASE WHEN is_correct = FALSE THEN 1 END) AS times_answered_incorrect,
     BOOL_OR(CASE WHEN is_active = TRUE THEN is_correct ELSE NULL END) AS is_most_recent_answer_correct
 FROM
     public.answer
 WHERE
     is_correct IS NOT NULL
 GROUP BY
     question_id, question_type
 ORDER BY
     question_type, 3 desc
) t where ratio_correct >0 and ratio_correct < 1 and  is_most_recent_answer_correct and question_id not ilike '%_abs';


-- has been correct, most recent is wrong
select question_id from (

SELECT
     question_id,
     question_type,
     round(COUNT(CASE WHEN is_correct = TRUE THEN 1 END) * 1.0 / count(*), 2) as ratio_correct,
    --  COUNT(CASE WHEN is_correct = FALSE THEN 1 END) AS times_answered_incorrect,
     BOOL_OR(CASE WHEN is_active = TRUE THEN is_correct ELSE NULL END) AS is_most_recent_answer_correct
 FROM
     public.answer
 WHERE
     is_correct IS NOT NULL
 GROUP BY
     question_id, question_type
 ORDER BY
     question_type, 3 desc
) t where ratio_correct >0 and ratio_correct < 1 and  not is_most_recent_answer_correct and question_id not ilike '%_abs';


select
    run_token,
    question_type,
    sum(case when ratio_correct = 1 then 1 else 0 end) as alway_correct,
    sum(case when ratio_correct > 0 and ratio_correct < 1 and is_most_recent_answer_correct then 1 else 0 end) as has_been_correct_most_recent_correct,
    sum(case when ratio_correct > 0 and ratio_correct < 1 and not is_most_recent_answer_correct then 1 else 0 end) as has_been_correct_most_recent_wrong,
    sum(case when ratio_correct = 0 then 1 else 0 end) as never_correct
from (
SELECT
     question_id,
     run_token,
     question_type,
     round(COUNT(CASE WHEN is_correct = TRUE THEN 1 END) * 1.0 / count(*), 2) as ratio_correct,
     BOOL_OR(CASE WHEN is_active = TRUE THEN is_correct ELSE NULL END) AS is_most_recent_answer_correct
 FROM
     public.answer
 WHERE
     is_correct IS NOT NULL and run_token ilike '%2025-04-03%'
 GROUP BY
     question_id, question_type, run_token
 ORDER BY
     question_type, 3 desc
) t where question_id not ilike '%_abs' group by 1,2 order by 1;


-- 2025-04-01
--        question_type       | alway_correct | has_been_correct_most_recent_correct | has_been_correct_most_recent_wrong | never_correct
-- ---------------------------+---------------+--------------------------------------+------------------------------------+---------------
--  knowledge-update          |             8 |                                    5 |                                  1 |            13
--  multi-session             |             5 |                                    6 |                                  0 |            45
--  single-session-assistant  |             1 |                                    1 |                                  0 |             6
--  single-session-preference |             1 |                                    3 |                                  0 |             8
--  single-session-user       |             9 |                                    5 |                                  1 |            12
--  temporal-reasoning        |             2 |                                    1 |                                  0 |            11

