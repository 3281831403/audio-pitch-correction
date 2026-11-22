"""Contract tests for the pitchfix exercise.

There are exactly 15 tests: one for each of the ten defects, plus five
combined regressions.  A correct implementation must make all of them
pass without changing this file.
"""

import math

import pytest

from pitchfix import (
    MAJOR_SCALE,
    MAX_CENTS,
    SCALE_TABLE,
    PitchFixError,
    apply_correction,
    correct_batch,
    correction_amount,
    detect_vibrato,
    nearest_note,
    rescale_to_scale,
    smooth_curve,
    validate,
)

CONFIG = {
    "scale": list(MAJOR_SCALE),
    "window": 3,
    "strength": 0.5,
    "min_rate": 5.0,
}


def test_nearest_note_uses_nearest_not_floor():
    """Defect 1: flooring would snap 90 cents down to 0, not up to 100."""
    target, deviation = nearest_note(90.0, SCALE_TABLE["chromatic"])
    assert target == pytest.approx(100.0)
    assert deviation == pytest.approx(-10.0)


def test_smooth_curve_median_preserves_vibrato():
    """Defect 2: a mean filter flattens the alternating vibrato samples."""
    curve = [
        (0.0, 40.0),
        (100.0, -40.0),
        (200.0, 40.0),
        (300.0, -40.0),
        (400.0, 40.0),
    ]
    smoothed = smooth_curve(curve, 3)

    assert len(smoothed) == len(curve)
    assert smoothed[0] == pytest.approx((0.0, 40.0))
    assert smoothed[-1] == pytest.approx((400.0, 40.0))
    # The medians here are +40 and -40; a mean would flatten both to 13.33.
    assert smoothed[1][1] == pytest.approx(40.0)
    assert smoothed[2][1] == pytest.approx(-40.0)


def test_correction_amount_scales_with_strength():
    """Defect 3: every off-note point must use the requested strength."""
    curve = [(0.0, 20.0), (100.0, 0.0), (200.0, 700.0)]

    quarter = correction_amount(curve, MAJOR_SCALE, 0.25)
    full = correction_amount(curve, MAJOR_SCALE, 1.0)

    assert quarter == pytest.approx([0.25, 0.0, 0.0])
    assert full == pytest.approx([1.0, 0.0, 0.0])
    assert all(0.0 <= amount <= 1.0 for amount in quarter)


def test_apply_correction_preserves_length_and_timestamps():
    """Defect 4: correcting must not add/remove points or shift time."""
    segments = [
        (0.0, 100.0, 20.0, 0.0),
        (100.0, 220.0, 80.0, 100.0),
        (220.0, 400.0, 130.0, 100.0),
    ]
    amounts = [1.0, 0.25, 0.0]

    corrected = apply_correction(segments, amounts)

    assert len(corrected) == len(segments)
    assert [row[0] for row in corrected] == [0.0, 100.0, 220.0]
    assert [row[1] for row in corrected] == [100.0, 220.0, 400.0]
    assert corrected[0][2] == pytest.approx(0.0)
    assert corrected[1][2] == pytest.approx(85.0)
    assert corrected[2][2] == pytest.approx(130.0)


def test_empty_scale_is_reported_and_rejected():
    """Defect 5: an empty scale must be diagnosed and raise, not divide."""
    issues = validate([(0.0, 0.0)], [])
    assert any("empty" in issue.lower() for issue in issues)

    with pytest.raises(PitchFixError):
        nearest_note(0.0, [])


def test_detect_vibrato_flags_oscillating_region():
    """Defect 6: real vibrato must be detected before correction."""
    curve = [
        (0.0, 0.0),
        (20.0, 40.0),
        (40.0, -40.0),
        (60.0, 40.0),
        (80.0, -40.0),
        (100.0, 40.0),
        (120.0, 0.0),
    ]
    flags = detect_vibrato(curve, min_rate=5.0)

    assert len(flags) == len(curve)
    assert all(isinstance(flag, bool) for flag in flags)
    assert any(flags)


def test_validate_reports_unsorted_curve():
    """Defect 7: a backwards curve must be rejected before correction."""
    issues = validate([(100.0, 0.0), (50.0, 0.0)], MAJOR_SCALE)

    assert issues
    assert any("sort" in issue.lower() for issue in issues)


