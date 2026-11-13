// Find Parking page: map, nearest-lot search, filters and booking

const state = { lat: 19.1364, lng: 72.8296, type: "car", lots: [], selected: null };
const TYPE_LABEL = { car: "car", bike: "bike", ev: "EV" };
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- map setup
const map = L.map("map").setView([state.lat, state.lng], 14);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const lotLayer = L.layerGroup().addTo(map);
const markers = {};
const me = L.marker([state.lat, state.lng], {
  draggable: true,
  zIndexOffset: 1000,
  icon: L.divIcon({ className: "", html: '<div class="me"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
}).addTo(map).bindTooltip("You are here (drag me)");

me.on("dragend", () => { const p = me.getLatLng(); setLocation(p.lat, p.lng, false); });
map.on("click", (e) => setLocation(e.latlng.lat, e.latlng.lng, false));

function setLocation(lat, lng, recenter) {
  state.lat = lat;
  state.lng = lng;
  me.setLatLng([lat, lng]);
  if (recenter) map.setView([lat, lng], 14);
  loadLots();
}

// ------------------------------------------------------------ loading data
function level(lot) {
  if (lot.available_slots <= 0) return "full";
  return lot.available_slots / lot.total_slots <= 0.3 ? "warn" : "good";
}
const LEVEL_TEXT = { good: "Free", warn: "Filling up", full: "Full" };

async function loadLots() {
  const params = new URLSearchParams({
    lat: state.lat, lng: state.lng, vehicle_type: state.type,
    radius_km: $("radius").value, max_price: $("maxPrice").value,
    available_only: $("availableOnly").checked ? 1 : 0,
    covered: $("covered").checked ? 1 : 0,
  });
  try {
    state.lots = await api("/api/lots?" + params);
  } catch (err) {
    $("count").textContent = "Could not load parking lots";
    toast(err.message, true);
    return;
  }
  renderList();
  renderMarkers();
}

function renderList() {
  const n = state.lots.length;
  if (n) {
    // one-line summary: free slots nearby, nearest lot and cheapest price
    const free = state.lots.reduce((sum, lot) => sum + Math.round(lot.available_slots), 0);
    const cheapest = Math.min(...state.lots.map((lot) => lot.price_per_hour));
    $("count").textContent = `${free} free ${TYPE_LABEL[state.type]} slots in ${n} ${n === 1 ? "lot" : "lots"}. ` +
      `Nearest is ${state.lots[0].distance_km} km away, cheapest is ${rupees(cheapest)}/hr.`;
  } else {
    $("count").textContent = "No parking lots found here";
  }
  $("lots").innerHTML = n ? state.lots.map((lot) => {
    const lv = level(lot);
    return `
    <li class="lot ${lot.lot_id === state.selected ? "on" : ""}" data-id="${lot.lot_id}">
      <div class="lot-top">
        <h3>${esc(lot.name)}</h3>
        <span class="price">${rupees(lot.price_per_hour)}<small>/hr</small></span>
      </div>
      <p class="addr">${esc(lot.address)}</p>
      <div class="meta">
        <span class="tag">${lot.distance_km} km away</span>
        <span class="tag ${lv}">${LEVEL_TEXT[lv]}: ${Math.round(lot.available_slots)} of ${lot.total_slots} slots</span>
        <span class="tag">${lot.open_time === "00:00" ? "Open 24 hours" : `${lot.open_time} to ${lot.close_time}`}</span>
        ${lot.is_covered ? '<span class="tag">Covered</span>' : ""}
        ${lot.has_cctv ? '<span class="tag">CCTV</span>' : ""}
        ${lot.has_ev_charging ? '<span class="tag">EV charging</span>' : ""}
      </div>
      <div class="row">
        <button class="btn btn-primary btn-small" data-book="${lot.lot_id}" ${lv === "full" ? "disabled" : ""}>Book a slot</button>
        <a class="btn btn-light btn-small" target="_blank" rel="noopener"
           href="https://www.google.com/maps/dir/?api=1&origin=${state.lat},${state.lng}&destination=${lot.latitude},${lot.longitude}">Directions</a>
      </div>
    </li>`;
  }).join("") : '<li class="empty">Nothing matches here. Try a bigger distance or remove a filter.</li>';
}

function renderMarkers() {
  lotLayer.clearLayers();
  for (const key in markers) delete markers[key];
  state.lots.forEach((lot) => {
    const lv = level(lot);
    const icon = L.divIcon({
      className: "",
      html: `<div class="pin ${lv} ${lot.lot_id === state.selected ? "on" : ""}">${Math.round(lot.available_slots)}</div>`,
      iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16],
    });
    const marker = L.marker([lot.latitude, lot.longitude], { icon, title: lot.name }).addTo(lotLayer);
    marker.bindPopup(`
      <h3>${esc(lot.name)}</h3>
      <div>${esc(lot.area)}, ${lot.distance_km} km away</div>
      <div><strong>${rupees(lot.price_per_hour)}/hr</strong> for a ${TYPE_LABEL[state.type]} slot</div>
      <div>${Math.round(lot.available_slots)} of ${lot.total_slots} slots free</div>
      <div class="row">
        <button class="btn btn-primary btn-small" data-book="${lot.lot_id}" ${lv === "full" ? "disabled" : ""}>Book a slot</button>
      </div>`);
    marker.on("click", () => select(lot.lot_id, false));
    markers[lot.lot_id] = marker;
  });
}

function select(lotId, openPopup) {
  state.selected = lotId;
  document.querySelectorAll(".lot").forEach((li) => li.classList.toggle("on", Number(li.dataset.id) === lotId));
  const li = document.querySelector(`.lot[data-id="${lotId}"]`);
  if (li) li.scrollIntoView({ block: "nearest", behavior: "smooth" });
  const lot = state.lots.find((l) => l.lot_id === lotId);
  if (openPopup && lot) {
    map.setView([lot.latitude, lot.longitude], Math.max(map.getZoom(), 15));
    markers[lotId].openPopup();
  }
}

// ----------------------------------------------------------------- filters
async function loadAreas() {
  const areas = await api("/api/areas");
  $("area").innerHTML = '<option value="">Choose an area...</option>' +
    areas.map((a) => `<option value="${a.latitude},${a.longitude}">${esc(a.name)}</option>`).join("");
}

$("area").addEventListener("change", (e) => {
  if (!e.target.value) return;
  const [lat, lng] = e.target.value.split(",").map(Number);
  setLocation(lat, lng, true);
});

$("locate").addEventListener("click", () => {
  if (!navigator.geolocation) return toast("Your browser does not support location", true);
  toast("Finding your location...");
  navigator.geolocation.getCurrentPosition(
    (pos) => { $("area").value = ""; setLocation(pos.coords.latitude, pos.coords.longitude, true); },
    () => toast("Could not get your location. Click on the map instead.", true),
    { enableHighAccuracy: true, timeout: 8000 });
});

document.querySelectorAll(".seg button").forEach((button) =>
  button.addEventListener("click", () => {
    document.querySelectorAll(".seg button").forEach((b) => b.classList.toggle("on", b === button));
    state.type = button.dataset.type;
    loadLots();
  }));

["radius", "maxPrice", "availableOnly", "covered"].forEach((id) => $(id).addEventListener("change", loadLots));

// ----------------------------------------------------------------- booking
let bookingLot = null;

function openBooking(lotId) {
  bookingLot = state.lots.find((l) => l.lot_id === lotId);
  if (!bookingLot) return;
  $("mName").textContent = bookingLot.name;
  $("mInfo").textContent = `${TYPE_LABEL[state.type]} slot in ${bookingLot.area}, ${rupees(bookingLot.price_per_hour)} per hour`.replace(/^./, (c) => c.toUpperCase());
  $("mResult").hidden = true;
  $("bookForm").querySelector("button[type=submit]").hidden = false;
  updateCost();
  $("modal").hidden = false;
}

function updateCost() {
  if (bookingLot) $("mCost").textContent = rupees(bookingLot.price_per_hour * $("bookForm").hours.value);
}

// one click handler for every "Book a slot" button (list and map popups)
document.addEventListener("click", (e) => {
  const book = e.target.closest("[data-book]");
  if (book) return openBooking(Number(book.dataset.book));
  const card = e.target.closest(".lot");
  if (card && !e.target.closest("a")) select(Number(card.dataset.id), true);
});

$("bookForm").hours.addEventListener("change", updateCost);
$("closeModal").addEventListener("click", () => ($("modal").hidden = true));
$("modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("modal").hidden = true; });

$("bookForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    const result = await postJSON("/api/bookings", {
      lot_id: bookingLot.lot_id,
      vehicle_type: state.type,
      customer_name: form.customer_name.value,
      vehicle_number: form.vehicle_number.value,
      hours: Number(form.hours.value),
    });
    $("mResult").innerHTML = `Booked. Park in slot <span class="slot">${esc(result.slot_code)}</span>
      Booking #${result.booking_id} for ${esc(result.vehicle_number)}.<br>
      Check out from <a href="/bookings">My Bookings</a> when you leave.`;
    $("mResult").hidden = false;
    form.querySelector("button[type=submit]").hidden = true;
    loadLots();
  } catch (err) {
    toast(err.message, true);
  }
});

// -------------------------------------------------------------------- start
loadAreas().catch((err) => toast(err.message, true));
loadLots();
setInterval(loadLots, 30000);   // refresh availability every 30 seconds
