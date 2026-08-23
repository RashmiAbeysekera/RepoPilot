import SystemStatusCard from "@/components/SystemStatusCard";

/**
 * This file is a Server Component by default (no "use client" here).
 * It renders once and contains no interactivity itself — it just lays
 * out static content and embeds the interactive SystemStatusCard.
 * Splitting it this way keeps the interactive part small and isolated.
 */
export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-8 px-4 py-16 bg-neutral-50 dark:bg-neutral-950">
      <header className="text-center">
        <h1 className="text-3xl font-bold tracking-tight">RepoPilot AI</h1>
        <p className="mt-2 text-neutral-500 dark:text-neutral-400">
          AI-powered software engineering assistant
        </p>
      </header>

      <SystemStatusCard />
    </main>
  );
}
