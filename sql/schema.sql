-- Smart Car Parking Management System
-- Database schema (MySQL 8+ / MariaDB 10.4+)
-- Run with:  python setup_db.py   (this also loads the sample data)

CREATE DATABASE IF NOT EXISTS smart_parking;
USE smart_parking;

DROP VIEW IF EXISTS v_lot_availability;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS slots;
DROP TABLE IF EXISTS lot_pricing;
DROP TABLE IF EXISTS parking_lots;
DROP TABLE IF EXISTS areas;

-- 1. Areas of the city (Andheri, Bandra, ...)
CREATE TABLE areas (
    area_id   INT AUTO_INCREMENT PRIMARY KEY,
    name      VARCHAR(60) NOT NULL UNIQUE,
    latitude  DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL
);

-- 2. Parking lots, each with a map location
CREATE TABLE parking_lots (
    lot_id      INT AUTO_INCREMENT PRIMARY KEY,
    area_id     INT NOT NULL,
    name        VARCHAR(100) NOT NULL,
    address     VARCHAR(200) NOT NULL,
    latitude    DECIMAL(9,6) NOT NULL,
    longitude   DECIMAL(9,6) NOT NULL,
    open_time   TIME NOT NULL DEFAULT '00:00:00',
    close_time  TIME NOT NULL DEFAULT '23:59:00',
    is_covered  BOOLEAN NOT NULL DEFAULT FALSE,
    has_cctv    BOOLEAN NOT NULL DEFAULT FALSE,
    has_ev_charging BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (area_id) REFERENCES areas(area_id),
    INDEX idx_lot_location (latitude, longitude)
);

-- 3. Price per hour for each vehicle type in each lot
CREATE TABLE lot_pricing (
    lot_id         INT NOT NULL,
    vehicle_type   ENUM('car','bike','ev') NOT NULL,
    price_per_hour DECIMAL(6,2) NOT NULL CHECK (price_per_hour >= 0),
    PRIMARY KEY (lot_id, vehicle_type),
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id) ON DELETE CASCADE
);

-- 4. Individual parking slots
CREATE TABLE slots (
    slot_id      INT AUTO_INCREMENT PRIMARY KEY,
    lot_id       INT NOT NULL,
    slot_code    VARCHAR(10) NOT NULL,
    vehicle_type ENUM('car','bike','ev') NOT NULL,
    status       ENUM('available','occupied','maintenance') NOT NULL DEFAULT 'available',
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id) ON DELETE CASCADE,
    UNIQUE KEY uq_slot_code (lot_id, slot_code),
    INDEX idx_slot_lookup (lot_id, vehicle_type, status)
);

-- 5. Bookings (one row each time a vehicle parks)
CREATE TABLE bookings (
    booking_id     INT AUTO_INCREMENT PRIMARY KEY,
    slot_id        INT NOT NULL,
    customer_name  VARCHAR(80) NOT NULL,
    vehicle_number VARCHAR(15) NOT NULL,
    vehicle_type   ENUM('car','bike','ev') NOT NULL,
    start_time     DATETIME NOT NULL,
    expected_hours INT NOT NULL,
    end_time       DATETIME NULL,
    amount         DECIMAL(8,2) NULL,
    status         ENUM('active','completed','cancelled') NOT NULL DEFAULT 'active',
    FOREIGN KEY (slot_id) REFERENCES slots(slot_id),
    INDEX idx_booking_start (start_time),
    INDEX idx_booking_vehicle (vehicle_number),
    INDEX idx_booking_status (status)
);

-- 6. Payments (made at checkout)
CREATE TABLE payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    amount     DECIMAL(8,2) NOT NULL,
    method     ENUM('upi','card','cash','wallet') NOT NULL,
    paid_at    DATETIME NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
);

-- View: live availability of every lot by vehicle type
CREATE VIEW v_lot_availability AS
SELECT
    s.lot_id,
    s.vehicle_type,
    COUNT(*)                        AS total_slots,
    SUM(s.status = 'available')     AS available_slots,
    SUM(s.status = 'occupied')      AS occupied_slots
FROM slots s
GROUP BY s.lot_id, s.vehicle_type;
