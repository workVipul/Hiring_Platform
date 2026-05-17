import JDTable from "@/components/dashboard/JDTable";

export default function DashboardPage() {
  return (
    <section className="page-section">
      <div className="page-heading">
        <p className="eyebrow">Dashboard</p>
        <h1>Job Descriptions</h1>
        <p className="muted">Published JDs across your hiring workspace.</p>
      </div>
      <JDTable />
    </section>
  );
}
