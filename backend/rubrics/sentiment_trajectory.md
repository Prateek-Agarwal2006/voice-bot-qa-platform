Score sentiment trajectory from 0 to 10 (10 = the customer ended the call in a clearly better or consistently positive state).

Compare the customer's apparent state **at the start** of the call with their state **at the end**, using what they say and how they say it. Direction matters more than absolute level: a call that starts angry and ends satisfied is a success; a call that starts neutral and ends irritated is a failure — even if the average sentiment is similar.

This dimension scores the **change**; the overall level of frustration is scored separately by User Disappointment.

## Bands
- 9-10: Clear improvement (frustrated → satisfied) or consistently positive throughout.
- 7-8: Steady neutral-or-better; no deterioration.
- 4-6: Mild decline, or frustration that surfaced and was only partially recovered by the end.
- 2-3: Clear deterioration — the customer ends notably more frustrated than they began.
- 0-1: The call ends in open anger, resignation, or abandonment after starting workably.

## Violation types
- sentiment_decline_event: An identifiable moment where the customer's state visibly worsened.
- unrecovered_frustration: Frustration surfaced and the bot never brought the customer back.
- negative_ending: The customer's final turns are clearly worse than their opening turns.
