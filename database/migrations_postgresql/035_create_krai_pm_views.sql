-- Migration 033: Create views for krai_pm schema
-- Purpose: Provide consistent public interface to PM schema tables via vw_ prefix.
-- Created: 2026-05-19

CREATE OR REPLACE VIEW public.vw_service_tickets AS
  SELECT * FROM krai_pm.service_tickets;

CREATE OR REPLACE VIEW public.vw_part_lifetimes AS
  SELECT * FROM krai_pm.part_lifetimes;

CREATE OR REPLACE VIEW public.vw_device_lifecycle AS
  SELECT * FROM krai_pm.device_lifecycle;

CREATE OR REPLACE VIEW public.vw_predictions AS
  SELECT * FROM krai_pm.predictions;
