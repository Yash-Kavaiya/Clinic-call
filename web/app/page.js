"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("reception@adajan.clinic");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("token")) {
      router.replace("/today");
    }
  }, [router]);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await api("/staff/login", { method: "POST", json: { email, password } });
      setToken(data.token);
      localStorage.setItem("staff_name", data.name);
      router.push("/today");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="login card">
      <h1>Adajan Family Clinic</h1>
      <p className="muted">Reception console</p>
      <form onSubmit={onSubmit} className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error ? <p className="muted">{error}</p> : null}
        <button type="submit">Sign in</button>
      </form>
    </div>
  );
}
