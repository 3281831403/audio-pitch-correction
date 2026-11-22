"""Pitch-correction primitives for the pitchfix exercise.

Data conventions
----------------
A pitch curve is a list of ``(time_ms, cents)`` pairs.  ``time_ms`` is a
non-negative millisecond timestamp and ``cents`` is a pitch measured in
cents.  A target scale is a list/tuple of semitone offsets from the
reference pitch (a 12-TET octave has 12 semitones, so one semitone is
``100.0`` cents).  ``SCALE_TABLE`` contains the common scale tables.

The exercise uses a tolerance of one cent: a value within
``TOLERANCE_CENTS`` of an allowed note is treated as already in tune.
All functions are pure: they never mutate their arguments.  Invalid
input is reported with :class:`PitchFixError` (or, for
:func:`validate`, with strings in the returned list).
"""

from __future__ import annotations

import math

CENTS_PER_SEMITONE = 100.0
TOLERANCE_CENTS = 1.0
MIN_CENTS = -1200.0
MAX_CENTS = 1200.0

# Semitone-offset tables.  A note's pitch in cents is 100 * offset.
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
SCALE_TABLE = {
    "major": MAJOR_SCALE,
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "chromatic": list(range(12)),
}


class PitchFixError(ValueError):
    """Raised when a pitch-correction operation cannot be performed."""


def _as_finite(value, what):
    """Return ``value`` as a finite float or raise :class:`PitchFixError`."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise PitchFixError(f"{what} must be a finite number") from None
    if not math.isfinite(number):
        raise PitchFixError(f"{what} must be a finite number")
    return number


def _clamp01(value):
    """Clamp ``value`` to ``[0.0, 1.0]`` (NaN degrades to 0.0)."""
    if value != value:  # NaN
        return 0.0
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return float(value)


def _offset_list(scale):
    """Materialise a scale and reject empty/non-finite offsets."""
    try:
        offsets = list(scale)
    except TypeError:
        raise PitchFixError("scale must be an iterable of semitone offsets") from None
    if not offsets:
        raise PitchFixError("scale is empty")
    result = []
    for offset in offsets:
        number = _as_finite(offset, "scale offset")
        result.append(number)
    return result


def _median(values):
    """Return the median of a non-empty sequence of numbers."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _nearest_offset(value, offsets):
    """Return ``(target_cents, deviation_cents)`` for a finite ``value``."""
    # Pick the nearest allowed note; on an exact midpoint prefer the lower
    # note, so the choice is deterministic.  Distances are compared directly
    # rather than floored, which is what used to make everything a semitone
    # flat.
    best_offset = min(offsets)
    best_distance = abs(value - CENTS_PER_SEMITONE * best_offset)
    for offset in offsets:
        distance = abs(value - CENTS_PER_SEMITONE * offset)
        is_lower = offset < best_offset
        if distance < best_distance or (distance == best_distance and is_lower):
            best_offset = offset
            best_distance = distance

    target = CENTS_PER_SEMITONE * best_offset
    return target, value - target


def nearest_note(cents, scale):
    """Return ``(target_cents, deviation_cents)`` for ``cents``.

    ``scale`` is a non-empty iterable of semitone offsets into the scale
    table; an offset ``s`` denotes the pitch ``100.0 * s`` cents.  Pick
    the closest allowed note.  On an exact midpoint prefer the lower
    note, so the choice is deterministic.

    The returned deviation is signed: ``deviation_cents = cents -
    target_cents``.  Values within the one-cent tolerance still return
    the note they are nearest to (they simply have a tiny deviation).

    Raise ``PitchFixError`` when ``scale`` is empty or when ``cents`` is
    not finite.
    """
    value = _as_finite(cents, "cents")
    offsets = _offset_list(scale)
    return _nearest_offset(value, offsets)


