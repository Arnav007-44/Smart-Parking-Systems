"""Smart Car Parking Management System - Flask backend.

Run:  python app.py   then open http://localhost:5001
"""
import math
import re
from datetime import date, datetime
from decimal import Decimal

import pymysql
from flask import Flask, g, jsonify, render_template, request

import config

app = Flask(__name__)
VEHICLE_TYPES = ("car", "bike", "ev")
PAYMENT_METHODS = ("upi", "card", "cash", "wallet")

# Distance in km between the user (%(lat)s, %(lng)s) and a lot (Haversine formula)
DISTANCE_SQL = """
    6371 * 2 * ASIN(SQRT(
        POWER(SIN(RADIANS(l.latitude - %(lat)s) / 2), 2) +
        COS(RADIANS(%(lat)s)) * COS(RADIANS(l.latitude)) *
        POWER(SIN(RADIANS(l.longitude - %(lng)s) / 2), 2)
    ))"""


# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                               password=config.DB_PASSWORD, database=config.DB_NAME,
                               cursorclass=pymysql.cursors.DictCursor, autocommit=True)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, params=None):
    with db().cursor() as cur:
        cur.execute(sql, params)
        return [clean(row) for row in cur.fetchall()]


def clean(row):
    """Convert MySQL types (Decimal, datetime) into JSON-friendly values."""
    out = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, (datetime, date)):
            value = value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
        out[key] = value
    return out


def error(message, code=400):
    return jsonify({"error": message}), code


@app.errorhandler(pymysql.err.OperationalError)
def database_down(_err):
    """Friendly message instead of a crash page when MySQL cannot be reached."""
    return error("Cannot connect to MySQL. Check that MySQL is running and the password in config.py is correct.", 503)


# ------------------------------------------------------------------- pages
@app.route("/")
def page_map():
    return render_template("index.html", active="map")


@app.route("/bookings")
def page_bookings():
    return render_template("bookings.html", active="bookings")


@app.route("/dashboard")
def page_dashboard():
    return render_template("dashboard.html", active="dashboard")


# ----------------------------------------------------------------- map API
@app.route("/api/areas")
def api_areas():
    return jsonify(query("SELECT area_id, name, latitude, longitude FROM areas ORDER BY name"))


@app.route("/api/lots")
def api_lots():
    """Parking lots near a point, nearest first, with live availability and price."""
    try:
        lat = float(request.args.get("lat", 19.1364))
        lng = float(request.args.get("lng", 72.8296))
        radius = float(request.args.get("radius_km", 5))
        max_price = float(request.args.get("max_price", 0))
    except ValueError:
        return error("lat, lng, radius_km and max_price must be numbers")
    vtype = request.args.get("vehicle_type", "car")
    if vtype not in VEHICLE_TYPES:
        return error("vehicle_type must be car, bike or ev")

    filters = ""
    if max_price > 0:
        filters += " AND p.price_per_hour <= %(max_price)s"
    if request.args.get("covered") == "1":
        filters += " AND l.is_covered = 1"
    if request.args.get("available_only") == "1":
        filters += " AND v.available_slots > 0"

    sql = f"""
        SELECT l.lot_id, l.name, a.name AS area, l.address, l.latitude, l.longitude,
               TIME_FORMAT(l.open_time, '%%H:%%i')  AS open_time,
               TIME_FORMAT(l.close_time, '%%H:%%i') AS close_time,
               l.is_covered, l.has_cctv, l.has_ev_charging,
               p.price_per_hour, v.total_slots, v.available_slots,
               ROUND({DISTANCE_SQL}, 2) AS distance_km
        FROM parking_lots l
        JOIN areas a              ON a.area_id = l.area_id
        JOIN lot_pricing p        ON p.lot_id = l.lot_id AND p.vehicle_type = %(vtype)s
        JOIN v_lot_availability v ON v.lot_id = l.lot_id AND v.vehicle_type = %(vtype)s
        WHERE 1 = 1 {filters}
        HAVING distance_km <= %(radius)s
        ORDER BY distance_km
    """
    return jsonify(query(sql, {"lat": lat, "lng": lng, "radius": radius,
                               "max_price": max_price, "vtype": vtype}))


@app.route("/api/lots/<int:lot_id>")
def api_lot_detail(lot_id):
    lot = query("""SELECT l.lot_id, l.name, a.name AS area, l.address, l.latitude, l.longitude,
                          TIME_FORMAT(l.open_time, '%%H:%%i') AS open_time,
                          TIME_FORMAT(l.close_time, '%%H:%%i') AS close_time,
                          l.is_covered, l.has_cctv, l.has_ev_charging
                   FROM parking_lots l JOIN areas a ON a.area_id = l.area_id
                   WHERE l.lot_id = %s""", (lot_id,))
    if not lot:
        return error("Parking lot not found", 404)
    lot = lot[0]
    lot["slot_types"] = query(
        """SELECT v.vehicle_type, p.price_per_hour, v.total_slots, v.available_slots
           FROM v_lot_availability v
           JOIN lot_pricing p ON p.lot_id = v.lot_id AND p.vehicle_type = v.vehicle_type
           WHERE v.lot_id = %s ORDER BY v.vehicle_type""", (lot_id,))
    return jsonify(lot)


