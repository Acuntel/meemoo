"""Trajectory + bump figures for docs/assets (matplotlib, headless Agg).

Palette: the validated categorical slots from the dataviz reference palette,
assigned in fixed order to the docking phases / series. Light surface.
"""

from __future__ import annotations

from pathlib import Path

from sim3d.spec import Episode3DResult, Rig3DConfig

# fixed-order categorical slots (validated palette, light mode)
_PHASE_COLORS = {
    "TRANSIT": "#2a78d6",  # slot 1 blue
    "ALIGN": "#eb6834",  # slot 2 orange
    "FINAL_APPROACH": "#1baf7a",  # slot 3 aqua
    "CAPTURE_PENDING": "#eda100",  # slot 4 yellow
    "ABORT": "#e87ba4",  # slot 5 magenta
}
_INK = "#333333"
_MUTED = "#999999"
_GRID = "#e8e8e8"

Trace = list[tuple[float, float, float, float, str]]


def _style(ax: object) -> None:
    import matplotlib.axes

    assert isinstance(ax, matplotlib.axes.Axes)
    ax.grid(color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_MUTED)
    ax.tick_params(colors=_INK, labelsize=9)


def _draw_dock(ax: object, rig: Rig3DConfig, plane: str) -> None:
    """Cone cross-section outline (top view: y, side view: z)."""
    import matplotlib.axes

    assert isinstance(ax, matplotlib.axes.Axes)
    c = rig.dock_z if plane == "z" else 0.0
    cup_x = -(rig.cone_depth - rig.cup_depth)
    xs = [0.0, cup_x, -rig.cone_depth]
    rs = [rig.mouth_radius, rig.throat_radius, rig.cup_exit_radius]
    for sign in (1.0, -1.0):
        ax.plot(xs, [c + sign * r for r in rs], color=_MUTED, linewidth=2)
    ax.plot([0.0, 0.0], [c - rig.mouth_radius, c + rig.mouth_radius],
            color=_MUTED, linewidth=1, linestyle=":")


