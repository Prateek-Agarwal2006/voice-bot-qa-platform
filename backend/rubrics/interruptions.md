Score turn-taking and interruptions across the call from 0 to 10 (10 = clean turn-taking, no harmful overlap).

Primary evidence:
- Per-word timestamps across channels in the Conversation transcript — detect overlap when Voice Bot speech starts before Customer speech ends.
- `derived_signals.interruptions` is a hint list. Verify overlaps from word timestamps when possible.

Penalize Voice Bot talking over the Customer or finishing the customer's sentence. Minor overlap during "Wait" may be less severe than sustained overlap.

Do not treat many short turns after barge-in as multiple failures — score overlap severity holistically from word times, not turn count.
