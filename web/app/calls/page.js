"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import Shell from "../../components/Shell";

export default function CallsPage() {
  const [rows, setRows] = useState([]);
  const [detail, setDetail] = useState(null);

  async function load() {
    setRows(await api("/staff/calls"));
  }

  useEffect(() => {
    load();
  }, []);

  async function open(id) {
    setDetail(await api(`/staff/calls/${id}`));
  }

  return (
    <Shell>
      <div className="card">
        <h1>Call log</h1>
        <button type="button" onClick={load}>
          Refresh
        </button>
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>From</th>
              <th>SID</th>
              <th>Outcome</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>{c.created_at.replace("T", " ").slice(0, 16)}</td>
                <td>{c.from_phone}</td>
                <td>{c.exotel_sid || "—"}</td>
                <td>
                  <span className="pill">{c.outcome}</span>
                </td>
                <td>
                  <button className="ghost" type="button" onClick={() => open(c.id)}>
                    Transcript
                  </button>
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={5} className="muted">
                  No calls yet. Webhooks will land here.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {detail ? (
        <div className="card">
          <h2>Call {detail.exotel_sid}</h2>
          <p className="muted">{detail.transfer_reason}</p>
          {(detail.utterances || []).map((u, i) => (
            <p key={i}>
              <strong>{u.role}:</strong> {u.text}
            </p>
          ))}
        </div>
      ) : null}
    </Shell>
  );
}
