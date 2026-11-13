"""Creates the database, tables and sample data.

Run once:  python setup_db.py

All parking lots, prices and bookings here are SAMPLE DATA made for this
project. Lot names are invented; only the Mumbai area names are real.
"""
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pymysql

import config

random.seed(42)  # same sample data every time
HISTORY_DAYS = 60

# (area, latitude, longitude)
AREAS = [
    ("Andheri West", 19.1364, 72.8296), ("Andheri East", 19.1155, 72.8727),
    ("Bandra West", 19.0596, 72.8295), ("Bandra Kurla Complex", 19.0674, 72.8686),
    ("Juhu", 19.1075, 72.8263), ("Powai", 19.1176, 72.9060),
    ("Dadar", 19.0178, 72.8478), ("Lower Parel", 18.9980, 72.8302),
    ("Worli", 19.0170, 72.8170), ("Colaba", 18.9067, 72.8147),
    ("Fort", 18.9340, 72.8356), ("Borivali", 19.2307, 72.8567),
    ("Malad", 19.1860, 72.8485), ("Goregaon", 19.1663, 72.8526),
    ("Ghatkopar", 19.0860, 72.9081), ("Kurla", 19.0726, 72.8845),
    ("Chembur", 19.0522, 72.9005), ("Vile Parle", 19.0996, 72.8440),
]

# (area, lot name, address, car price, bike price, covered, cctv, ev, popularity)
LOTS = [
    ("Andheri West", "Metro Station Parking", "Near Metro Station, J P Road", 40, 15, 1, 1, 1, 1.3),
    ("Andheri West", "Link Road Plaza Parking", "New Link Road", 50, 20, 1, 1, 0, 1.1),
    ("Andheri West", "Lokhandwala Market Parking", "Lokhandwala Complex", 60, 20, 0, 1, 0, 1.2),
    ("Andheri East", "Station East Parking", "Near Railway Station, East side", 30, 10, 0, 1, 0, 1.2),
    ("Andheri East", "Business Park Parking", "Andheri Kurla Road, Marol", 50, 20, 1, 1, 1, 1.0),
    ("Bandra West", "Linking Road Parking", "Linking Road", 80, 30, 0, 1, 0, 1.4),
    ("Bandra West", "Bandstand Sea View Parking", "Bandstand Promenade", 70, 25, 0, 0, 0, 0.9),
    ("Bandra Kurla Complex", "BKC Tower Basement Parking", "G Block, BKC", 100, 40, 1, 1, 1, 1.3),
    ("Bandra Kurla Complex", "BKC Open Ground Parking", "E Block, BKC", 60, 20, 0, 1, 0, 1.0),
    ("Juhu", "Juhu Beach Parking", "Juhu Tara Road", 60, 20, 0, 0, 0, 1.1),
    ("Powai", "Lakeside Mall Parking", "Central Avenue, Hiranandani", 50, 20, 1, 1, 1, 1.1),
    ("Dadar", "Dadar Market Parking", "Near Flower Market", 40, 15, 0, 1, 0, 1.2),
    ("Lower Parel", "Mill Compound Parking", "Senapati Bapat Marg", 90, 30, 1, 1, 1, 1.2),
    ("Worli", "Sea Face Parking", "Worli Sea Face", 70, 25, 0, 1, 0, 0.9),
    ("Colaba", "Causeway Parking", "Colaba Causeway", 80, 30, 0, 1, 0, 1.0),
    ("Fort", "Heritage Square Parking", "Near Horniman Circle", 70, 25, 1, 1, 0, 1.1),
    ("Borivali", "National Park Gate Parking", "Western Express Highway", 30, 10, 0, 0, 0, 0.8),
    ("Malad", "Mindspace Parking", "Link Road, Mindspace", 40, 15, 1, 1, 1, 1.0),
    ("Goregaon", "Film City Road Parking", "Film City Road", 30, 10, 0, 1, 0, 0.8),
    ("Ghatkopar", "Metro Mall Parking", "LBS Marg", 40, 15, 1, 1, 0, 1.1),
    ("Kurla", "Terminus Parking", "Near Lokmanya Tilak Terminus", 30, 10, 0, 1, 0, 1.0),
    ("Chembur", "Diamond Garden Parking", "Diamond Garden Road", 30, 10, 0, 0, 0, 0.8),
    ("Vile Parle", "Airport Road Parking", "Near Domestic Airport", 90, 30, 1, 1, 1, 1.2),
]

