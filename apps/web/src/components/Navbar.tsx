"use client";

import Link from "next/link";
import { clearToken } from "@/lib/api";

export function Navbar({ showAuth = true }: { showAuth?: boolean }) {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#0b1020]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-xl font-bold text-white">
          Jobnova
        </Link>
        <nav className="hidden gap-8 text-sm text-slate-300 md:flex">
          <Link href="/#features">Features</Link>
        </nav>
        {showAuth && (
          <div className="flex gap-3">
            <Link
              href="/login"
              className="rounded-full border border-white/20 px-4 py-2 text-sm text-white hover:bg-white/10"
            >
              Login
            </Link>
            <Link
              href="/dashboard"
              className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-[#0b1020] hover:bg-emerald-400"
            >
              Dashboard
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}

export function LogoutButton() {
  return (
    <button
      type="button"
      onClick={() => {
        clearToken();
        window.location.href = "/login";
      }}
      className="text-sm text-slate-400 hover:text-white"
    >
      Log out
    </button>
  );
}
