"""Wheel RPM policy shared by navigation and the final UART writer."""
import math

NORMAL_RPM = 65.0
SLOW_RPM = 40.0
WHEEL_RADIUS_M = .0366
HALF_TRACK_M = .096
MPS_PER_RPM = 2 * math.pi * WHEEL_RADIUS_M / 60


def rpm_to_speed(rpm):
    return rpm * MPS_PER_RPM


def rpm_to_turn(rpm):
    return rpm_to_speed(rpm) / HALF_TRACK_M


def twist_to_wheels(v, w):
    return ((v - w * HALF_TRACK_M) / MPS_PER_RPM,
            (v + w * HALF_TRACK_M) / MPS_PER_RPM)


def wheels_to_twist(left, right):
    return ((left + right) * MPS_PER_RPM / 2,
            (right - left) * MPS_PER_RPM / (2 * HALF_TRACK_M))


def running_wheels(left, right, normal_rpm=NORMAL_RPM, slow=False):
    """Keep direction and differential steering, with no weak nonzero target.

    Zero remains zero. Straight cruise reaches 65; crawl/recovery reaches 40.
    Turning can use unequal wheel targets within [40, 65]. The resulting
    twist must be checked against geometry *after* this conversion.
    """
    if not all(math.isfinite(x) for x in (left, right, normal_rpm)):
        raise ValueError('Nonfinite wheel target')
    if normal_rpm not in (SLOW_RPM, NORMAL_RPM):
        raise ValueError('Choose 40 or 65 RPM')
    peak=max(abs(left),abs(right))
    if peak < 1e-8:
        return 0.,0.
    ceiling=SLOW_RPM if slow or peak <= SLOW_RPM + 1e-6 else normal_rpm
    # Flooring two unequal, opposite wheel speeds to +/-40 used to erase
    # translation entirely. A requested forward/reverse arc must remain an
    # arc: pivot about the inner wheel rather than turning both wheels in
    # opposite directions. The same pivot preserves steering at crawl speed.
    translating=abs(left+right)>1e-8
    if translating and (left*right<0 or
                        (ceiling==SLOW_RPM and abs(left-right)>peak*.15)):
        if abs(left)>abs(right):
            return math.copysign(ceiling,left),0.
        return 0.,math.copysign(ceiling,right)
    def wheel(value):
        if abs(value) < 1e-8:return 0.
        return round(math.copysign(max(SLOW_RPM,min(ceiling,abs(value)*ceiling/peak)),value),3)
    return wheel(left),wheel(right)
