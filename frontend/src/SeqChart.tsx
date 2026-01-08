interface Pt {
  n: number;
  effect: number;
  ci_lower: number;
  ci_upper: number;
  significant: boolean;
}

/** Inline SVG confidence-sequence chart: effect line + shaded CI band; the
 * zero line is highlighted so you can see when/if the band excludes 0. */
export function SeqChart({ points }: { points: Pt[] }) {
  const W = 720;
  const H = 260;
  const pad = { l: 48, r: 16, t: 16, b: 28 };
  if (points.length === 0)
    return <div className="chart">no data yet</div>;

  const finite = points.filter(
    (p) => isFinite(p.ci_lower) && isFinite(p.ci_upper),
  );
  const pts = finite.length ? finite : points;
  const xs = pts.map((p) => p.n);
  const lo = Math.min(0, ...pts.map((p) => p.ci_lower));
  const hi = Math.max(0, ...pts.map((p) => p.ci_upper));
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);

  const sx = (n: number) =>
    pad.l + ((n - xMin) / (xMax - xMin || 1)) * (W - pad.l - pad.r);
  const sy = (v: number) =>
    pad.t + (1 - (v - lo) / (hi - lo || 1)) * (H - pad.t - pad.b);

  const band =
    pts.map((p) => `${sx(p.n)},${sy(p.ci_upper)}`).join(" ") +
    " " +
    pts
      .slice()
      .reverse()
      .map((p) => `${sx(p.n)},${sy(p.ci_lower)}`)
      .join(" ");
  const line = pts.map((p) => `${sx(p.n)},${sy(p.effect)}`).join(" ");

  const firstSig = pts.find((p) => p.significant);

  return (
    <div className="chart">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`}>
        {/* CI band */}
        <polygon points={band} fill="#3d4b6e" fillOpacity="0.35" />
        {/* zero line */}
        <line
          x1={pad.l}
          x2={W - pad.r}
          y1={sy(0)}
          y2={sy(0)}
          stroke="#f78ea2"
          strokeDasharray="4 4"
          strokeWidth="1"
        />
        <text x={pad.l + 2} y={sy(0) - 4} fill="#f78ea2" fontSize="11">
          effect = 0
        </text>
        {/* effect line */}
        <polyline points={line} fill="none" stroke="#7aa2f7" strokeWidth="2" />
        {/* first-significant marker */}
        {firstSig && (
          <>
            <line
              x1={sx(firstSig.n)}
              x2={sx(firstSig.n)}
              y1={pad.t}
              y2={H - pad.b}
              stroke="#7ee787"
              strokeWidth="1"
            />
            <text
              x={sx(firstSig.n) + 4}
              y={pad.t + 12}
              fill="#7ee787"
              fontSize="11"
            >
              significant @ n={firstSig.n}
            </text>
          </>
        )}
        {/* axes labels */}
        <text x={pad.l} y={H - 8} fill="#8b93a7" fontSize="11">
          n={xMin}
        </text>
        <text x={W - pad.r - 40} y={H - 8} fill="#8b93a7" fontSize="11">
          n={xMax}
        </text>
        <text x={4} y={sy(hi) + 10} fill="#8b93a7" fontSize="11">
          {hi.toFixed(2)}
        </text>
        <text x={4} y={sy(lo)} fill="#8b93a7" fontSize="11">
          {lo.toFixed(2)}
        </text>
      </svg>
    </div>
  );
}
