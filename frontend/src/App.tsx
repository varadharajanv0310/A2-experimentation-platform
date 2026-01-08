import { useEffect, useState } from "react";
import { SeqChart } from "./SeqChart";

interface Experiment {
  key: string;
  hypothesis: string;
  variants: string[];
  primary_metric: string;
  status: string;
  guardrails: { metric: string }[];
}

interface Results {
  pooled: {
    effect: number;
    ci_lower: number;
    ci_upper: number;
    significant: boolean;
    p_value: number;
    n_control: number;
    n_treatment: number;
    cuped_variance_reduction?: number;
  };
  segments: Record<string, { effect: number; ci_lower: number; ci_upper: number; significant: boolean }>;
  srm: { p_value: number; flagged: boolean; observed: number[] };
  guardrails: { metric: string; effect: number; flagged: boolean; direction: string }[];
}

const fmt = (x: number) => (isFinite(x) ? x.toFixed(3) : "—");

export function App() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [sequence, setSequence] = useState<any[]>([]);
  const [cuped, setCuped] = useState(false);

  useEffect(() => {
    fetch("/api/experiments")
      .then((r) => r.json())
      .then((e: Experiment[]) => {
        setExperiments(e);
        if (e.length) setSelected(e[0].key);
      });
  }, []);

  useEffect(() => {
    if (!selected) return;
    const exp = experiments.find((e) => e.key === selected);
    const metric = exp?.primary_metric ?? "";
    fetch(`/api/experiments/${selected}/results?metric=${metric}&cuped=${cuped}`)
      .then((r) => r.json())
      .then(setResults);
    fetch(`/api/experiments/${selected}/sequence?metric=${metric}&step=50`)
      .then((r) => r.json())
      .then(setSequence);
  }, [selected, cuped, experiments]);

  const exp = experiments.find((e) => e.key === selected);

  return (
    <div className="app">
      <div className="sidebar">
        <h1>◮ A2 Experiments</h1>
        {experiments.map((e) => (
          <div
            key={e.key}
            className={`exp-item ${e.key === selected ? "active" : ""}`}
            onClick={() => setSelected(e.key)}
          >
            <div className="key">
              {e.key}
              <span className={`badge ${e.status}`}>{e.status}</span>
            </div>
            <div className="hyp">{e.hypothesis}</div>
          </div>
        ))}
      </div>

      <div className="main">
        {exp && results ? (
          <>
            <h2>{exp.key}</h2>
            <div className="sub">
              {exp.hypothesis} · primary metric: <b>{exp.primary_metric}</b>
            </div>

            <label className="toggle">
              <input
                type="checkbox"
                checked={cuped}
                onChange={(e) => setCuped(e.target.checked)}
              />
              CUPED variance reduction
              {results.pooled.cuped_variance_reduction != null && (
                <b style={{ color: "#7ee787" }}>
                  {" "}
                  −{(results.pooled.cuped_variance_reduction * 100).toFixed(1)}% variance
                </b>
              )}
            </label>

            <div className="row">
              <div className="card">
                <div className="label">Effect (treatment − control)</div>
                <div className={`value ${results.pooled.significant ? "sig" : "nosig"}`}>
                  {fmt(results.pooled.effect)}
                </div>
              </div>
              <div className="card">
                <div className="label">Always-valid 95% CI</div>
                <div className="value" style={{ fontSize: 18 }}>
                  [{fmt(results.pooled.ci_lower)}, {fmt(results.pooled.ci_upper)}]
                </div>
              </div>
              <div className="card">
                <div className="label">Decision</div>
                <div className={`value ${results.pooled.significant ? "sig" : "nosig"}`}>
                  {results.pooled.significant ? "SIGNIFICANT" : "inconclusive"}
                </div>
              </div>
              <div className="card">
                <div className="label">SRM</div>
                <div className={`value ${results.srm.flagged ? "bad" : "nosig"}`} style={{ fontSize: 18 }}>
                  {results.srm.flagged ? "MISMATCH" : "balanced"}
                  <div style={{ fontSize: 12, color: "#8b93a7" }}>
                    p={fmt(results.srm.p_value)} · {results.srm.observed.join(" / ")}
                  </div>
                </div>
              </div>
            </div>

            <div className="section-title">Confidence sequence (legitimate peeking)</div>
            <SeqChart points={sequence} />

            {results.guardrails.length > 0 && (
              <>
                <div className="section-title">Guardrails</div>
                <table>
                  <thead>
                    <tr><th>Metric</th><th>Effect</th><th>Direction</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {results.guardrails.map((g) => (
                      <tr key={g.metric}>
                        <td>{g.metric}</td>
                        <td>{fmt(g.effect)}</td>
                        <td>{g.direction}</td>
                        <td>
                          <span className={`pill ${g.flagged ? "flag" : "ok"}`}>
                            {g.flagged ? "REGRESSION" : "ok"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            {Object.keys(results.segments).length > 0 && (
              <>
                <div className="section-title">Segment slices (heterogeneous effects)</div>
                <table>
                  <thead>
                    <tr><th>Segment</th><th>Effect</th><th>CI</th><th>Significant</th></tr>
                  </thead>
                  <tbody>
                    {Object.entries(results.segments).map(([seg, s]) => (
                      <tr key={seg}>
                        <td>{seg}</td>
                        <td>{fmt(s.effect)}</td>
                        <td>[{fmt(s.ci_lower)}, {fmt(s.ci_upper)}]</td>
                        <td>
                          <span className={`pill ${s.significant ? "ok" : ""}`}>
                            {s.significant ? "yes" : "no"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        ) : (
          <div>Loading…</div>
        )}
      </div>
    </div>
  );
}
