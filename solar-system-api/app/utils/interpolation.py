"""
Interpolation utilities for smooth video transitions between snapshots.
"""


def lerp(start: float, end: float, t: float) -> float:
    """Linear interpolation. t ranges from 0.0 to 1.0."""
    return start + (end - start) * t


def ease_in_out(t: float) -> float:
    """Smooth easing function (Hermite interpolation) for more natural motion."""
    return t * t * (3 - 2 * t)


def interpolate_snapshots(snapshot_a: dict, snapshot_b: dict, t: float) -> dict:
    """
    Creates an intermediate state between two snapshots at time t (0.0 to 1.0).

    - People present in both: lerp their positions
    - People only in A (removed): fade them out (reduce alpha as t increases)
    - People only in B (added): fade them in (increase alpha as t increases)
    """
    eased_t = ease_in_out(t)

    people_a = {p["id"]: p for p in snapshot_a.get("people", [])}
    people_b = {p["id"]: p for p in snapshot_b.get("people", [])}

    all_ids = set(people_a.keys()) | set(people_b.keys())

    interpolated_people = []
    for pid in all_ids:
        if pid in people_a and pid in people_b:
            # Present in both — lerp position
            pa, pb = people_a[pid], people_b[pid]
            interpolated_people.append(
                {
                    **pb,
                    "x_position": lerp(pa["x_position"], pb["x_position"], eased_t),
                    "y_position": lerp(pa["y_position"], pb["y_position"], eased_t),
                    "alpha": 1.0,
                }
            )
        elif pid in people_a:
            # Removed — fade out
            interpolated_people.append({**people_a[pid], "alpha": 1.0 - eased_t})
        else:
            # Added — fade in
            interpolated_people.append({**people_b[pid], "alpha": eased_t})

    return {
        **snapshot_b,
        "people": interpolated_people,
    }
