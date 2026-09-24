import Link from "next/link";
export default function NotFound() {
  return (
    <div className="empty-state">
      <h1>That play is out of bounds.</h1>
      <p>The page you’re looking for isn’t here.</p>
      <Link href="/" className="button primary">
        Back to home
      </Link>
    </div>
  );
}
