// Analytics page: KPI tiles and charts (Chart.js), data from /api/analytics

// colours chosen for the dark background
const BLUE = "#3987e5", ORANGE = "#d95926", INK = "#c3c2b7", GRID = "#343a43";

Chart.defaults.font.family = '"Barlow", "Segoe UI", system-ui, Arial, sans-serif';
Chart.defaults.font.size = 13;
Chart.defaults.color = INK;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation.duration = 400;
Chart.defaults.plugins.legend.display = false;

const number = (v) => Number(v).toLocaleString("en-IN");
const compact = (v) => (v >= 100000 ? (v / 100000).toFixed(1) + "L" : v >= 1000 ? +(v / 1000).toFixed(1) + "k" : v);

function barChart(id, labels, values, { horizontal = false, format = number, title = "", max } = {}) {
  const valueAxis = { beginAtZero: true, max, grid: { color: GRID }, border: { display: false }, ticks: { callback: (v) => compact(v) } };
  const labelAxis = { grid: { display: false }, ticks: { autoSkip: !horizontal, maxRotation: 0 } };
  return new Chart(document.getElementById(id), {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: BLUE, borderRadius: 4, maxBarThickness: 34 }] },
    options: {
      indexAxis: horizontal ? "y" : "x",
      scales: horizontal ? { x: valueAxis, y: labelAxis } : { x: labelAxis, y: valueAxis },
      plugins: {
        title: { display: !!title, text: title, align: "start", color: "#f1efe9", font: { weight: "600" } },
        tooltip: { callbacks: { label: (ctx) => format(ctx.raw) } },
      },
    },
  });
}

function hourLabel(h) {
  return h === 0 ? "12am" : h < 12 ? h + "am" : h === 12 ? "12pm" : h - 12 + "pm";
}

async function load() {
  let d;
  try {
    d = await api("/api/analytics");
  } catch (err) {
    return toast(err.message, true);
  }
  const s = d.summary;
  const occupancy = s.total_slots ? Math.round((100 * s.occupied_now) / s.total_slots) : 0;
  document.getElementById("kpis").innerHTML = [
    ["Parking lots", number(s.total_lots), `${number(s.total_slots)} slots`],
    ["Occupied right now", occupancy + "%", `${number(s.occupied_now)} of ${number(s.total_slots)} slots`],
    ["Revenue today", rupees(s.revenue_today), "so far"],
    ["Revenue, 30 days", rupees(s.revenue_30d), `${number(s.bookings_30d)} bookings`],
    ["Average stay", (s.avg_hours ?? 0) + " hrs", "per booking"],
  ].map(([label, value, note]) =>
    `<div class="kpi"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join("");

  barChart("peak", d.peak_hours.map((r) => hourLabel(r.hour)), d.peak_hours.map((r) => r.avg_bookings),
    { format: (v) => `${number(v)} bookings per day in this hour` });

  new Chart(document.getElementById("trend"), {
    type: "line",
    data: {
      labels: d.revenue_trend.map((r) => new Date(r.day).toLocaleDateString("en-IN", { day: "numeric", month: "short" })),
      datasets: [
        { label: "Daily revenue", data: d.revenue_trend.map((r) => r.revenue), borderColor: BLUE, backgroundColor: BLUE,
          borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.25 },
        { label: "7-day average", data: d.revenue_trend.map((r) => r.avg_7d), borderColor: ORANGE, backgroundColor: ORANGE,
          borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 5, tension: 0.25 },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 10, maxRotation: 0 } },
        y: { beginAtZero: true, grid: { color: GRID }, border: { display: false }, ticks: { callback: (v) => "₹" + compact(v) } },
      },
      plugins: {
        legend: { display: true, align: "end", labels: { boxWidth: 18, boxHeight: 2 } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${rupees(ctx.raw)}` } },
      },
    },
  });

  barChart("revLot", d.revenue_by_lot.map((r) => r.lot.replace(" Parking", "")), d.revenue_by_lot.map((r) => r.revenue),
    { horizontal: true, format: rupees });
  barChart("occ", d.occupancy.map((r) => r.lot.replace(" Parking", "")), d.occupancy.map((r) => r.occupancy_pct),
    { horizontal: true, max: 100, format: (v) => v + "% occupied" });
  barChart("week", d.weekdays.map((r) => r.day.slice(0, 3)), d.weekdays.map((r) => r.avg_bookings),
    { format: (v) => `${number(v)} bookings per day` });
  barChart("mix", d.vehicle_mix.map((r) => ({ car: "Car", bike: "Bike", ev: "EV" }[r.vehicle_type])),
    d.vehicle_mix.map((r) => r.bookings), { horizontal: true, title: "Bookings by vehicle", format: (v) => number(v) + " bookings" });
  barChart("pay", d.payment_methods.map((r) => ({ upi: "UPI", card: "Card", cash: "Cash", wallet: "Wallet" }[r.method])),
    d.payment_methods.map((r) => r.payments), { horizontal: true, title: "Payments by method", format: (v) => number(v) + " payments" });
}

load();
