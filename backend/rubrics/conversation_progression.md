Score conversation progression from 0 to 10 (10 = every turn moved the call forward; nothing was asked or said twice without reason).

Evaluate the **whole call** for forward motion. The signature voice-bot failures here are: re-asking for information the customer already provided, restating details the bot already gave, looping on the same step without progress, and asking overly broad questions when the bot already had enough information to act.

Do not penalise legitimate confirmations (repeating an order number back once to verify) or recaps the customer asked for.

## Bands
- 9-10: Every exchange advances the task; information given once is used throughout; questions are specific and necessary.
- 7-8: One isolated redundancy or unnecessary question that did not stall the call.
- 4-6: Several redundancies or one clear loop — the customer had to repeat themselves or hear the same content again.
- 2-3: The call visibly stalls — repeated re-asking, circular exchanges, little net progress across multiple turns.
- 0-1: The conversation loops without meaningful progress; the customer's information is effectively ignored.

## Violation types
- information_reask: The bot asks for information the customer already provided.
- redundant_statement: The bot restates details it already told the customer, unprompted.
- no_progress_loop: An exchange repeats without advancing the task.
- poor_question: The bot asks a broad or unnecessary question when it already had what it needed.
