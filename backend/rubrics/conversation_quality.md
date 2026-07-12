Score conversation quality from 0 to 10 (10 = natural, efficient voice interaction).

Evaluate the **whole call**, not isolated turn pairs. Consider flow, pacing, clarity for spoken dialogue, and whether the interaction felt coherent end-to-end.

For spoken dialogue, shorter is better: do **not** reward longer or more elaborate bot responses. Long monologues, over-enumerated lists, and contextually disproportionate detail increase listener load on a phone call and should be penalised. Short bot greetings and normal voice back-and-forth are fine.

Use the computed timing summary for pacing context. Repetition and re-asking are scored by Conversation Progression — penalise them here only when they break the flow of the call.

## Bands
- 9-10: Natural, efficient spoken interaction — clear, well-paced, easy to follow end-to-end.
- 7-8: Generally smooth with minor rough edges (an awkward phrasing, one slightly long reply).
- 4-6: Noticeably strained — verbose or confusing stretches, uneven pacing, but the call stays followable.
- 2-3: Hard to follow — rambling monologues, incoherent jumps, or pacing that would clearly frustrate a caller.
- 0-1: The interaction breaks down — the exchange is chaotic or effectively unusable as a spoken conversation.

## Violation types
- verbose_response: A bot reply is materially longer or denser than the moment requires.
- over_enumeration: The bot reads out a long list or menu unsuited to audio.
- confusing_flow: A jump, non sequitur, or structure that would confuse a listener.
- unnatural_phrasing: Wording clearly unsuited to spoken dialogue (markdown-like, robotic, or written-style text).
