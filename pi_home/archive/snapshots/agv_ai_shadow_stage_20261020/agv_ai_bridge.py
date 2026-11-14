"""Offline-testable adapters between learned policies and the AGV navigator.

The bridge does not open serial devices or command motors. In particular,
the local planner's filtered zero-velocity command must remain a STOP.
"""

import math


def measured_twist(telemetry):
    """Use measured ESP32 velocities rather than an always-zero placeholder."""
    if not isinstance(telemetry, dict):
        return 0.0, 0.0
    try:
        v, w = float(telemetry['v']), float(telemetry['w'])
    except (KeyError, TypeError, ValueError):
        return 0.0, 0.0
    return (v, w) if math.isfinite(v) and math.isfinite(w) else (0.0, 0.0)


def ai1_velocity(filtered_action, cruise_speed, turn_limit):
    """Respect the ONNX runtime's safety-filtered m/s and rad/s commands.

    Never impose a forward speed floor or slew a commanded emergency zero.
    The existing command writer remains the final motion/geometry arbiter.
    """
    try:
        if len(filtered_action) != 2:
            raise ValueError('AI1 action must contain v and w')
        v, w = (float(x) for x in filtered_action)
        cruise_speed, turn_limit = float(cruise_speed), float(turn_limit)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid AI1 action') from exc
    if not all(map(math.isfinite, (v, w, cruise_speed, turn_limit))):
        raise ValueError('Non-finite AI1 action or limits')
    if v < 0 or cruise_speed < 0 or turn_limit < 0:
        raise ValueError('Negative AI1 forward speed or limits')
    if v == 0.0 and w == 0.0:
        return 0.0, 0.0
    return min(v, cruise_speed, 0.35), max(-min(turn_limit, 1.5), min(min(turn_limit, 1.5), w))


def ai2_action_direction(action):
    """Grid training uses row 0 at the top; ROS map +Y is physically up."""
    return ((0.0, 1.0), (0.0, -1.0), (-1.0, 0.0), (1.0, 0.0))[action]


def ai2_ranked_candidates(candidates, q_values, rx, ry, map_yaw=0.0):
    """Give a finite, four-action AI2 policy a bounded directional vote."""
    try:
        values = [float(x) for x in q_values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid AI2 Q-values') from exc
    if len(values) != 4 or not all(map(math.isfinite, values)):
        raise ValueError('AI2 requires four finite Q-values')
    if not math.isfinite(map_yaw):
        raise ValueError('Invalid map yaw')
    action = max(range(4), key=lambda i: values[i])
    dx, dy = ai2_action_direction(action)
    c, s = math.cos(map_yaw), math.sin(map_yaw)
    dx, dy = c * dx - s * dy, s * dx + c * dy
    ranked = sorted(candidates, key=lambda c: c[0] - 0.5 * (
        (c[1][0] - rx) * dx + (c[1][1] - ry) * dy))
    return action, ranked


def ai2_observation(grid, start_cell, candidates, visited_cells, robot_xy,
                    world_yaw, no_progress_steps, free_cell_count):
    """Convert ROS coordinates to the 3x9x9 + 8-feature training convention.

    Returns None when no path-backed target is available. The 32x32 training
    grid uses a 64-step normalized geodesic distance and 100-step stall scale.
    This fixes coordinate/feature mismatch but does not prove sim-to-real.
    """
    import numpy as np

    cx, cy = start_cell
    rx, ry = robot_xy
    patch = np.zeros((3, 9, 9), dtype=np.float32)
    for row in range(9):
        for col in range(9):
            cell = (cx + col - 4, cy + 4 - row)  # north is top row
            if not grid.traversable(cell):
                patch[1, row, col] = 1.0
            elif cell in visited_cells:
                patch[2, row, col] = 1.0
            else:
                patch[0, row, col] = 1.0

    path = None
    for _, target in sorted(candidates, key=lambda item: item[0])[:5]:
        path = grid.path((rx, ry), target)
        if path is not None and len(path) > 1:
            break
    if not path or len(path) < 2:
        return None

    map_yaw = float(getattr(grid, 'origin', (0., 0., 0.))[2])
    step_x = path[1][0] - path[0][0]
    step_y = path[1][1] - path[0][1]
    c, s = math.cos(map_yaw), math.sin(map_yaw)
    step_x, step_y = c * step_x + s * step_y, -s * step_x + c * step_y
    # Project an 8-connected A* first step onto the 4-way training action space.
    if abs(step_x) >= abs(step_y):
        path_dx, path_dy = (1.0 if step_x >= 0 else -1.0), 0.0
    else:
        path_dx, path_dy = 0.0, (-1.0 if step_y > 0 else 1.0)
    grid_yaw = map_yaw - world_yaw
    features = np.array([
        path_dx, path_dy, min(1.0, (len(path) - 1) / 64.0), 1.0,
        math.sin(grid_yaw), math.cos(grid_yaw),
        min(1.0, len(visited_cells) / max(1, free_cell_count)),
        min(1.0, max(0, no_progress_steps) / 100.0),
    ], dtype=np.float32)
    return patch, features
