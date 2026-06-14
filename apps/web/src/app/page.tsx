import Link from "next/link";
import { Navbar } from "@/components/Navbar";

export default function HomePage() {
  return (
    <div className="hero-gradient min-h-screen">
      <Navbar />
      <main className="mx-auto max-w-6xl px-6 pb-24 pt-16 text-center">
        <p className="mb-4 text-sm font-medium text-violet-300">
          AI Mock Interview
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-white md:text-6xl">
          Practice Your Interview with Voice AI
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
          Two focused questions with push-to-record answers — introduce yourself,
          then share your past experience.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <Link
            href="/login"
            className="rounded-full bg-emerald-500 px-8 py-3 font-semibold text-[#0b1020] hover:bg-emerald-400"
          >
            Get Started
          </Link>
        </div>
      </main>

      <section id="features" className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-6 md:grid-cols-2">
          {[
            {
              title: "Two clear questions",
              desc: "Self-introduction, then past experience — no extra prompts.",
            },
            {
              title: "Record when you are ready",
              desc: "Press Record to answer, Done when finished, then hear the next question.",
            },
          ].map((f) => (
            <div key={f.title} className="card-glass p-6 text-left">
              <h3 className="text-lg font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
