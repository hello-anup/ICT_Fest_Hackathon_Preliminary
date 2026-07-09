# Bug Report - CoWork Multi-Tenant Coworking Space Booking API

## Overview

This report documents the bugs identified and fixed during the IUT 12th
ICT Fest Bdapps Agentic AI Hackathon preliminary round.

## Fixed Issues

### 1. Refresh Token Reuse Vulnerability

Files: - app/auth.py - app/routers/auth.py

Problem: Refresh tokens could be reused after successful refresh.

Fix: Implemented single-use refresh token rotation and invalidation.

------------------------------------------------------------------------

### 2. JWT Security Improvements

File: - app/auth.py

Fixes: - Access token expiry fixed to exactly 900 seconds. - Refresh
token expiry fixed to 7 days. - Added token type validation. - Added
revoked access token checking.

------------------------------------------------------------------------

### 3. Booking Conflict Logic

File: - app/routers/bookings.py

Problem: Incorrect overlap detection rejected valid back-to-back
bookings.

Fix:

existing.start_time \< new.end_time and new.start_time \<
existing.end_time

------------------------------------------------------------------------

### 4. Refund Calculation Precision

File: - app/services/refunds.py

Problem: Floating point conversion caused possible cent precision
errors.

Fix: Refund calculations now preserve integer cents.

------------------------------------------------------------------------

### 5. Room Statistics Consistency

Files: - app/services/stats.py - app/routers/rooms.py

Problem: In-memory statistics could become inconsistent.

Fix: Statistics now reflect database booking state.

------------------------------------------------------------------------

### 6. Multi-Tenant Security

File: - app/routers/rooms.py

Problem: Cross organization resource access protection needed
improvement.

Fix: All room queries verify organization ownership.

------------------------------------------------------------------------

### 7. Admin Report Validation

File: - app/routers/admin.py

Problem: Invalid date ranges were accepted.

Fix: Added date range validation returning INVALID_BOOKING_WINDOW.

------------------------------------------------------------------------

### 8. Booking Reference Uniqueness

File: - app/models.py

Problem: Duplicate booking reference codes were possible.

Fix: Added database uniqueness constraint.

------------------------------------------------------------------------

# Testing

Command:

python -m pytest -v

Result:

5 passed

Tests covered: - Refresh token single use - Logout token revocation -
Room statistics - Admin date validation - Cross organization access

------------------------------------------------------------------------

# Final Status

All identified API contract violations were fixed while preserving: -
Existing endpoints - Response formats - Authentication workflow -
Multi-tenant isolation - Booking rules

The project passes automated validation successfully.
