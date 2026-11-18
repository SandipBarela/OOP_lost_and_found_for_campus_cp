-- ==============================================================================
-- CAMPUS LOST & FOUND PORTAL - SUPABASE DATABASE SCHEMA
-- Project URL: https://kwbnyltlonlakyfyluzl.supabase.co
-- Features:
--   1. Separate 'lost_items' and 'found_items' tables
--   2. Unified 'items' view with INSTEAD OF triggers (keeps app.py working with 0 changes!)
--   3. 20+ Campus Users pre-seeded
--   4. Storage bucket 'item-images' with full access policies
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. USERS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    phone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 2. DROP OLD ITEMS TABLE / VIEW IF EXISTS
-- ------------------------------------------------------------------------------
DROP VIEW IF EXISTS public.items CASCADE;
DROP TABLE IF EXISTS public.items CASCADE;

-- Shared sequence for globally unique IDs across lost_items and found_items
CREATE SEQUENCE IF NOT EXISTS public.items_id_seq START WITH 1;

-- ------------------------------------------------------------------------------
-- 3. LOST ITEMS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.lost_items (
    id BIGINT PRIMARY KEY DEFAULT nextval('public.items_id_seq'),
    title TEXT NOT NULL,
    description TEXT,
    location TEXT NOT NULL,
    reported_by TEXT NOT NULL REFERENCES public.users(email) ON UPDATE CASCADE ON DELETE CASCADE,
    image_url TEXT,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Claimed', 'Resolved')),
    claimed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 4. FOUND ITEMS TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.found_items (
    id BIGINT PRIMARY KEY DEFAULT nextval('public.items_id_seq'),
    title TEXT NOT NULL,
    description TEXT,
    location TEXT NOT NULL,
    reported_by TEXT NOT NULL REFERENCES public.users(email) ON UPDATE CASCADE ON DELETE CASCADE,
    image_url TEXT,
    status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Claimed', 'Resolved')),
    claimed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 5. UNIFIED 'items' VIEW WITH INSTEAD OF TRIGGERS
-- Allows app.py to continue querying and inserting without any code breakage!
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.items AS
SELECT 
    id, title, description, location, 
    'Lost'::TEXT AS item_type, 
    reported_by, image_url, status, claimed_by, created_at, updated_at
FROM public.lost_items
UNION ALL
SELECT 
    id, title, description, location, 
    'Found'::TEXT AS item_type, 
    reported_by, image_url, status, claimed_by, created_at, updated_at
FROM public.found_items;

-- INSTEAD OF INSERT TRIGGER (routes into lost_items or found_items)
CREATE OR REPLACE FUNCTION public.insert_items_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.item_type = 'Found' THEN
        INSERT INTO public.found_items (title, description, location, reported_by, image_url, status, claimed_by)
        VALUES (NEW.title, NEW.description, NEW.location, NEW.reported_by, NEW.image_url, COALESCE(NEW.status, 'Open'), NEW.claimed_by)
        RETURNING id, title, description, location, 'Found'::TEXT, reported_by, image_url, status, claimed_by, created_at, updated_at
        INTO NEW.id, NEW.title, NEW.description, NEW.location, NEW.item_type, NEW.reported_by, NEW.image_url, NEW.status, NEW.claimed_by, NEW.created_at, NEW.updated_at;
    ELSE
        INSERT INTO public.lost_items (title, description, location, reported_by, image_url, status, claimed_by)
        VALUES (NEW.title, NEW.description, NEW.location, NEW.reported_by, NEW.image_url, COALESCE(NEW.status, 'Open'), NEW.claimed_by)
        RETURNING id, title, description, location, 'Lost'::TEXT, reported_by, image_url, status, claimed_by, created_at, updated_at
        INTO NEW.id, NEW.title, NEW.description, NEW.location, NEW.item_type, NEW.reported_by, NEW.image_url, NEW.status, NEW.claimed_by, NEW.created_at, NEW.updated_at;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS items_insert_trg ON public.items;
CREATE TRIGGER items_insert_trg
INSTEAD OF INSERT ON public.items
FOR EACH ROW
EXECUTE FUNCTION public.insert_items_trigger();

-- INSTEAD OF UPDATE TRIGGER (updates corresponding row in lost_items or found_items)
CREATE OR REPLACE FUNCTION public.update_items_trigger()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.lost_items
    SET status = NEW.status,
        claimed_by = NEW.claimed_by,
        title = NEW.title,
        description = NEW.description,
        location = NEW.location,
        image_url = NEW.image_url,
        updated_at = now()
    WHERE id = OLD.id;

    UPDATE public.found_items
    SET status = NEW.status,
        claimed_by = NEW.claimed_by,
        title = NEW.title,
        description = NEW.description,
        location = NEW.location,
        image_url = NEW.image_url,
        updated_at = now()
    WHERE id = OLD.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS items_update_trg ON public.items;
CREATE TRIGGER items_update_trg
INSTEAD OF UPDATE ON public.items
FOR EACH ROW
EXECUTE FUNCTION public.update_items_trigger();

-- INSTEAD OF DELETE TRIGGER (deletes from lost_items or found_items)
CREATE OR REPLACE FUNCTION public.delete_items_trigger()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM public.lost_items WHERE id = OLD.id;
    DELETE FROM public.found_items WHERE id = OLD.id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS items_delete_trg ON public.items;
CREATE TRIGGER items_delete_trg
INSTEAD OF DELETE ON public.items
FOR EACH ROW
EXECUTE FUNCTION public.delete_items_trigger();

-- ------------------------------------------------------------------------------
-- 6. PERMISSIONS & RLS SETTINGS (Enables seamless API read/write)
-- ------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON ROUTINES TO anon, authenticated, service_role;

ALTER TABLE IF EXISTS public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.lost_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.found_items DISABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- 7. SUPABASE STORAGE BUCKET FOR IMAGES
-- ------------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('item-images', 'item-images', true)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Public Access" ON storage.objects;
CREATE POLICY "Public Access" ON storage.objects FOR SELECT USING (bucket_id = 'item-images');

DROP POLICY IF EXISTS "Allow Uploads" ON storage.objects;
CREATE POLICY "Allow Uploads" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'item-images');

DROP POLICY IF EXISTS "Allow Updates" ON storage.objects;
CREATE POLICY "Allow Updates" ON storage.objects FOR UPDATE USING (bucket_id = 'item-images');

-- ------------------------------------------------------------------------------
-- 8. SEED DATA: 22 CAMPUS USERS
-- ------------------------------------------------------------------------------
INSERT INTO public.users (email, password, name, role) VALUES
    ('admin@campus.edu', 'admin123', 'Campus Admin', 'admin'),
    ('security.admin@campus.edu', 'secpass123', 'Security Helpdesk', 'admin'),
    ('library.admin@campus.edu', 'libpass123', 'Library Desk Admin', 'admin'),
    ('student1@campus.edu', 'pass123', 'Aarav Sharma', 'user'),
    ('student2@campus.edu', 'pass123', 'Diya Patel', 'user'),
    ('rohit.verma@campus.edu', 'pass123', 'Rohit Verma', 'user'),
    ('ananya.singh@campus.edu', 'pass123', 'Ananya Singh', 'user'),
    ('priya.nair@campus.edu', 'pass123', 'Priya Nair', 'user'),
    ('rahul.mehta@campus.edu', 'pass123', 'Rahul Mehta', 'user'),
    ('sneha.kulkarni@campus.edu', 'pass123', 'Sneha Kulkarni', 'user'),
    ('vikram.aditya@campus.edu', 'pass123', 'Vikram Aditya', 'user'),
    ('pooja.deshmukh@campus.edu', 'pass123', 'Pooja Deshmukh', 'user'),
    ('amit.kumar@campus.edu', 'pass123', 'Amit Kumar', 'user'),
    ('neha.gupta@campus.edu', 'pass123', 'Neha Gupta', 'user'),
    ('karan.johal@campus.edu', 'pass123', 'Karan Johal', 'user'),
    ('riya.sen@campus.edu', 'pass123', 'Riya Sen', 'user'),
    ('siddharth.rao@campus.edu', 'pass123', 'Siddharth Rao', 'user'),
    ('tanvi.joshi@campus.edu', 'pass123', 'Tanvi Joshi', 'user'),
    ('arjun.reddy@campus.edu', 'pass123', 'Arjun Reddy', 'user'),
    ('kavya.iyer@campus.edu', 'pass123', 'Kavya Iyer', 'user'),
    ('manish.tiwari@campus.edu', 'pass123', 'Manish Tiwari', 'user'),
    ('ishita.bose@campus.edu', 'pass123', 'Ishita Bose', 'user')
ON CONFLICT (email) DO NOTHING;

-- ------------------------------------------------------------------------------
-- 9. SEED SAMPLE LOST AND FOUND ITEMS
-- ------------------------------------------------------------------------------
INSERT INTO public.lost_items (title, description, location, reported_by, status) VALUES
    ('Blue Water Bottle', 'Steel bottle with anime sticker', 'Library 2nd Floor', 'student1@campus.edu', 'Open'),
    ('Black Wallet', 'Leather wallet with ID card', 'Sports Complex Cafeteria', 'rohit.verma@campus.edu', 'Open');

INSERT INTO public.found_items (title, description, location, reported_by, status) VALUES
    ('Scientific Calculator', 'Casio fx-991EX with cover', 'Lab 304', 'student2@campus.edu', 'Open'),
    ('Keys Keychain', 'Two brass keys with red lanyard', 'Auditorium Gate 2', 'ananya.singh@campus.edu', 'Open');
