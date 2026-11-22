"""pitchfix: small, dependency-free pitch-correction helpers."""

from .correction import (
    CENTS_PER_SEMITONE,
    MAJOR_SCALE,
    MAX_CENTS,
    MIN_CENTS,
    PitchFixError,
    SCALE_TABLE,
    TOLERANCE_CENTS,
    apply_correction,
    correct_batch,
    correction_amount,
    detect_vibrato,
    nearest_note,
    rescale_to_scale,
    smooth_curve,
    validate,
)

__all__ = [
    "CENTS_PER_SEMITONE",
    "MAJOR_SCALE",
    "MAX_CENTS",
    "MIN_CENTS",
    "PitchFixError",
    "SCALE_TABLE",
    "TOLERANCE_CENTS",
    "apply_correction",
    "correct_batch",
    "correction_amount",
    "detect_vibrato",
    "nearest_note",
    "rescale_to_scale",
    "smooth_curve",
    "validate",
]