def smooth_curve(curve, window):
    """Median-smooth ``curve`` while preserving both endpoints.

    ``curve`` is a sequence of ``(time_ms, cents)`` points.  ``window``
    is a positive odd integer; for each interior point the median of the
    point and its ``window // 2`` neighbours on each side is used.  A
    median (rather than a mean) is required so that short vibrato
    oscillations survive smoothing.  Points near an end use the
    available neighbours, and the first/last points are returned
    unchanged.  Return a new list with the same length and timestamps as
    the input; never mutate the input.

    Raise ``PitchFixError`` when ``window`` is not a positive odd
    integer.
    """
    if isinstance(window, bool) or not isinstance(window, int):
        raise PitchFixError("window must be a positive odd integer")
    if window <= 0 or window % 2 == 0:
        raise PitchFixError("window must be a positive odd integer")

    points = list(curve)
    if len(points) <= 2:
        # With fewer than three points every point is an endpoint.
        return [(float(time_ms), float(cents)) for time_ms, cents in points]

    half = window // 2
    result = [(float(points[0][0]), float(points[0][1]))]
    for index in range(1, len(points) - 1):
        low = max(0, index - half)
        high = min(len(points), index + half + 1)
        # Median (not mean): a short vibrato oscillation is not flattened.
        median = _median([points[j][1] for j in range(low, high)])
        result.append((float(points[index][0]), float(median)))
    result.append((float(points[-1][0]), float(points[-1][1])))
    return result


def correction_amount(curve, target, strength):
    """Return one blend coefficient in ``[0.0, 1.0]`` per curve point.

    ``target`` is the target scale (a sequence of semitone offsets).
    A coefficient of 0 means "leave this point alone"; 1 means "move it
    fully onto the nearest allowed note".  A point within the one-cent
    tolerance of an allowed note gets 0.0.  Every other point gets
    ``strength`` clamped to ``[0.0, 1.0]``, so ``strength=0`` never
    changes pitch and ``strength=1`` corrects fully.  Return a list of
    floats with the same length as ``curve`` (an empty curve yields
    ``[]``).

    Raise ``PitchFixError`` when the scale is empty or ``strength`` is
    not finite.
    """
    offsets = _offset_list(target)
    blend = _clamp01(_as_finite(strength, "strength"))

    amounts = []
    for _time_ms, cents in curve:
        value = _as_finite(cents, "cents")
        note, _deviation = _nearest_offset(value, offsets)
        if abs(value - note) <= TOLERANCE_CENTS:
            amounts.append(0.0)
        else:
            # Respect the requested strength instead of always correcting fully.
            amounts.append(blend)
    return amounts


def apply_correction(segments, amounts):
    """Apply per-segment blend amounts and keep the timeline intact.

    ``segments`` is a sequence of ``(start_ms, end_ms, cents,
    target_cents)`` tuples; ``amounts`` is a parallel sequence of
    coefficients.  For each segment the corrected pitch is::

        cents + clamp(amount, 0.0, 1.0) * (target_cents - cents)

    Return a new list of ``(start_ms, end_ms, corrected_cents)`` tuples,
    in the original order and with exactly the same list length and
    timestamps as the input.  The source segments are not mutated.

    Raise ``PitchFixError`` when the two sequences have different
    lengths.
    """
    segment_list = list(segments)
    amount_list = list(amounts)
    if len(segment_list) != len(amount_list):
        raise PitchFixError("segments and amounts must have the same length")

    corrected = []
    for (start_ms, end_ms, cents, target_cents), amount in zip(
        segment_list, amount_list
    ):
        value = _as_finite(cents, "cents")
        target_value = _as_finite(target_cents, "target_cents")
        # Blend only the pitch; timestamps are copied through untouched so the
        # timeline cannot drift.
        pitch = value + _clamp01(float(amount)) * (target_value - value)
        corrected.append((start_ms, end_ms, pitch))
    return corrected


