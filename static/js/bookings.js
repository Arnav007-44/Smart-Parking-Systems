// My Bookings page: look up bookings by vehicle number and check out

const results = document.getElementById("results");
const input = document.getElementById("vehicle");

async function search() {
  const number = input.value.trim();
  if (!number) return;
  let rows;
  try {
    rows = await api("/api/bookings?vehicle_number=" + encodeURIComponent(number));
  } catch (err) {
    return toast(err.message, true);
  }
  if (!rows.length) {
    results.innerHTML = '<p class="empty">No bookings found for this vehicle number.</p>';
    return;
  }
  results.innerHTML = `
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Vehicle</th><th>Parking lot</th><th>Slot</th><th>Started</th><th>Ended</th><th>Amount</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows.map((b) => `
        <tr>
          <td>${b.booking_id}</td>
          <td><span class="plate">${esc(b.vehicle_number)}</span></td>
          <td>${esc(b.lot_name)}<br><span class="muted">${esc(b.area)}</span></td>
          <td>${esc(b.slot_code)} (${esc(b.vehicle_type)})</td>
          <td>${esc(b.start_time.slice(0, 16))}</td>
          <td>${b.end_time ? esc(b.end_time.slice(0, 16)) : "-"}</td>
          <td>${b.amount == null ? `${rupees(b.price_per_hour)}/hr` : rupees(b.amount)}</td>
          <td><span class="status ${esc(b.status)}">${esc(b.status)}</span></td>
          <td>${b.status === "active" ? `
            <select data-method="${b.booking_id}" aria-label="Payment method">
              <option value="upi">UPI</option><option value="card">Card</option>
              <option value="cash">Cash</option><option value="wallet">Wallet</option>
            </select>
            <button class="btn btn-primary btn-small" data-checkout="${b.booking_id}">Pay and check out</button>` : ""}</td>
        </tr>`).join("")}
      </tbody>
    </table></div>`;
}

document.getElementById("searchForm").addEventListener("submit", (e) => { e.preventDefault(); search(); });

results.addEventListener("click", async (e) => {
  const id = e.target.dataset.checkout;
  if (!id) return;
  const method = results.querySelector(`[data-method="${id}"]`).value;
  try {
    const bill = await postJSON(`/api/bookings/${id}/checkout`, { method });
    toast(`Paid ${rupees(bill.amount)} for ${bill.hours_billed} hour(s). Thank you!`);
    search();
  } catch (err) {
    toast(err.message, true);
  }
});
