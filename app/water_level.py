import math

# Constants from the definition
R1 = 0.4  # m
R2 = 5.9  # m
R3 = 8.6  # m
R4 = 14.1  # m

V_MIN = 350.0  # m³  (volume at R1 and below)
V_R2 = 75975.0  # m³  (volume at R2)
V_R3 = 150225.0  # m³  (volume at R3)
V_MAX = 225850.0  # m³  (volume at R4)


def volume_from_level(level: float) -> float:
    """
    Compute tunnel water volume [m³] from water level LC001 [m].

    Piecewise definition based on:
      Case 1: LC001 < R1
      Case 2: R1 <= LC001 < R2
      Case 3: R2 <= LC001 < R3
      Case 4: R3 <= LC001 <= R4

    Raises:
        ValueError: if level > R4 (outside model domain).
    """
    if level < R1:
        # Case 1
        return V_MIN

    # Case 2
    if level < R2:
        Vbx = level - R1
        return ((1000.0 * Vbx * Vbx) / 2.0) * 5.0 + 350.0
        # which simplifies to: 2500 * Vbx**2 + 350

    # Case 3
    if level < R3:
        Vcx = level - R2
        return (5500.0 * Vcx * 5.0) + 75975.0
        # which simplifies to: 27500 * Vcx + 75975

    # Case 4
    if level <= R4:
        Vdx = level - R3
        return (
            ((5.5 * 5500.0 / 2.0) - ((5.5 - Vdx) * (5.5 - Vdx) * 1000.0 / 2.0)) * 5.0
        ) + 150225.0
        # which simplifies to: 225850 - 2500 * (5.5 - Vdx)**2

    # Above model range
    raise ValueError(f"Level {level} m is above the maximum modeled range ({R4} m).")


def level_from_volume(volume: float) -> float:
    """
    Compute water level LC001 [m] from tunnel water volume [m³].

    Inverse of volume_from_level, valid for:
        350 m³ <= volume <= 225850 m³

    Note: For volume == 350 m³ the model corresponds to any level < R1,
    so this function returns R1 as a conventional representative value.

    Raises:
        ValueError: if volume is outside [350, 225850] m³.
    """
    if volume < V_MIN or volume > V_MAX:
        raise ValueError(
            f"Volume {volume} m³ is outside the modeled range "
            f"[{V_MIN}, {V_MAX}] m³."
        )

    # Case 1 (flat segment): treat as level = R1
    if math.isclose(volume, V_MIN):
        return R1

    # Case 2: R1 < LC001 <= R2
    if volume <= V_R2:
        # V = 2500 * Vbx^2 + 350,  where Vbx = LC001 - R1
        Vbx_sq = (volume - 350.0) / 2500.0
        if Vbx_sq < 0:
            raise RuntimeError("Numerical issue: negative Vbx² in Case 2.")
        Vbx = math.sqrt(Vbx_sq)
        return R1 + Vbx

    # Case 3: R2 < LC001 <= R3
    if volume <= V_R3:
        # V = 27500 * Vcx + 75975, where Vcx = LC001 - R2
        Vcx = (volume - 75975.0) / 27500.0
        return R2 + Vcx

    # Case 4: R3 < LC001 <= R4
    # V = 225850 - 2500 * (5.5 - Vdx)²,  where Vdx = LC001 - R3
    # => (225850 - V)/2500 = (5.5 - Vdx)²
    term = (225850.0 - volume) / 2500.0
    if term < 0:
        raise RuntimeError("Numerical issue: negative term in Case 4.")
    sqrt_term = math.sqrt(term)
    Vdx = 5.5 - sqrt_term
    return R3 + Vdx


# (Optional) quick sanity checks
if __name__ == "__main__":
    for lvl in [R1, R2, R3, R4]:
        v = volume_from_level(lvl)
        lvl_back = level_from_volume(v)
        print(f"Level {lvl} m -> Volume {v} m³ -> Level {lvl_back} m")
