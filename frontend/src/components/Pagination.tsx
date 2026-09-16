interface Props {
  count: number;
  page: number;
  pageSize?: number;
  onPage: (page: number) => void;
}

export default function Pagination({ count, page, pageSize = 20, onPage }: Props) {
  const last = Math.max(1, Math.ceil(count / pageSize));
  if (last <= 1) return null;
  const pages: number[] = [];
  for (let p = Math.max(1, page - 2); p <= Math.min(last, page + 2); p++) pages.push(p);

  return (
    <nav className="pagination" aria-label="Pagination">
      <button className="btn ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ← Prev
      </button>
      {pages[0] > 1 && <span className="muted">…</span>}
      {pages.map((p) => (
        <button
          key={p}
          className={`btn ${p === page ? "primary" : "ghost"}`}
          disabled={p === page}
          onClick={() => onPage(p)}
        >
          {p}
        </button>
      ))}
      {pages[pages.length - 1] < last && <span className="muted">…</span>}
      <button className="btn ghost" disabled={page >= last} onClick={() => onPage(page + 1)}>
        Next →
      </button>
    </nav>
  );
}
