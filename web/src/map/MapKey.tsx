import { MAP, layerInfo, type LayerKey, type Mark, type Ramp } from './scales';

/** One legend mark, drawn the way the map draws it, on the map's own sea colour. */
export function Swatch({ mark }: { mark: Mark }) {
  const c = 9;
  return (
    <svg className="swatch" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
      {mark.shape === 'empty' ? (
        <circle cx={c} cy={c} r={3.2} fill="none" stroke={mark.fill} strokeWidth={1.2} />
      ) : mark.shape === 'diamond' ? (
        <path d={`M${c} ${c - 6}L${c + 6} ${c}L${c} ${c + 6}L${c - 6} ${c}Z`} fill={mark.fill} stroke={MAP.sea} strokeWidth={1.2} />
      ) : (
        <circle cx={c} cy={c} r={4.4} fill={mark.fill} stroke={MAP.sea} strokeWidth={1.2} />
      )}
      {mark.ring ? <circle cx={c} cy={c} r={7.1} fill="none" stroke={MAP.ring} strokeWidth={1.3} /> : null}
    </svg>
  );
}

/** A binned scale as one bar: a segment per bin, the break values between them. */
function RampBar({ ramp }: { ramp: Ramp }) {
  const n = ramp.colors.length;
  return (
    <>
      <div className="key-ramp" aria-hidden="true">
        <div className="key-ramp-bar">
          {ramp.colors.map((c) => (
            <span key={c} style={{ background: c }} />
          ))}
        </div>
        <div className="key-ramp-ticks">
          {ramp.breaks.map((b, i) => (
            <span key={b} style={{ left: `${((i + 1) / n) * 100}%` }}>
              {b}
            </span>
          ))}
        </div>
        {ramp.ends ? (
          <div className="key-ramp-ends">
            <span>{ramp.ends[0]}</span>
            <span>{ramp.ends[1]}</span>
          </div>
        ) : null}
      </div>
      <ul className="sr-only">
        {ramp.labels.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </>
  );
}

/** The colour key for the map's current layer. */
export function MapKey({ layer }: { layer: LayerKey }) {
  const info = layerInfo(layer);
  return (
    <div className="map-key">
      <p className="map-key-title">{info.title}</p>
      {info.ramp ? <RampBar ramp={info.ramp} /> : null}
      <ul className="map-key-items">
        {info.items.map((item) => (
          <li key={item.label}>
            <Swatch mark={item.mark} />
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
      {info.note ? <p className="map-key-note">{info.note}</p> : null}
    </div>
  );
}
