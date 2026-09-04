"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import Shell from "../../components/Shell";

export default function PatientsPage() {
  const [phone, setPhone] = useState("");
  const [rows, setRows] = useState([]);
  const [name, setName] = useState("");
  const [newPhone, setNewPhone] = useState("");

  async function search(e) {
    e?.preventDefault();
    const q = phone ? `?phone=${encodeURIComponent(phone)}` : "";
    setRows(await api(`/staff/patients${q}`));
  }

  async function create(e) {
    e.preventDefault();
    await api("/staff/patients", { method: "POST", json: { name, phone: newPhone, language: "gu" } });
    setName("");
    setNewPhone("");
    search();
  }

  return (
    <Shell>
      <div className="card">
        <h1>Patients</h1>
        <form onSubmit={search} className="row">
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <button type="submit">Search</button>
        </form>
      </div>
      <div className="card">
        <h2>Register</h2>
        <form onSubmit={create} className="row">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Phone
            <input value={newPhone} onChange={(e) => setNewPhone(e.target.value)} required />
          </label>
          <button type="submit">Save</button>
        </form>
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Language</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.phone}</td>
                <td>{p.language}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
