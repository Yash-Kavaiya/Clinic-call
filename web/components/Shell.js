"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Shell({ children }) {
  const router = useRouter();
  const path = usePathname();
  useEffect(() => {
    if (!localStorage.getItem("token")) router.replace("/");
  }, [router]);

  function logout() {
    localStorage.removeItem("token");
    router.replace("/");
  }

  return (
    <>
      <header className="top">
        <strong>Adajan Family Clinic</strong>
        <nav>
          <Link href="/today">Today</Link>
          <Link href="/walk-in">Walk-in</Link>
          <Link href="/patients">Patients</Link>
          <Link href="/calls">Calls</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <button className="ghost" onClick={logout} style={{ color: "#1f3d2b" }}>
          Sign out
        </button>
      </header>
      <main className="wrap">{children}</main>
    </>
  );
}
