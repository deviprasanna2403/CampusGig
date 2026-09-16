import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="card center">
      <h1>404</h1>
      <p className="muted">That page doesn't exist.</p>
      <Link className="btn primary" to="/">
        Go home
      </Link>
    </section>
  );
}