def test_validate_reports_out_of_range_cents():
    """Defect 8: absurd cents values must not cause an octave jump."""
    issues = validate([(0.0, MAX_CENTS + 1.0)], MAJOR_SCALE)

    assert issues
    assert any("range" in issue.lower() for issue in issues)


def test_correct_batch_isolates_tracks_and_rolls_back():
    """Defect 9: tracks need private curves, and a bad track aborts all."""
    tracks = [
        {"id": "a", "curve": [(0.0, 20.0), (100.0, 40.0)]},
        {"id": "b", "curve": [(0.0, 20.0), (100.0, 40.0)]},
    ]
    original = [(track["id"], list(track["curve"])) for track in tracks]

    result = correct_batch(tracks, CONFIG)

    assert result["count"] == 2
    assert [track["id"] for track in result["tracks"]] == ["a", "b"]
    assert result["tracks"][0]["curve"] is not result["tracks"][1]["curve"]
    assert result["tracks"][0]["curve"] is not tracks[0]["curve"]
    assert [(track["id"], track["curve"]) for track in tracks] == original

    bad_tracks = [
        {"id": "ok", "curve": [(0.0, 20.0), (100.0, 40.0)]},
        {"id": "bad", "curve": [(100.0, 0.0), (50.0, 0.0)]},
    ]
    bad_original = [(track["id"], list(track["curve"])) for track in bad_tracks]
    with pytest.raises(PitchFixError):
        correct_batch(bad_tracks, CONFIG)
    assert [(track["id"], track["curve"]) for track in bad_tracks] == bad_original


def test_smooth_curve_rejects_nonpositive_window():
    """Defect 10: a negative window must raise a domain error."""
    with pytest.raises(PitchFixError):
        smooth_curve([(0.0, 0.0), (10.0, 10.0)], -1)


def test_correction_amount_zero_on_scale():
    """Combined: in-tune notes get zero correction and rescale stays put."""
    in_tune = [(0.0, 0.0), (20.0, 200.0), (40.0, 400.0), (60.0, 700.0)]

    amounts = correction_amount(in_tune, MAJOR_SCALE, 1.0)

    assert amounts == pytest.approx([0.0, 0.0, 0.0, 0.0], abs=1e-9)
    snapped = rescale_to_scale([(0.0, 199.0)], MAJOR_SCALE, 1.0)
    assert len(snapped) == 1
    assert snapped[0][0] == pytest.approx(0.0)
    assert snapped[0][1] == pytest.approx(200.0)


def test_strength_zero_output_equals_input():
    """Combined: strength 0 leaves every pitch unchanged to 1e-9."""
    curve = [(0.0, 13.0), (100.0, 47.0), (200.0, -60.0)]
    targets = [nearest_note(cents, MAJOR_SCALE)[0] for _, cents in curve]
    amounts = correction_amount(curve, MAJOR_SCALE, 0.0)
    segments = [
        (time_ms, time_ms, cents, target)
        for (time_ms, cents), target in zip(curve, targets)
    ]

    corrected = apply_correction(segments, amounts)

    assert [row[2] for row in corrected] == pytest.approx(
        [cents for _, cents in curve], abs=1e-9
    )


def test_empty_curve_returns_empty():
    """Combined: every curve transform has a well-defined empty result."""
    assert smooth_curve([], 3) == []
    assert correction_amount([], MAJOR_SCALE, 1.0) == []
    assert rescale_to_scale([], MAJOR_SCALE, 0.5) == []
    assert detect_vibrato([], 5.0) == []


def test_window_zero_raises_pitchfix_error():
    """Combined: window=0 is invalid and must raise PitchFixError."""
    with pytest.raises(PitchFixError):
        smooth_curve([(0.0, 0.0), (10.0, 10.0)], 0)


def test_correct_batch_preserves_track_order():
    """Combined: a fully successful batch keeps the input track order."""
    tracks = [
        {"id": "lead", "curve": [(0.0, 20.0), (100.0, 55.0)]},
        {"id": "double", "curve": [(0.0, 720.0), (100.0, 760.0)]},
        {"id": "harmony", "curve": [(0.0, -30.0), (100.0, -5.0)]},
    ]

    result = correct_batch(tracks, CONFIG)

    assert result["count"] == len(tracks)
    assert [track["id"] for track in result["tracks"]] == [
        "lead",
        "double",
        "harmony",
    ]
    assert len(result["tracks"]) == len(tracks)
