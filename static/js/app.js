/**
 * Resort CRM — vanilla JavaScript (ไม่ต้องมี build step / framework)
 *  - sidebar บนมือถือ
 *  - toast + ซ่อน flash message อัตโนมัติ
 *  - กราฟรายรับ (ดึงจาก /api/revenue/)
 *  - เปลี่ยนสถานะห้องแบบ realtime (POST /api/rooms/<id>/status/)
 *  - ตรวจห้องว่างในฟอร์มจอง (GET /api/availability/)
 */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const baht = (n) => "฿" + Number(n).toLocaleString("th-TH", { maximumFractionDigits: 0 });

  function csrfToken() {
    const cookie = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="));
    if (cookie) return decodeURIComponent(cookie.split("=")[1]);
    return $("[name=csrfmiddlewaretoken]")?.value || "";
  }

  async function api(url, { method = "GET", body } = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = csrfToken();
    }
    const res = await fetch(url, {
      method,
      headers,
      credentials: "same-origin",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function toast(message, type = "success") {
    const root = $("#toast-root");
    if (!root) return;
    const el = document.createElement("div");
    el.className = `toast ${type === "error" ? "bg-rose-600" : "bg-slate-900"} translate-y-2 opacity-0`;
    el.textContent = message;
    root.appendChild(el);
    requestAnimationFrame(() => el.classList.remove("translate-y-2", "opacity-0"));
    setTimeout(() => {
      el.classList.add("opacity-0");
      setTimeout(() => el.remove(), 300);
    }, 2500);
  }

  // --- Sidebar (mobile) ----------------------------------------------------
  $$("[data-sidebar-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      $("#sidebar")?.classList.toggle("-translate-x-full");
      $("#sidebar-backdrop")?.classList.toggle("hidden");
    })
  );

  // --- Flash messages ------------------------------------------------------
  $$("[data-autodismiss]").forEach((el) => {
    if (el.classList.contains("alert-error") || el.classList.contains("alert-warning")) return;
    setTimeout(() => {
      el.classList.add("opacity-0");
      setTimeout(() => el.remove(), 500);
    }, 4000);
  });

  // --- ยืนยันก่อน submit / auto-submit select --------------------------------
  $$("form[data-confirm]").forEach((form) =>
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    })
  );
  $$("select[data-autosubmit]").forEach((sel) => sel.addEventListener("change", () => sel.form.submit()));

  // --- Revenue chart -------------------------------------------------------
  const chart = $("#revenue-chart");
  if (chart) {
    api(chart.dataset.url)
      .then(({ days, sum }) => {
        const max = Math.max(...days.map((d) => d.total), 1);
        chart.innerHTML = "";
        days.forEach((d) => {
          const col = document.createElement("div");
          col.className = "group relative flex h-full flex-1 flex-col items-center justify-end gap-1";
          const pct = Math.max((d.total / max) * 100, d.total > 0 ? 3 : 1);
          col.innerHTML = `
            <span class="pointer-events-none absolute -top-1 hidden -translate-y-full whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-xs text-white group-hover:block">${d.label}: ${baht(d.total)}</span>
            <div class="w-full rounded-t-md bg-teal-500/80 transition group-hover:bg-teal-600" style="height:${pct}%"></div>
            <span class="text-[10px] text-slate-400">${d.label}</span>`;
          chart.appendChild(col);
        });
        const sumEl = $("#revenue-sum");
        if (sumEl) sumEl.textContent = `รวม ${baht(sum)}`;
      })
      .catch(() => {
        chart.innerHTML = '<p class="m-auto text-sm text-rose-500">โหลดข้อมูลไม่สำเร็จ</p>';
      });
  }

  // --- Room board: เปลี่ยนสถานะห้อง -------------------------------------------
  $$("select[data-room-status]").forEach((select) => {
    let previous = select.value;
    select.addEventListener("change", async () => {
      const card = select.closest(".room-card");
      select.disabled = true;
      try {
        const data = await api(select.dataset.url, { method: "POST", body: { status: select.value } });
        if (card) card.dataset.status = data.status;
        previous = data.status;
        toast(`ห้อง ${card?.querySelector("p")?.textContent ?? ""} → ${data.label}`);
      } catch (err) {
        select.value = previous;
        toast(`บันทึกไม่สำเร็จ: ${err.message}`, "error");
      } finally {
        select.disabled = false;
      }
    });
  });

  // --- Booking form: ตรวจห้องว่างตามวันที่ ------------------------------------
  const bookingForm = $("form[data-booking-form]");
  if (bookingForm) {
    const checkIn = $("#id_check_in", bookingForm);
    const checkOut = $("#id_check_out", bookingForm);
    const roomSelect = $("select[data-availability]", bookingForm);
    const hint = $("#availability-hint");

    $$("option", roomSelect).forEach((o) => (o.dataset.label = o.textContent));

    async function refresh() {
      if (!checkIn.value || !checkOut.value) return;
      if (checkOut.value <= checkIn.value) {
        hint.hidden = false;
        hint.textContent = "⚠️ วันเช็คเอาท์ต้องอยู่หลังวันเช็คอิน";
        return;
      }
      const params = new URLSearchParams({
        check_in: checkIn.value,
        check_out: checkOut.value,
        booking: bookingForm.dataset.bookingId || "",
      });
      try {
        const data = await api(`${bookingForm.dataset.availabilityUrl}?${params}`);
        const free = new Set(data.rooms.map((r) => String(r.id)));
        $$("option", roomSelect).forEach((o) => {
          if (!o.value) return;
          const ok = free.has(o.value);
          o.disabled = !ok;
          o.textContent = ok ? o.dataset.label : `${o.dataset.label} — ไม่ว่าง`;
        });
        hint.hidden = false;
        const selectedBusy = roomSelect.value && !free.has(roomSelect.value);
        hint.className = `mt-4 rounded-lg px-3 py-2 text-sm ${selectedBusy ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-800"}`;
        hint.textContent = selectedBusy
          ? `⚠️ ห้องที่เลือกไม่ว่างในช่วงนี้ — มีห้องว่าง ${data.rooms.length} ห้อง (${data.nights} คืน)`
          : `✓ มีห้องว่าง ${data.rooms.length} ห้อง สำหรับ ${data.nights} คืน`;
      } catch (err) {
        hint.hidden = false;
        hint.textContent = `ตรวจสอบห้องว่างไม่สำเร็จ: ${err.message}`;
      }
    }

    [checkIn, checkOut, roomSelect].forEach((el) => el?.addEventListener("change", refresh));
    refresh();
  }
})();
