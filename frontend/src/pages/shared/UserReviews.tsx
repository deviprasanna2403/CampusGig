import { useParams } from "react-router-dom";
import ErrorState from "../../components/ErrorState";
import ReviewsList from "../../components/reviews/ReviewsList";

/** Reviews received by one user account — linked to from dashboards and cards. */
export default function UserReviews() {
  const { userId } = useParams<{ userId: string }>();

  if (!userId) return <ErrorState error={new Error("Missing user id.")} retry={() => undefined} />;

  return (
    <section>
      <h1>Reviews</h1>
      <p className="muted">Ratings and comments left after completed engagements.</p>
      <div className="card">
        <ReviewsList userId={userId} />
      </div>
    </section>
  );
}
