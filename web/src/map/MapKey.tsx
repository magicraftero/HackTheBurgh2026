import { useId } from 'react';
import { LAYERS, MAP, layerInfo, type LayerKey, type Mark, type Ramp } from './scales';

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
              {ramp.ticks?.[i] ?? b}
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

type KeyProps = {
  layer: LayerKey;
  onLayer: (l: LayerKey) => void;
  /** False when this year's file has no disease flags. */
  hasDisease: boolean;
  showAreas: boolean;
  onShowAreas: (on: boolean) => void;
};

/** Pick what the map shows, and read what the colours mean, in one place. */
export function MapKey({ layer, onLayer, hasDisease, showAreas, onShowAreas }: KeyProps) {
  const name = useId();
  const info = layerInfo(layer);
  return (
    <div className="map-key">
      <fieldset className="key-layers">
        <legend>Colour the farms by</legend>
        {LAYERS.map((l) => {
          const off = l.key === 'disease' && !hasDisease;
          return (
            <label key={l.key} className="key-layer" title={off ? 'No disease flags in this year’s file' : undefined}>
              <input type="radio" name={name} value={l.key} checked={layer === l.key} disabled={off} onChange={() => onLayer(l.key)} />
              <span>{l.label}</span>
            </label>
          );
        })}
      </fieldset>
      <p className="map-key-title">{info.title}</p>
      <RampBar ramp={info.ramp} />
      <p className="map-key-heat">Averaged over the farms within about 10 km.</p>
      <ul className="map-key-items">
        <li className="map-key-lead">Zoomed in:</li>
        {info.items.map((item) => (
          <li key={item.label}>
            <Swatch mark={item.mark} />
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
      {info.note ? <p className="map-key-note">{info.note}</p> : null}
      <label className="map-check">
        <input type="checkbox" checked={showAreas} onChange={(e) => onShowAreas(e.target.checked)} />
        <span>Show production area numbers</span>
      </label>
    </div>
  );
}
