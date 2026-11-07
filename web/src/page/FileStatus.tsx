import { statusText } from '../components/States';
import { CHART_NAMES, CHARTS, DATA_FILES, DATA_KEYS, chartPath } from '../data/files';
import type { AllFiles } from '../data/source';

/** Every file the site reads, who owes it, when, and whether it has landed. */
export function FileStatus({ files }: { files: AllFiles }) {
  const rows = [
    ...DATA_KEYS.map((k) => ({
      file: DATA_FILES[k].path,
      owner: DATA_FILES[k].owner,
      due: DATA_FILES[k].due,
      status: files.data[k],
    })),
    ...CHART_NAMES.map((c) => ({
      file: chartPath(c),
      owner: CHARTS[c].owner,
      due: CHARTS[c].due,
      status: files.charts[c],
    })),
  ];
  const loaded = rows.filter((r) => r.status.state === 'ok').length;

  return (
    <details className="file-status" open>
      <summary>
        Files: {loaded} of {rows.length} loaded
      </summary>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Every file the site reads and whether it has arrived</caption>
          <thead>
            <tr>
              <th scope="col">File</th>
              <th scope="col">From</th>
              <th scope="col">Due</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const s = statusText(r.status);
              return (
                <tr key={r.file}>
                  <th scope="row">
                    <code>{r.file}</code>
                  </th>
                  <td>{r.owner}</td>
                  <td>{r.due}</td>
                  <td className={`tone-${s.tone}`}>
                    <span aria-hidden="true">{s.symbol}</span> {s.text}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note">
        The farm year files (<code>data/farm_weeks/&lt;year&gt;.json</code>) load when you pick a year
        in finding 1.
      </p>
    </details>
  );
}
