-- Smart Car Parking Management System
-- Data analysis queries (MySQL 8+ / MariaDB 10.4+)
-- Run after setup_db.py. Each query answers one business question.

USE smart_parking;

-- Q1. How many slots does each lot have, and how many are free right now?
--     (JOIN + GROUP BY + conditional aggregation)
SELECT l.name AS lot, a.name AS area,
       COUNT(*)                     AS total_slots,
       SUM(s.status = 'available')  AS free_slots,
       ROUND(100 * SUM(s.status = 'occupied') / COUNT(*), 1) AS occupancy_pct
FROM slots s
JOIN parking_lots l ON l.lot_id = s.lot_id
JOIN areas a        ON a.area_id = l.area_id
GROUP BY l.lot_id, l.name, a.name
ORDER BY occupancy_pct DESC;

-- Q2. Which hours of the day are the busiest? (peak hours)
SELECT HOUR(start_time) AS hour_of_day, COUNT(*) AS bookings
FROM bookings
WHERE status <> 'cancelled'
GROUP BY HOUR(start_time)
ORDER BY bookings DESC;

-- Q3. Which lots earn the most money, and what share of total revenue is that?
--     (window function: SUM() OVER ())
SELECT l.name AS lot,
       SUM(p.amount) AS revenue,
       ROUND(100 * SUM(p.amount) / SUM(SUM(p.amount)) OVER (), 1) AS pct_of_total
FROM payments p
JOIN bookings b     ON b.booking_id = p.booking_id
JOIN slots s        ON s.slot_id = b.slot_id
JOIN parking_lots l ON l.lot_id = s.lot_id
GROUP BY l.lot_id, l.name
ORDER BY revenue DESC;

-- Q4. Rank the lots inside each area by revenue.
--     (window function: RANK() OVER (PARTITION BY ...))
SELECT a.name AS area, l.name AS lot, SUM(p.amount) AS revenue,
       RANK() OVER (PARTITION BY a.area_id ORDER BY SUM(p.amount) DESC) AS rank_in_area
FROM payments p
JOIN bookings b     ON b.booking_id = p.booking_id
JOIN slots s        ON s.slot_id = b.slot_id
JOIN parking_lots l ON l.lot_id = s.lot_id
JOIN areas a        ON a.area_id = l.area_id
GROUP BY a.area_id, a.name, l.lot_id, l.name
ORDER BY area, rank_in_area;

-- Q5. Daily revenue, 7-day moving average and running total.
--     (CTE + window frames)
WITH daily AS (
    SELECT DATE(paid_at) AS day, SUM(amount) AS revenue
    FROM payments
    GROUP BY DATE(paid_at)
)
SELECT day, revenue,
       ROUND(AVG(revenue) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)) AS moving_avg_7d,
       SUM(revenue) OVER (ORDER BY day) AS running_total
FROM daily
ORDER BY day;

-- Q6. Is revenue growing? Compare each week with the week before.
--     (LAG window function)
WITH weekly AS (
    SELECT YEARWEEK(paid_at, 1) AS year_week, MIN(DATE(paid_at)) AS week_start, SUM(amount) AS revenue
    FROM payments
    GROUP BY YEARWEEK(paid_at, 1)
)
SELECT week_start, revenue,
       LAG(revenue) OVER (ORDER BY year_week) AS previous_week,
       ROUND(100 * (revenue - LAG(revenue) OVER (ORDER BY year_week))
                 / LAG(revenue) OVER (ORDER BY year_week), 1) AS growth_pct
FROM weekly
ORDER BY year_week;

-- Q7. Weekday vs weekend: bookings and average bill.
SELECT CASE WHEN WEEKDAY(start_time) >= 5 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
       COUNT(DISTINCT DATE(start_time))                              AS days,
       ROUND(COUNT(*) / COUNT(DISTINCT DATE(start_time)))            AS bookings_per_day,
       ROUND(AVG(amount), 2)                                         AS avg_bill
FROM bookings
WHERE status = 'completed'
GROUP BY day_type;

-- Q8. How long do people park, by vehicle type?
SELECT vehicle_type,
       COUNT(*) AS bookings,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) / 60, 2) AS avg_hours,
       ROUND(AVG(amount), 2) AS avg_bill
FROM bookings
WHERE status = 'completed'
GROUP BY vehicle_type;

-- Q9. Which payment method is used most?
SELECT method, COUNT(*) AS payments, SUM(amount) AS revenue,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM payments), 1) AS pct_of_payments
FROM payments
GROUP BY method
ORDER BY payments DESC;

-- Q10. Lots that earn more than the average lot. (subquery in HAVING)
SELECT l.name AS lot, SUM(p.amount) AS revenue
FROM payments p
JOIN bookings b     ON b.booking_id = p.booking_id
JOIN slots s        ON s.slot_id = b.slot_id
JOIN parking_lots l ON l.lot_id = s.lot_id
GROUP BY l.lot_id, l.name
HAVING SUM(p.amount) > (
    SELECT AVG(lot_revenue) FROM (
        SELECT SUM(p2.amount) AS lot_revenue
        FROM payments p2
        JOIN bookings b2 ON b2.booking_id = p2.booking_id
        JOIN slots s2    ON s2.slot_id = b2.slot_id
        GROUP BY s2.lot_id
    ) t
)
ORDER BY revenue DESC;

-- Q11. Revenue earned per slot: which lots use their space best?
SELECT l.name AS lot, COUNT(DISTINCT s.slot_id) AS slots,
       ROUND(SUM(p.amount) / COUNT(DISTINCT s.slot_id)) AS revenue_per_slot
FROM slots s
JOIN parking_lots l  ON l.lot_id = s.lot_id
LEFT JOIN bookings b ON b.slot_id = s.slot_id AND b.status = 'completed'
LEFT JOIN payments p ON p.booking_id = b.booking_id
GROUP BY l.lot_id, l.name
ORDER BY revenue_per_slot DESC;

-- Q12. Cancellation rate by area.
SELECT a.name AS area,
       COUNT(*) AS bookings,
       SUM(b.status = 'cancelled') AS cancelled,
       ROUND(100 * SUM(b.status = 'cancelled') / COUNT(*), 2) AS cancel_pct
FROM bookings b
JOIN slots s        ON s.slot_id = b.slot_id
JOIN parking_lots l ON l.lot_id = s.lot_id
JOIN areas a        ON a.area_id = l.area_id
GROUP BY a.area_id, a.name
ORDER BY cancel_pct DESC;

-- Q13. Find the 5 nearest lots with a free car slot to a point
--      (here: Andheri station, 19.1197, 72.8464) using the Haversine formula.
SELECT l.name AS lot, p.price_per_hour, v.available_slots,
       ROUND(6371 * 2 * ASIN(SQRT(
           POWER(SIN(RADIANS(l.latitude - 19.1197) / 2), 2) +
           COS(RADIANS(19.1197)) * COS(RADIANS(l.latitude)) *
           POWER(SIN(RADIANS(l.longitude - 72.8464) / 2), 2))), 2) AS distance_km
FROM parking_lots l
JOIN lot_pricing p        ON p.lot_id = l.lot_id AND p.vehicle_type = 'car'
JOIN v_lot_availability v ON v.lot_id = l.lot_id AND v.vehicle_type = 'car'
WHERE v.available_slots > 0
ORDER BY distance_km
LIMIT 5;