def rescale_to_scale(curve, scale, snap_ratio):
    """Snap every point part-way to its nearest scale note.

    ``snap_ratio`` is a blend ratio in ``[0.0, 1.0]``: 0 leaves each
    pitch unchanged, 1 moves it fully to the nearest note, and 0.5 moves
    it half-way.  Return a new ``[(time_ms, cents)]`` list with the same
    length, order, and timestamps.  An empty curve returns ``[]``.

    Raise ``PitchFixError`` for an empty scale or a ``snap_ratio``
    outside ``[0.0, 1.0]``.
    """
    offsets = _offset_list(scale)
    ratio = _as_finite(snap_ratio, "snap_ratio")
    if not 0.0 <= ratio <= 1.0:
        raise PitchFixError("snap_ratio must be within [0.0, 1.0]")

    result = []
    for time_ms, cents in curve:
        value = _as_finite(cents, "cents")
        note, _deviation = _nearest_offset(value, offsets)
        result.append((float(time_ms), value + ratio * (note - value)))
    return result


def detect_vibrato(curve, min_rate):
    """Mark points that belong to a vibrato region.

    Return a list of booleans with one entry per ``(time_ms, cents)``
    point (an empty curve yields ``[]``).  A region is vibrato when the
    pitch oscillates up and down with a direction-reversal rate of at
    least ``min_rate`` hertz.  Marking a point True means pitch
    correction must leave it untouched, so real vibrato is not flattened
    as if it were bad intonation.  Endpoints may be False when there is
    not enough context.  The curve is not modified.

    Raise ``PitchFixError`` when ``min_rate`` is not a positive finite
    number.
    """
    rate = _as_finite(min_rate, "min_rate")
    if rate <= 0.0:
        raise PitchFixError("min_rate must be a positive finite number")

    points = list(curve)
    flags = [False] * len(points)
    if len(points) < 3:
        return flags

    # Direction of each non-flat step between consecutive samples.
    signs = []
    for index in range(len(points) - 1):
        delta = points[index + 1][1] - points[index][1]
        if delta > 0:
            signs.append((index, 1))
        elif delta < 0:
            signs.append((index, -1))

    # A direction reversal is a turn point; count how often the pitch turns
    # around per second.  Enough reversals means this is vibrato, not a
    # slowly drifting (and genuinely out-of-tune) note.
    turns = [
        signs[i][0]
        for i in range(1, len(signs))
        if signs[i][1] != signs[i - 1][1]
    ]
    if not turns:
        return flags

    span_seconds = (points[-1][0] - points[0][0]) / 1000.0
    if span_seconds <= 0.0:
        return flags
    if len(turns) / span_seconds < rate:
        return flags

    # Mark the oscillating region (interior turn points); endpoints stay
    # unmarked because there is not enough context there.
    first, last = turns[0], turns[-1]
    for index in range(first, last + 1):
        flags[index] = True
    return flags


def validate(curve, scale):
    """Return a list of human-readable problems; never raise for data.

    The checks cover the three failure modes of the exercise:

    * timestamps are not in non-decreasing order ("unsorted");
    * the target scale is empty ("empty");
    * a cents value is non-finite or outside
      ``[MIN_CENTS, MAX_CENTS]`` ("out of range").

    An empty curve is valid and produces no issues by itself, provided
    the scale is valid.  Return ``[]`` when everything is valid.  The
    strings are diagnostics for the caller; callers must not assume a
    particular language or a fixed number of messages.
    """
    issues = []

    try:
        offsets = list(scale)
    except TypeError:
        issues.append("target scale is not a sequence")
        offsets = []
    if not offsets:
        issues.append("target scale is empty")
    else:
        for offset in offsets:
            try:
                finite = math.isfinite(float(offset))
            except (TypeError, ValueError):
                finite = False
            if not finite:
                issues.append("target scale contains a non-finite offset")
                break

    previous = None
    unsorted_reported = False
    for point in curve:
        time_ms, cents = point
        if previous is not None and not unsorted_reported:
            try:
                backwards = time_ms < previous
            except TypeError:
                backwards = True
            if backwards:
                issues.append("curve timestamps are not sorted in ascending order")
                unsorted_reported = True
        previous = time_ms

        try:
            finite = math.isfinite(float(cents))
        except (TypeError, ValueError):
            finite = False
        if not finite or not (MIN_CENTS <= float(cents) <= MAX_CENTS):
            issues.append(
                f"cents value {cents!r} is out of range "
                f"[{MIN_CENTS}, {MAX_CENTS}]"
            )

    return issues


