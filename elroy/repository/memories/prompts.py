from ...core.constants import MEMORY_WORD_COUNT_LIMIT
from ...utils.clock import local_now, utc_now

MEMORY_CONSOLIDATION = f"""# Memory Consolidation Task

Your task is to consolidate or reorganize two or more memory excerpts. These excerpts have been flagged as having overlapping or redundant content and require consolidation or reorganization.

Each excerpt has the following characteristics:
- They are written from the first-person perspective of an AI assistant.
- They consist of a title and a main body.

If the excerpts cover the same topic, consolidate them into a single, cohesive memory. If they address distinct topics, create separate, reorganized memories for each.

## Dates and times

The memories being consolidated can be from any time in the past. Note that the current time is {local_now()}, or {utc_now()} UTC

Use ISO 8601 format for dates and times to ensure references remain unambiguous in future retrievals.


## Style Guidelines

- Limit each new memory excerpt to {MEMORY_WORD_COUNT_LIMIT} words.

## Memory Title Guidelines

Examples of effective and ineffective memory titles are provided:

**Ineffective:**
- UserFoo's project progress and personal goals: 'Personal goals' is too vague; two topics are referenced.

**Effective:**
- UserFoo's project on building a treehouse: Specific and topic-focused.
- UserFoo's goal to be more thoughtful in conversation: Specifies a clear goal.

**Ineffective:**
- UserFoo's weekend plans: 'Weekend plans' lacks specificity, and dates should be in ISO 8601 format.

**Effective:**
- UserFoo's plan to attend a concert on 2022-02-11: Specific with a defined date.

**Ineffective:**
- UserFoo's preferred name and well-being: Covers two distinct topics; 'well-being' is generic.

**Effective:**
- UserFoo's preferred name: Focused on a single topic.
- UserFoo's feeling of rejuvenation after rest: Clarifies the topic.

## Formatting

Responses should be in Markdown format, adhering strictly to these guidelines:

```markdown
# Memory Consolidation Reasoning
Provide a clear explanation of the consolidation or reorganization choices. Justify which information was included or omitted, and detail organizational strategies and considerations.

## Memory Title 1
Include all pertinent content from the original memories for the specified topic. Optionally, add reflections on how the assistant should respond to this information, along with any open questions the memory poses.

## Memory Title 2  (If necessary)
Detail the content for a second memory, should distinct topics require individual consolidation. Repeat as needed.
```

## Examples

Here are examples of effective consolidation:

### Input:
```markdown
# Memory Consolidation Input
## UserFoo's exercise progress for 2024-01-04
UserFoo felt tired but completed a 5-mile run. Encourage recognition of this achievement.

## UserFoo's workout for 2024-01-04
UserFoo did a long run as marathon prep. Encourage consistency!
```

### Output:
```markdown
# Memory Consolidation Reasoning
I combined the two memories, as they both describe the same workout and recommend similar interactions. I included specific marathon prep details to maintain context.

## UserFoo's exercise progress for 2024-01-04
Despite tiredness, UserFoo completed a 5-mile marathon prep run. I should consider inquiring about the marathon date and continue to offer encouragement.
```

### Input:
```markdown
# Memory Consolidation Input
## UserFoo's reading list update for 2024-02-15
UserFoo added several books to their reading list, including "The Pragmatic Programmer" and "Clean Code". I should track which ones they finish to offer recommendations.

## UserFoo's book recommendations from colleagues
UserFoo received recommendations from colleagues, specifically "The Pragmatic Programmer" and "Code Complete". They seemed interested in starting with these.
```

### Output:
```markdown
# Memory Consolidation Reasoning
I merged the two memories because they both pertain to UserFoo's interest in expanding their reading list with programming books. I prioritized the mention of recommendations from colleagues, as it might influence UserFoo's reading behavior.

## UserFoo's updated reading list as of 2024-02-15
UserFoo expanded their reading list, adding "The Pragmatic Programmer" and "Clean Code". Colleagues recommended "The Pragmatic Programmer" and "Code Complete", sparking UserFoo's interest in starting with the recommended titles. I should note when UserFoo completes a book to provide further recommendations.
```

### Input:
```markdown
# Memory Consolidation Input
## UserFoo's preferred programming languages
UserFoo enjoys working with Python and JavaScript. They mentioned an interest in exploring new frameworks in these languages.

## UserFoo's project interests
UserFoo is interested in developing a web application using Python. They are also keen on contributing to an open-source JavaScript library.
```

### Output:
```markdown
# Memory Consolidation Reasoning
I reorganized the memories since both touch on UserFoo's preferred programming languages and their project interests. Given the overlap in topics, separate memories were created to better capture their preferences and ongoing endeavors clearly.

## UserFoo's preferred programming languages
UserFoo enjoys programming with Python and JavaScript. They are interested in exploring new frameworks within these languages to advance their skills and projects.

## UserFoo's current project interests
Currently, UserFoo is focused on developing a web application using Python while also expressing a desire to contribute to an open-source JavaScript library. These projects reflect their interest in leveraging their preferred languages in practical contexts.
```
"""
