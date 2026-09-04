"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import Shell from "../../components/Shell";

export default function SettingsPage() {
  const [clinic, setClinic] = useState(null);
  const [msg, setMsg] = useState("");

  async function load() {
    setClinic(await api("/staff/clinic"));
  }

  useEffect(() => {
    load();
  }, []);

  async function toggle() {
    const next = clinic.voice_mode === "bot" ? "human" : "bot";
    await api("/staff/clinic/voice-mode", { method: "POST", json: { voice_mode: next } });
    setMsg(next === "human" ? "Kill-switch on: bot will route to human." : "Bot is live.");
    load();
  }

  if (!clinic) {
    return (
      <Shell>
        <p>Loading…</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="card">
        <h1>{clinic.name}</h1>
        <p>
          Voice mode: <span className="pill">{clinic.voice_mode}</span>
        </p>
        <p className="muted">{clinic.branch.address}</p>
        <p className="muted">Recording retention: {clinic.recording_retention_days} days</p>
        <button type="button" onClick={toggle}>
          {clinic.voice_mode === "bot" ? "Kill-switch: humans only" : "Resume bot"}
        </button>
        {msg ? <p>{msg}</p> : null}
        <p className="muted">
          Also swap the Exotel app to the humans-only flow if Sarvam is down. See docs/runbooks.
        </p>
      </div>
    </Shell>
  );
}