# How busy each hour of the day is (0 = midnight ... 23 = 11 pm)
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 7, 10, 12, 11, 9, 9, 8, 7, 7, 8, 10, 12, 12, 9, 6, 4, 2]
FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Riya", "Ananya", "Ishaan", "Kavya", "Rohan",
               "Sneha", "Arjun", "Priya", "Neha", "Kunal", "Meera", "Siddharth", "Tanvi",
               "Omkar", "Pooja", "Rahul", "Sakshi", "Yash", "Diya", "Nikhil", "Aditi"]
LAST_NAMES = ["Patil", "Shah", "Mehta", "Joshi", "Desai", "Kulkarni", "Nair", "Iyer",
              "Sharma", "Gupta", "Fernandes", "Pawar", "Rao", "Khan", "Deshmukh", "Verma"]


def vehicle_number():
    return "MH%02d%s%04d" % (random.choice([1, 2, 3, 4, 43, 47]),
                             "".join(random.choices("ABCDEFGHJKLMNPRSTUVWXYZ", k=2)),
                             random.randint(1, 9999))


def run_schema(cur):
    sql = Path(__file__).with_name("sql").joinpath("schema.sql").read_text()
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    for statement in "\n".join(lines).split(";"):
        if statement.strip():
            cur.execute(statement)


