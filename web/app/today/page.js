"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import Shell from "../../components/Shell";

function todayISO() {
  const d = new Date();
  const tz = 330;
  const local = new Date(d.getTime() + tz * 60 * 1000);
  return local.toISOString().slice(0, 10);
}

export default function TodayPage() {
  const [date, setDate] = useState(todayISO());
  const [doctors, setDoctors] = useState([]);
  const [doctorId, setDoctorId] = useState("");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const docs = await api("/staff/doctors");
      setDoctors(docs);
      const q = new URLSearchParams({ date });
      if (doctorId) q.set("doctor_id", doctorId);
      setRows(await api(`/staff/appointments?${q}`));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [date, doctorId]);

  async function mark(id, status) {
    await api(`/staff/appointments/${id}/status`, { method: "POST", json: { status } });
    load();
  }

  return (
    <Shell>
      <div className="card">
        <h1>Today’s list</h1>
        <div className="row">
          <label>
            Date
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label>
            Doctor
            <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
              <option value="">All</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={load}>
            Refresh
          </button>
        </div>
        {error ? <p>{error}</p> : null}
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Patient</th>
              <th>Phone</th>
              <th>Doctor</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td>{a.slot_start.slice(11, 16)}</td>
                <td>{a.patient.name}</td>
                <td>{a.patient.phone}</td>
                <td>{a.doctor.name}</td>
                <td>
                  <span className="pill">{a.status}</span>
                </td>
                <td>
                  {a.status !== "checked_in" && a.status !== "cancelled" ? (
                    <button type="button" onClick={() => mark(a.id, "checked_in")}>
                      Arrived
                    </button>
                  ) : null}{" "}
                  {a.status !== "no_show" && a.status !== "cancelled" && a.status !== "completed" ? (
                    <button className="ghost" type="button" onClick={() => mark(a.id, "no_show")}>
                      No-show
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={6} className="muted">
                  No appointments for this day.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
