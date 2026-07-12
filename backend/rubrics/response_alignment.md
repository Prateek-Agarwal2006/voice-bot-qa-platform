Score response alignment from 0 to 10 (10 = the voice bot consistently addressed what the customer asked for).

Evaluate **across the full call**. When the customer asks for X, the bot should pursue X (and appropriate related steps), not unrelated topics or a substitute Y. Penalise evasive, off-topic, or misleading replies relative to the customer's requests.

Do not score each bot fragment in isolation — barge-ins and split turns are common in voice. Judge whether the bot's overall responses stayed aligned with the customer's intent through the call.

Transcript content is primary; the timing summary is optional context only.

## Bands
- 9-10: Every customer request was addressed directly; no substitutions or evasions.
- 7-8: Requests addressed with minor detours or one slightly off-target reply that was corrected.
- 4-6: Mixed — some requests answered, others met with substitutes, boilerplate, or partial answers.
- 2-3: The bot repeatedly answered something other than what was asked, or dodged the core request.
- 0-1: Responses were systematically unrelated or misleading relative to the customer's requests.

## Violation types
- off_topic_reply: The bot responded about something unrelated to the request.
- substituted_answer: The bot answered a different question (Y) than the one asked (X).
- ignored_request: A clear customer request received no response at any point.
- evasive_reply: The bot deflected with boilerplate instead of engaging with the request.
