Score faithfulness from 0 to 10 (10 = everything the bot stated was consistent and grounded in the call).

Judge only what is checkable **within the transcript** — there are no tool logs or knowledge bases here. Look for: the bot contradicting something it said earlier, the bot misstating information the customer provided, and the bot asserting specific facts (prices, dates, policies, availability) with unwarranted certainty and no grounding in the conversation.

Do not penalise plausible domain statements merely because they cannot be verified from the call — penalise **internal inconsistency** and **specifics presented as confirmed fact** that nothing in the call supports.

## Bands
- 9-10: No contradictions; customer-provided details are used accurately; claims stay appropriately hedged.
- 7-8: One minor slip (a small detail misremembered) that was corrected or had no consequence.
- 4-6: A noticeable inconsistency or an unsupported specific stated as fact, affecting the customer's understanding.
- 2-3: Multiple contradictions or fabricated-sounding specifics that materially misled the customer.
- 0-1: The bot's statements are unreliable throughout — contradictory or invented content dominates the call.

## Violation types
- self_contradiction: The bot states something incompatible with what it said earlier in the call.
- misstated_customer_info: The bot repeats back or uses customer-provided information incorrectly.
- unsupported_specific: A concrete fact (price, date, policy) asserted as confirmed with no grounding in the call.
- false_confirmation: The bot confirms an action or state the call gives no evidence for.
