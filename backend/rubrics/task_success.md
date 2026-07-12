Score task success from 0 to 10 (10 = the customer's goal for the call was clearly achieved).

Evaluate the **entire call** as one arc (greeting through outcome). Infer the customer's goal from what they say across the conversation — do not treat a single short utterance (e.g. "Wait.") as the whole task.

Consider whether the voice bot resolved the request, delivered correct information, completed the transaction, or reached a sensible handoff/end state. Give partial credit for sub-goals completed (goal identified, steps progressed, confirmation given) even when the overall goal was not fully achieved.

The computed timing summary is context only; task success is primarily from transcript content and how the call ended.

## Bands
- 9-10: Goal explicitly achieved and confirmed (booking made, issue resolved, correct information delivered, transaction completed).
- 7-8: Goal achieved with friction (repeats, detours), or a sensible warm handoff with context transferred.
- 4-6: Partially achieved — some sub-goals met, others abandoned or left unresolved.
- 2-3: Goal not achieved; the bot misunderstood or pursued the wrong task; the customer left without an outcome.
- 0-1: Call collapsed — wrong outcome stated as fact, customer gave up mid-task, or the bot ended the call incorrectly.

## Violation types
- goal_not_addressed: The customer's stated need was never pursued.
- wrong_outcome: The bot completed or reported something other than what the customer asked for.
- incorrect_information: The bot delivered information contradicted elsewhere in the call.
- premature_ending: The call ended before the goal was resolved or handed off.
