CUSTOMER_CHANNEL = 0
VOICE_BOT_CHANNEL = 1

CHANNEL_LABEL = {
    CUSTOMER_CHANNEL: "Customer",
    VOICE_BOT_CHANNEL: "Voice Bot",
}

SCRIBE_MODEL_ID = "scribe_v2"

HESITATION_MIN_GAP_SEC = 0.5
DEAD_AIR_MIN_GAP_SEC = 1.0

# Scribe language_probability below this marks the evaluation as low-confidence (E2).
TRANSCRIPT_CONFIDENCE_MIN = 0.7

# Barge-in recovery (E3): bot words closer than the merge gap form one continuous
# bot speech segment; a customer word this long after their previous word is a new onset.
BOT_SEGMENT_MERGE_GAP_SEC = 0.5
CUSTOMER_ONSET_MIN_GAP_SEC = 1.0
# After a customer barge-in, the bot yielding within this window is acceptable.
BARGE_IN_YIELD_OK_SEC = 1.0
# Word-level overlaps closer than this merge into one interruption episode.
INTERRUPTION_EPISODE_MERGE_GAP_SEC = 1.0

# Deterministic timing scores (E3). Bands are (upper_bound_seconds, judge_score);
# first band whose bound >= value wins, else the floor score applies.
LATENCY_P50_BANDS = ((2.0, 10), (3.0, 8), (4.0, 6), (6.0, 4))
LATENCY_FLOOR_SCORE = 2
LATENCY_OUTLIER_SEC = 6.0
LATENCY_OUTLIER_PENALTY = 2

DEAD_AIR_TOTAL_BANDS = ((0.0, 10), (3.0, 9), (6.0, 7), (12.0, 5), (20.0, 3))
DEAD_AIR_FLOOR_SCORE = 1
DEAD_AIR_LONG_GAP_SEC = 5.0
DEAD_AIR_LONG_GAP_PENALTY = 1

OVERLAP_TOTAL_BANDS = ((0.0, 10), (0.5, 9), (1.5, 7), (3.0, 5), (6.0, 3))
OVERLAP_FLOOR_SCORE = 1
FAILED_YIELD_PENALTY = 1
FAILED_YIELD_PENALTY_MAX = 2
