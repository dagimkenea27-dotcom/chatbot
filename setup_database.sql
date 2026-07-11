-- ============================================================
-- GojoShop.et — Database Setup
-- Run this in XAMPP phpMyAdmin or MySQL CLI:
--   mysql -u root -p < setup_database.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS gojoshop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gojoshop;

-- -------------------------------------------------------
-- Orders table
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_id        VARCHAR(20)  NOT NULL UNIQUE,   -- e.g. ORD-1001
    customer_name   VARCHAR(100) NOT NULL,
    customer_phone  VARCHAR(20),
    customer_email  VARCHAR(100),
    status          ENUM('pending','processing','shipped','delivered','cancelled') DEFAULT 'pending',
    total_amount    DECIMAL(10,2) NOT NULL,
    payment_method  VARCHAR(50)  DEFAULT 'Cash on Delivery',
    payment_status  ENUM('paid','unpaid','refunded') DEFAULT 'unpaid',
    delivery_address TEXT,
    tracking_number VARCHAR(50),
    notes           TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- -------------------------------------------------------
-- Order items table
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_id        VARCHAR(20)  NOT NULL,
    product_name    VARCHAR(150) NOT NULL,
    quantity        INT          NOT NULL DEFAULT 1,
    unit_price      DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- -------------------------------------------------------
-- Seed data — 6 sample orders across all statuses
-- -------------------------------------------------------
INSERT IGNORE INTO orders
    (order_id, customer_name, customer_phone, customer_email, status, total_amount, payment_method, payment_status, delivery_address, tracking_number)
VALUES
    ('ORD-1001', 'Abebe Girma',    '+251911001001', 'abebe@email.com',   'delivered',   4500.00,  'Telebirr',        'paid',   'Bole, Addis Ababa',             'TRK-88210'),
    ('ORD-1002', 'Sara Tesfaye',   '+251922002002', 'sara@email.com',    'shipped',     12800.00, 'Amole',           'paid',   'Kazanchis, Addis Ababa',        'TRK-88211'),
    ('ORD-1003', 'Mekdes Alemu',   '+251933003003', 'mekdes@email.com',  'processing',  2300.00,  'Cash on Delivery','unpaid', 'Piassa, Addis Ababa',           NULL),
    ('ORD-1004', 'Dawit Haile',    '+251944004004', 'dawit@email.com',   'pending',     8750.00,  'Credit Card',     'paid',   'Megenagna, Addis Ababa',        NULL),
    ('ORD-1005', 'Hana Bekele',    '+251955005005', 'hana@email.com',    'cancelled',   3200.00,  'Telebirr',        'refunded','Sarbet, Addis Ababa',          NULL),
    ('ORD-1006', 'Yonas Tadesse',  '+251966006006', 'yonas@email.com',   'shipped',     19500.00, 'Amole',           'paid',   'CMC, Addis Ababa',              'TRK-88215');

INSERT IGNORE INTO order_items (order_id, product_name, quantity, unit_price) VALUES
    ('ORD-1001', 'Samsung Galaxy S24',   1, 3500.00),
    ('ORD-1001', 'Phone Case',           2,  250.00),
    ('ORD-1001', 'Charger',              1,  500.00),

    ('ORD-1002', 'MacBook Pro 14"',      1,12000.00),
    ('ORD-1002', 'Laptop Bag',           1,  800.00),

    ('ORD-1003', 'Men\'s Jacket',        1, 1800.00),
    ('ORD-1003', 'T-Shirt',             2,  250.00),

    ('ORD-1004', 'AirPods Pro',          1, 6500.00),
    ('ORD-1004', 'iPhone 15 Case',       2,  500.00),
    ('ORD-1004', 'Lightning Cable',      1,  750.00),

    ('ORD-1005', 'Women\'s Dress',       2, 1600.00),

    ('ORD-1006', 'MacBook Pro 16"',      1,18000.00),
    ('ORD-1006', 'USB-C Hub',            1,  800.00),
    ('ORD-1006', 'Screen Protector',     1,  700.00);

SELECT CONCAT('Setup complete! Orders: ', COUNT(*)) AS result FROM orders;