def correct_batch(tracks, config):
    """Correct several tracks atomically and return a new result dict.

    ``tracks`` is a sequence of mappings with at least ``"id"`` and
    ``"curve"`` (a ``[(time_ms, cents)]`` list).  ``config`` is a mapping
    with ``"scale"`` (semitone offsets), ``"window"`` (odd positive
    int), ``"strength"`` (0..1 blend), and ``"min_rate"`` (vibrato
    threshold in hertz).

    All tracks must be validated before any result is returned.  If any
    track is invalid, raise ``PitchFixError`` and produce no partial
    result: the inputs stay untouched, which is the batch rollback
    guarantee.  Valid tracks are processed on independent copies (never
    through a shared curve), with smoothing, vibrato detection, and
    strength-aware correction.  ``strength=0`` returns each curve
    unchanged.  On success return::

        {"tracks": [{"id": <id>, "curve": [...]}, ...],
         "count": <number of tracks>}

    preserving the input order and the original track ids.
    """
    track_list = list(tracks)

    try:
        scale_offsets = _offset_list(config["scale"])
        window = config["window"]
        strength = _as_finite(config["strength"], "strength")
        min_rate = _as_finite(config["min_rate"], "min_rate")
    except KeyError as exc:
        raise PitchFixError(f"config is missing {exc.args[0]!r}") from None

    if min_rate <= 0.0:
        raise PitchFixError("min_rate must be a positive finite number")
    if (
        isinstance(window, bool)
        or not isinstance(window, int)
        or window <= 0
        or window % 2 == 0
    ):
        raise PitchFixError("window must be a positive odd integer")
    snap = _clamp01(strength)

    # Validate every track up front.  Raising here, before any output is
    # built, is what makes the batch atomic: the caller's data is untouched
    # and no partial result escapes.
    for track in track_list:
        if "id" not in track or "curve" not in track:
            raise PitchFixError("each track needs an 'id' and a 'curve'")
        issues = validate(track["curve"], scale_offsets)
        if issues:
            raise PitchFixError(
                f"track {track['id']!r} is invalid: " + "; ".join(issues)
            )

    corrected_tracks = []
    for track in track_list:
        # A private copy per track: tracks must never share a curve object.
        source = [(float(time_ms), float(cents)) for time_ms, cents in track["curve"]]

        if snap == 0.0:
            # strength 0 means "leave the pitch alone", smoothing included.
            corrected_tracks.append({"id": track["id"], "curve": source})
            continue

        smoothed = smooth_curve(source, window)
        vibrato = detect_vibrato(smoothed, min_rate)
        raw_amounts = correction_amount(smoothed, scale_offsets, snap)
        # Points inside a detected vibrato region are left untouched so real
        # expression is not flattened as if it were bad intonation.
        amounts = [
            0.0 if is_vibrato else amount
            for amount, is_vibrato in zip(raw_amounts, vibrato)
        ]
        targets = [nearest_note(cents, scale_offsets)[0] for _, cents in smoothed]
        segments = [
            (time_ms, time_ms, cents, target)
            for (time_ms, cents), target in zip(smoothed, targets)
        ]
        corrected = apply_correction(segments, amounts)
        corrected_tracks.append(
            {
                "id": track["id"],
                "curve": [(row[0], row[2]) for row in corrected],
            }
        )

    return {"tracks": corrected_tracks, "count": len(corrected_tracks)}