def main():
    try:
        conn = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT,
                               user=config.DB_USER, password=config.DB_PASSWORD,
                               autocommit=False)
    except pymysql.err.OperationalError as err:
        print("Could not connect to MySQL:", err.args[-1])
        print("Check that MySQL is running and that DB_USER / DB_PASSWORD in config.py are correct.")
        return
    cur = conn.cursor()
    print("Creating tables...")
    run_schema(cur)

    # ---- areas -------------------------------------------------------------
    cur.executemany("INSERT INTO areas (name, latitude, longitude) VALUES (%s,%s,%s)", AREAS)
    cur.execute("SELECT name, area_id, latitude, longitude FROM areas")
    area = {name: (aid, float(lat), float(lng)) for name, aid, lat, lng in cur.fetchall()}

    # ---- lots, prices and slots ---------------------------------------------
    print("Adding parking lots and slots...")
    lots = []      # each: dict with id, prices, popularity and slot ids by type
    for a_name, name, address, car, bike, covered, cctv, ev, pop in LOTS:
        aid, alat, alng = area[a_name]
        lat = alat + random.uniform(-0.006, 0.006)   # spread lots around the area centre
        lng = alng + random.uniform(-0.006, 0.006)
        is_24h = random.random() < 0.5
        cur.execute(
            """INSERT INTO parking_lots (area_id, name, address, latitude, longitude,
                   open_time, close_time, is_covered, has_cctv, has_ev_charging)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (aid, name, f"{address}, {a_name}, Mumbai", round(lat, 6), round(lng, 6),
             "00:00:00" if is_24h else "06:00:00", "23:59:00" if is_24h else "23:00:00",
             covered, cctv, ev))
        lot_id = cur.lastrowid
        prices = {"car": car, "bike": bike}
        counts = {"car": random.randint(20, 60), "bike": random.randint(15, 40)}
        if ev:
            prices["ev"] = car + 20        # EV slots cost a little more (charging)
            counts["ev"] = random.randint(3, 8)
        cur.executemany("INSERT INTO lot_pricing VALUES (%s,%s,%s)",
                        [(lot_id, t, p) for t, p in prices.items()])
        slot_ids = {}
        for vtype, n in counts.items():
            slot_ids[vtype] = []
            for i in range(1, n + 1):
                cur.execute("INSERT INTO slots (lot_id, slot_code, vehicle_type) VALUES (%s,%s,%s)",
                            (lot_id, f"{vtype[0].upper()}-{i:03d}", vtype))
                slot_ids[vtype].append(cur.lastrowid)
        lots.append({"id": lot_id, "prices": prices, "pop": pop, "slots": slot_ids})

    # ---- booking history ----------------------------------------------------
    print(f"Generating {HISTORY_DAYS} days of booking history...")
    now = datetime.now().replace(microsecond=0)
    first_day = (now - timedelta(days=HISTORY_DAYS)).replace(hour=0, minute=0, second=0)
    busy_until = {}          # slot_id -> time the slot becomes free again
    bookings, payments, occupied = [], [], []
    booking_id = 0
    for d in range(HISTORY_DAYS + 1):
        day = first_day + timedelta(days=d)
        weekend = day.weekday() >= 5
        growth = 0.8 + 0.4 * d / HISTORY_DAYS          # usage slowly grows over time
        for lot in lots:
            for vtype, slot_list in lot["slots"].items():
                n = int(len(slot_list) * lot["pop"] * growth * (1.25 if weekend else 1.0)
                        * random.uniform(1.0, 1.5))
                starts = sorted(
                    day + timedelta(hours=random.choices(range(24), HOUR_WEIGHTS)[0],
                                    minutes=random.randint(0, 59))
                    for _ in range(n))
                for start in starts:
                    if start > now:
                        continue
                    free = [s for s in slot_list if busy_until.get(s, first_day) <= start]
                    if not free:
                        continue                         # lot was full at that time
                    slot = random.choice(free)
                    expected = random.choices([1, 2, 3, 4, 6, 8], [30, 30, 18, 12, 6, 4])[0]
                    minutes = max(20, int(expected * 60 * random.uniform(0.7, 1.2)))
                    end = start + timedelta(minutes=minutes)
                    booking_id += 1
                    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                    base = [booking_id, slot, name, vehicle_number(), vtype, start, expected]
                    if random.random() < 0.04:           # a few bookings get cancelled
                        bookings.append(base + [start + timedelta(minutes=5), None, "cancelled"])
                        continue
                    busy_until[slot] = end
                    if end > now:                        # still parked right now
                        bookings.append(base + [None, None, "active"])
                        occupied.append(slot)
                    else:
                        amount = math.ceil(minutes / 60) * lot["prices"][vtype]
                        bookings.append(base + [end, amount, "completed"])
                        method = random.choices(["upi", "card", "cash", "wallet"], [60, 20, 14, 6])[0]
                        payments.append((booking_id, amount, method, end))

    cur.executemany(
        """INSERT INTO bookings (booking_id, slot_id, customer_name, vehicle_number, vehicle_type,
               start_time, expected_hours, end_time, amount, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", bookings)
    cur.executemany("INSERT INTO payments (booking_id, amount, method, paid_at) VALUES (%s,%s,%s,%s)",
                    payments)
    if occupied:
        cur.executemany("UPDATE slots SET status='occupied' WHERE slot_id=%s", [(s,) for s in occupied])
    # a few slots are closed for maintenance
    cur.execute("UPDATE slots SET status='maintenance' WHERE status='available' AND slot_id % 97 = 0")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM parking_lots"); n_lots = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM slots"); n_slots = cur.fetchone()[0]
    print(f"Done: {n_lots} lots, {n_slots} slots, {len(bookings)} bookings, {len(payments)} payments.")
    print("Now run:  python app.py")
    conn.close()


if __name__ == "__main__":
    main()
