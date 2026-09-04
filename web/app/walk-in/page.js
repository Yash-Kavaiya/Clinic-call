"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import Shell from "../../components/Shell";

function todayISO() {
  const d = new Date();
  return new Date(d.getTime() + 330 * 60 * 1000).toISOString().slice(0, 10);
}

export default function WalkInPage() {
  const router = useRouter();
  const [doctors, setDoctors] = useState([]);
  const [date, setDate] = useState(todayISO());
  const [doctorId, setDoctorId] = useState("");
  const [slots, setSlots] = useState([]);
  const [slotId, setSlotId] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("walk-in");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api("/staff/doctors").then((d) => {
      setDoctors(d);
      if (d[0]) setDoctorId(String(d[0].id));
    });
  }, []);

  useEffect(() => {
    if (!date) return;
    const q = new URLSearchParams({ date });
    if (doctorId) q.set("doctor_id", doctorId);
    api(`/staff/availability?${q}`).then((s) => {
      setSlots(s);
      setSlotId(s[0]?.slot_id || "");
    });
  }, [date, doctorId]);

  async function submit(e) {
    e.preventDefault();
    setMsg("");
    const data = await api("/staff/appointments/walk-in", {
      method: "POST",
      json: { name, phone, slot_id: slotId, reason },
    });
    setMsg(`Booked #${data.id}`);
    router.push("/today");
  }

  return (
    <Shell>
      <div className="card">
        <h1>Walk-in</h1>
        <form onSubmit={submit}>
          <div className="row">
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label>
              Phone
              <input value={phone} onChange={(e) => setPhone(e.target.value)} required />
            </label>
            <label>
              Date
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <label>
              Doctor
              <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Slot
              <select value={slotId} onChange={(e) => setSlotId(e.target.value)}>
                {slots.map((s) => (
                  <option key={s.slot_id} value={s.slot_id}>
                    {s.speak_time} ({s.slot_start.slice(11, 16)})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Reason
              <input value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
            <button type="submit">Book</button>
          </div>
        </form>
        {msg ? <p>{msg}</p> : null}
      </div>
    </Shell>
  );
}
