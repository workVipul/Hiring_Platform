import JDTable from "@/components/JDTable";

export const metadata = {
  title: "Job Descriptions — JDForge",
};

export default function JDsPage() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Job Descriptions</h1>
        <p className="mt-1 text-gray-500 text-sm">
          All JDs stored in the database. PDFs served from local storage (S3-ready).
        </p>
      </div>
      <JDTable />
    </main>
  );
}
