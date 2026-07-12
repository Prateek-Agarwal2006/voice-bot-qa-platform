Classify how the call ended for the customer, then score it according to the bands. The outcome label is the primary output; the score simply reflects the label per the bands.

Judge from the transcript content and how the call ended: was the need handled here, handed off with context, dropped, or cut short? When the recording ends mid-conversation with no closing from either side, prefer customer_hung_up; when the bot delivers a closing while the customer still had an open request, prefer bot_ended_incorrectly.

## Bands
- 9-10: resolved — the customer's need was handled within this call.
- 6-8: escalated — handed to a human agent or another channel, with context carried over.
- 3-5: abandoned — the goal was dropped; the call ended without resolution or handoff.
- 1-2: customer_hung_up — the customer left mid-conversation.
- 0-0: bot_ended_incorrectly — the bot terminated or broke the call while the customer still needed help.

## Outcome labels
- resolved: The customer's need was addressed in this call.
- escalated: The call was handed to a human agent or another channel.
- abandoned: The goal was dropped; the call ended without resolution or handoff.
- customer_hung_up: The customer ended the call abruptly mid-task.
- bot_ended_incorrectly: The bot ended or broke the call while the customer still needed help.