def _plot_traj(path: Path, trace: Trace, rig: Rig3DConfig, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax_top, ax_side) = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, plane, ylab in ((ax_top, "y", "y (m)"), (ax_side, "z", "z (m)")):
        _style(ax)
        _draw_dock(ax, rig, plane)
        seen: set[str] = set()
        for i in range(1, len(trace)):
            t0, x0, y0, z0, ph = trace[i - 1]
            _, x1, y1, z1, _ = trace[i]
            color = _PHASE_COLORS.get(ph, _MUTED)
            a0 = y0 if plane == "y" else z0
            a1 = y1 if plane == "y" else z1
            label = ph if ph in _PHASE_COLORS and ph not in seen else None
            seen.add(ph)
            ax.plot([x0, x1], [a0, a1], color=color, linewidth=2, label=label)
        sx, sy, sz = trace[0][1], trace[0][2], trace[0][3]
        ax.plot([sx], [sy if plane == "y" else sz], marker="o", markersize=8,
                color=_INK, linestyle="none", label="start")
        ax.set_xlabel("x (m) — dock mouth at 0", color=_INK)
        ax.set_ylabel(ylab, color=_INK)
    ax_top.legend(loc="best", fontsize=8, frameon=False, labelcolor=_INK)
    fig.suptitle(title, color=_INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_bump(path: Path, series: dict[str, list[tuple[float, float]]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"damper on": "#2a78d6", "damper off": "#eb6834"}
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    _style(ax)
    for name, pts in series.items():
        ts = [p[0] for p in pts]
        tilts = [p[1] for p in pts]
        ax.plot(ts, tilts, color=colors.get(name, _MUTED), linewidth=2, label=name)
    ax.axhline(2.0, color=_MUTED, linewidth=1, linestyle="--")
    ax.annotate("2 deg settle band", xy=(0.99, 2.2), xycoords=("axes fraction", "data"),
                ha="right", fontsize=8, color=_MUTED)
    ax.set_xlabel("time since shove (s)", color=_INK)
    ax.set_ylabel("total tilt (deg)", color=_INK)
    ax.legend(loc="best", fontsize=9, frameon=False, labelcolor=_INK)
    ax.set_title("1 N x 0.2 s shove during hover — pendulum recovery (50 Hz control)",
                 color=_INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# Controller v1 (reactive beam-hold), as published 2026-07-28 before the
# planner landed. Kept as constants so the comparison figure is honest about
# what it is comparing: these are measurements, not a baseline re-run under
# different conditions. Cells: first-attempt, within-one-retry, within-six.
_V1 = {
    "2D sim\n50 Hz": (0.160, 0.350, 0.635),
    "MuJoCo\n50 Hz": (0.070, 0.105, 0.280),
    "MuJoCo\n10 Hz": (0.075, 0.135, 0.315),
}


def _plot_before_after(path: Path, after: dict[str, tuple[float, float, float]]
                       ) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cells = [c for c in _V1 if c in after]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.0), sharey=True)
    titles = ("first attempt", "within one retry", "within six attempts")
    for i, (ax, title) in enumerate(zip(axes, titles, strict=True)):
        _style(ax)
        xs = range(len(cells))
        ax.bar([x - 0.19 for x in xs], [_V1[c][i] * 100 for c in cells],
               width=0.36, color=_MUTED, label="controller v1")
        ax.bar([x + 0.19 for x in xs], [after[c][i] * 100 for c in cells],
               width=0.36, color=_PHASE_COLORS["FINAL_APPROACH"],
               label="controller v2")
        for x, c in zip(xs, cells, strict=True):
            ax.annotate(f"{after[c][i] * 100:.0f}%", xy=(x + 0.19, after[c][i] * 100),
                        xytext=(0, 3), textcoords="offset points", ha="center",
                        fontsize=8, color=_INK)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(cells, fontsize=8, color=_INK)
        ax.set_title(title, color=_INK, fontsize=10)
        ax.set_ylim(0, 105)
    axes[0].set_ylabel("success (%)", color=_INK)
    # the Phase-6 gate is BOTH bars: >95% first attempt and >99% within one
    for ax, bar in ((axes[0], 95.0), (axes[1], 99.0)):
        ax.axhline(bar, color=_PHASE_COLORS["ABORT"], linewidth=1, linestyle="--")
        ax.annotate(f"Phase-6 gate ({bar:.0f}%)", xy=(0.02, bar + 1.5),
                    xycoords=("axes fraction", "data"), fontsize=8,
                    color=_PHASE_COLORS["ABORT"])
    axes[2].legend(loc="lower right", fontsize=8, frameon=False, labelcolor=_INK)
    fig.suptitle("Docking success, 200 randomized episodes per cell "
                 "(same episode contract, same physics)", color=_INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def write_before_after(out_dir: Path) -> Path:
    """Read both engines' result files and draw the v1-vs-v2 comparison."""
    import json

    after: dict[str, tuple[float, float, float]] = {}
    two = out_dir / "physics2d_results.json"
    three = out_dir / "physics3d_results.json"
    if two.exists():
        d = json.loads(two.read_text()).get("hz50", {}).get("rates")
        if d:
            after["2D sim\n50 Hz"] = (d["first_attempt"], d["within_one_retry"],
                                      d["within_max_attempts"])
    if three.exists():
        doc = json.loads(three.read_text())["docking"]
        for key, cell in (("hz50", "MuJoCo\n50 Hz"), ("hz10", "MuJoCo\n10 Hz")):
            d = doc.get(key, {}).get("rates")
            if d:
                after[cell] = (d["first_attempt"], d["within_one_retry"],
                               d["within_max_attempts"])
    path = out_dir / "docking_v1_vs_v2.png"
    _plot_before_after(path, after)
    return path


def write_plots(out_dir: Path, results: list[Episode3DResult],
                *, control_hz: float = 50.0) -> list[Path]:
    """Re-run one success + one failure with tracing, plus a bump pair."""
    from sim3d.experiment import run_bump, run_episode3d

    rig = Rig3DConfig()
    written: list[Path] = []
    ok_seed = next((r.seed for r in results if r.ok and r.retries == 0),
                   next((r.seed for r in results if r.ok), None))
    bad_seed = next((r.seed for r in results if not r.ok), None)
    for seed, name, label in (
        (ok_seed, "physics3d_traj_success.png", "successful dock"),
        (bad_seed, "physics3d_traj_fail.png", "failed episode"),
    ):
        if seed is None:
            continue
        trace: Trace = []
        r = run_episode3d(seed, control_hz=control_hz, trace=trace)
        p = out_dir / name
        _plot_traj(
            p, trace, rig,
            f"MuJoCo rig, {label} (seed {r.seed}, {control_hz:.0f} Hz control, "
            f"buoyancy {r.buoyancy_gf:+.1f} gf, retries {r.retries}, "
            f"end {r.end_phase})",
        )
        written.append(p)
    series: dict[str, list[tuple[float, float]]] = {}
    for damper, name in ((True, "damper on"), (False, "damper off")):
        tr: list[tuple[float, float]] = []
        run_bump(7, damper=damper, control_hz=control_hz, trace=tr)
        series[name] = tr
    p = out_dir / "physics3d_bump_settle.png"
    _plot_bump(p, series)
    written.append(p)
    return written


def main() -> None:
    """CLI: refresh the v1-vs-v2 comparison from both engines' result files."""
    path = write_before_after(Path("docs/assets"))
    print(f"wrote {path}")  # noqa: T201 - CLI progress is this tool's UI


if __name__ == "__main__":
    main()