# ------------------------------------------------------------- booking API
@app.route("/api/bookings", methods=["POST"])
def api_create_booking():
    data = request.get_json(silent=True) or {}
    name = str(data.get("customer_name", "")).strip()
    number = re.sub(r"[\s-]", "", str(data.get("vehicle_number", ""))).upper()
    vtype = data.get("vehicle_type")
    try:
        lot_id = int(data.get("lot_id"))
        hours = int(data.get("hours"))
    except (TypeError, ValueError):
        return error("lot_id and hours are required")
    if not 2 <= len(name) <= 80:
        return error("Please enter your name")
    if not re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}", number):
        return error("Enter a valid vehicle number, for example MH02AB1234")
    if vtype not in VEHICLE_TYPES:
        return error("vehicle_type must be car, bike or ev")
    if not 1 <= hours <= 24:
        return error("Hours must be between 1 and 24")

    conn = db()
    conn.begin()                      # transaction: so two people cannot get the same slot
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT booking_id FROM bookings WHERE vehicle_number=%s AND status='active'",
                        (number,))
            if cur.fetchone():
                conn.rollback()
                return error("This vehicle already has an active booking", 409)
            cur.execute("""SELECT s.slot_id, s.slot_code, p.price_per_hour, l.name AS lot_name
                           FROM slots s
                           JOIN lot_pricing p ON p.lot_id = s.lot_id AND p.vehicle_type = s.vehicle_type
                           JOIN parking_lots l ON l.lot_id = s.lot_id
                           WHERE s.lot_id=%s AND s.vehicle_type=%s AND s.status='available'
                           ORDER BY s.slot_id LIMIT 1 FOR UPDATE""", (lot_id, vtype))
            slot = cur.fetchone()
            if not slot:
                conn.rollback()
                return error("Sorry, no free slot of this type in this parking lot", 409)
            cur.execute("""INSERT INTO bookings (slot_id, customer_name, vehicle_number, vehicle_type,
                                                 start_time, expected_hours)
                           VALUES (%s,%s,%s,%s,NOW(),%s)""",
                        (slot["slot_id"], name, number, vtype, hours))
            booking_id = cur.lastrowid
            cur.execute("UPDATE slots SET status='occupied' WHERE slot_id=%s", (slot["slot_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    price = float(slot["price_per_hour"])
    return jsonify({"booking_id": booking_id, "lot_name": slot["lot_name"],
                    "slot_code": slot["slot_code"], "vehicle_number": number,
                    "price_per_hour": price, "estimated_amount": price * hours}), 201


@app.route("/api/bookings")
def api_list_bookings():
    number = re.sub(r"[\s-]", "", request.args.get("vehicle_number", "")).upper()
    if not number:
        return error("vehicle_number is required")
    return jsonify(query(
        """SELECT b.booking_id, b.customer_name, b.vehicle_number, b.vehicle_type, b.start_time,
                  b.end_time, b.expected_hours, b.amount, b.status,
                  s.slot_code, l.name AS lot_name, a.name AS area, p.price_per_hour
           FROM bookings b
           JOIN slots s        ON s.slot_id = b.slot_id
           JOIN parking_lots l ON l.lot_id = s.lot_id
           JOIN areas a        ON a.area_id = l.area_id
           JOIN lot_pricing p  ON p.lot_id = l.lot_id AND p.vehicle_type = b.vehicle_type
           WHERE b.vehicle_number = %s
           ORDER BY b.start_time DESC LIMIT 50""", (number,)))


@app.route("/api/bookings/<int:booking_id>/checkout", methods=["POST"])
def api_checkout(booking_id):
    """Vehicle leaves: work out the bill, record payment, free the slot."""
    method = (request.get_json(silent=True) or {}).get("method", "upi")
    if method not in PAYMENT_METHODS:
        return error("method must be upi, card, cash or wallet")
    conn = db()
    conn.begin()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT b.slot_id, p.price_per_hour,
                                  TIMESTAMPDIFF(MINUTE, b.start_time, NOW()) AS minutes
                           FROM bookings b
                           JOIN slots s ON s.slot_id = b.slot_id
                           JOIN lot_pricing p ON p.lot_id = s.lot_id AND p.vehicle_type = b.vehicle_type
                           WHERE b.booking_id=%s AND b.status='active' FOR UPDATE""", (booking_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return error("Active booking not found", 404)
            hours = max(1, math.ceil(row["minutes"] / 60))       # billed per started hour
            amount = hours * float(row["price_per_hour"])
            cur.execute("UPDATE bookings SET status='completed', end_time=NOW(), amount=%s "
                        "WHERE booking_id=%s", (amount, booking_id))
            cur.execute("INSERT INTO payments (booking_id, amount, method, paid_at) "
                        "VALUES (%s,%s,%s,NOW())", (booking_id, amount, method))
            cur.execute("UPDATE slots SET status='available' WHERE slot_id=%s", (row["slot_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return jsonify({"booking_id": booking_id, "hours_billed": hours, "amount": amount, "method": method})


# ----------------------------------------------------------- analytics API
@app.route("/api/analytics")
def api_analytics():
    """All numbers for the dashboard page (last 30 days unless stated)."""
    summary = query("""
        SELECT (SELECT COUNT(*) FROM parking_lots) AS total_lots,
               (SELECT COUNT(*) FROM slots) AS total_slots,
               (SELECT COUNT(*) FROM slots WHERE status='occupied') AS occupied_now,
               (SELECT COUNT(*) FROM bookings
                 WHERE status <> 'cancelled' AND start_time >= NOW() - INTERVAL 30 DAY) AS bookings_30d,
               (SELECT COALESCE(SUM(amount),0) FROM payments
                 WHERE paid_at >= NOW() - INTERVAL 30 DAY) AS revenue_30d,
               (SELECT COALESCE(SUM(amount),0) FROM payments WHERE DATE(paid_at) = CURDATE()) AS revenue_today,
               (SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 1) FROM bookings
                 WHERE status='completed' AND start_time >= NOW() - INTERVAL 30 DAY) AS avg_hours
    """)[0]

    peak_hours = query("""
        SELECT HOUR(start_time) AS hour, ROUND(COUNT(*) / COUNT(DISTINCT DATE(start_time)), 1) AS avg_bookings
        FROM bookings
        WHERE status <> 'cancelled' AND start_time >= NOW() - INTERVAL 30 DAY
        GROUP BY HOUR(start_time) ORDER BY hour""")

    weekdays = query("""
        SELECT DAYNAME(start_time) AS day, WEEKDAY(start_time) AS day_no,
               ROUND(COUNT(*) / COUNT(DISTINCT DATE(start_time))) AS avg_bookings
        FROM bookings
        WHERE status <> 'cancelled' AND start_time >= CURDATE() - INTERVAL 28 DAY AND start_time < CURDATE()
        GROUP BY DAYNAME(start_time), WEEKDAY(start_time) ORDER BY day_no""")

    # Daily revenue with a 7-day moving average (window function)
    revenue_trend = query("""
        SELECT day, revenue, ROUND(AVG(revenue) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)) AS avg_7d
        FROM (SELECT DATE(paid_at) AS day, SUM(amount) AS revenue
              FROM payments
              WHERE paid_at >= CURDATE() - INTERVAL 36 DAY AND DATE(paid_at) < CURDATE()
              GROUP BY DATE(paid_at)) d
        ORDER BY day""")[-30:]

    revenue_by_lot = query("""
        SELECT l.name AS lot, a.name AS area, SUM(pay.amount) AS revenue
        FROM payments pay
        JOIN bookings b     ON b.booking_id = pay.booking_id
        JOIN slots s        ON s.slot_id = b.slot_id
        JOIN parking_lots l ON l.lot_id = s.lot_id
        JOIN areas a        ON a.area_id = l.area_id
        WHERE pay.paid_at >= NOW() - INTERVAL 30 DAY
        GROUP BY l.lot_id, a.name, l.name ORDER BY revenue DESC LIMIT 10""")

    occupancy = query("""
        SELECT l.name AS lot, a.name AS area,
               ROUND(100 * SUM(s.status='occupied') / COUNT(*), 1) AS occupancy_pct,
               SUM(s.status='occupied') AS occupied, COUNT(*) AS total
        FROM slots s
        JOIN parking_lots l ON l.lot_id = s.lot_id
        JOIN areas a        ON a.area_id = l.area_id
        GROUP BY l.lot_id, a.name, l.name ORDER BY occupancy_pct DESC LIMIT 10""")

    vehicle_mix = query("""
        SELECT vehicle_type, COUNT(*) AS bookings
        FROM bookings WHERE status <> 'cancelled' AND start_time >= NOW() - INTERVAL 30 DAY
        GROUP BY vehicle_type ORDER BY FIELD(vehicle_type, 'car', 'bike', 'ev')""")

    payment_methods = query("""
        SELECT method, COUNT(*) AS payments, SUM(amount) AS revenue
        FROM payments WHERE paid_at >= NOW() - INTERVAL 30 DAY
        GROUP BY method ORDER BY FIELD(method, 'upi', 'card', 'cash', 'wallet')""")

    return jsonify({"summary": summary, "peak_hours": peak_hours, "weekdays": weekdays,
                    "revenue_trend": revenue_trend, "revenue_by_lot": revenue_by_lot,
                    "occupancy": occupancy, "vehicle_mix": vehicle_mix,
                    "payment_methods": payment_methods})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
