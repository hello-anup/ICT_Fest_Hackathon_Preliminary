# Bug Report - CoWork Multi-Tenant Coworking Space Booking API

## Project Overview

This document provides a detailed record of the bugs identified, root
causes, fixes, and validation performed for the CoWork Multi-Tenant
Coworking Space Booking API.

The main focus areas were:

-   Authentication security
-   JWT lifecycle management
-   Refresh token handling
-   Booking business rules
-   Room availability validation
-   Refund calculation
-   Multi-tenant organization isolation
-   Admin reporting
-   Database integrity
-   Automated API validation

All fixes were implemented while keeping the existing API structure and
expected behavior unchanged.

------------------------------------------------------------------------

# 1. JWT Access Token Expiry Calculation Issue

## File

    app/auth.py

## Problem

The access token lifetime calculation was incorrect.

The previous implementation applied incorrect time conversion, causing
the generated JWT expiration time to differ from the required API
specification.

The expected behavior:

    Access token lifetime = exactly 900 seconds

## Impact

Incorrect token expiration can cause:

-   Users staying authenticated longer than expected
-   Security policy violation
-   Authentication tests failing

## Root Cause

The token creation logic mixed minute-based and second-based
calculations.

## Fix Implemented

Updated JWT generation logic:

-   Access token lifetime fixed to 15 minutes
-   Refresh token lifetime fixed to 7 days
-   Added proper UTC timestamp handling

Example:

    Access Token:
    900 seconds

    Refresh Token:
    604800 seconds

------------------------------------------------------------------------

# 2. Refresh Token Replay Vulnerability

## Files

    app/auth.py
    app/routers/auth.py

## Problem

A refresh token could be used multiple times after a successful refresh
operation.

Example:

Request 1:

    POST /auth/refresh

    Response:
    200 OK

The same refresh token could again be sent:

    POST /auth/refresh

    Response:
    200 OK

This violated the requirement that refresh tokens must be single-use.

------------------------------------------------------------------------

## Impact

A leaked refresh token could continuously generate new access tokens.

Security risks:

-   Unauthorized session extension
-   Token replay attack
-   User session compromise

------------------------------------------------------------------------

## Root Cause

The system generated new tokens but did not maintain refresh token usage
state.

------------------------------------------------------------------------

## Fix Implemented

Added refresh token tracking:

New functionality:

    is_refresh_token_used()

Flow:

1.  Receive refresh token
2.  Decode JWT payload
3.  Check whether token was already used
4.  Reject reused token
5.  Mark token as used
6.  Generate new token pair

Expected behavior:

First usage:

    200 OK

Second usage:

    401 UNAUTHORIZED

------------------------------------------------------------------------

# 3. Password Security Improvements

## File

    app/auth.py

## Problem

Password handling required stronger validation consistency.

## Fix Implemented

Implemented secure password hashing using:

    PBKDF2-HMAC-SHA256

with:

    100000 iterations

Features:

-   Random salt generation
-   Secure password comparison
-   Timing attack resistant verification

------------------------------------------------------------------------

# 4. Booking Conflict Detection Bug

## File

    app/routers/bookings.py

## Problem

Room availability conflict detection incorrectly blocked valid
consecutive bookings.

Example:

Existing booking:

    10:00 - 11:00

New booking:

    11:00 - 12:00

The system considered this as overlapping.

------------------------------------------------------------------------

## Root Cause

The previous condition used inclusive comparison:

    start <= end

which treated boundary times as conflicts.

------------------------------------------------------------------------

## Fix Implemented

Changed overlap detection:

Before:

    existing.start_time <= new.end_time
    AND
    new.start_time <= existing.end_time

After:

    existing.start_time < new.end_time
    AND
    new.start_time < existing.end_time

Now:

-   Real overlaps are blocked
-   Back-to-back bookings are allowed

------------------------------------------------------------------------

# 5. Booking Time Validation Bug

## File

    app/routers/bookings.py

## Problem

Bookings could be created too close to the current time because of an
incorrect grace period.

------------------------------------------------------------------------

## Fix Implemented

Updated validation rule:

A booking must satisfy:

    start_time > current_time

Past bookings are rejected immediately.

------------------------------------------------------------------------

# 6. Booking Pagination Bug

## File

    app/routers/bookings.py

## Problem

Pagination skipped records.

Incorrect:

    offset(page * limit)

For page 1:

    offset(10)

causing first records to disappear.

------------------------------------------------------------------------

## Fix

Changed to:

    offset((page - 1) * limit)

Now:

Page 1:

    offset 0

Page 2:

    offset 10

------------------------------------------------------------------------

# 7. Refund Calculation Precision Bug

## File

    app/services/refunds.py

## Problem

Refund calculation converted cents into floating-point dollars.

Example:

    1000 cents
    → 10.00 dollars
    → calculation
    → cents

Floating point conversion can introduce rounding errors.

------------------------------------------------------------------------

## Impact

Possible incorrect refund amounts.

------------------------------------------------------------------------

## Fix

Refund values are now calculated using integer cents.

Benefits:

-   Exact financial calculations
-   No floating point precision issues
-   Correct ledger values

------------------------------------------------------------------------

# 8. Room Statistics Consistency Issue

## Files

    app/services/stats.py
    app/routers/rooms.py

## Problem

Room statistics were maintained only in memory.

Problems:

-   Data loss after restart
-   Possible inconsistency
-   Incorrect statistics during concurrent updates

------------------------------------------------------------------------

## Fix

Statistics endpoint now calculates from database records.

Calculated values:

    Total confirmed bookings

    Total revenue in cents

Source:

    Booking table

This guarantees that API output matches actual booking data.

------------------------------------------------------------------------

# 9. Multi-Tenant Organization Isolation Bug

## File

    app/routers/rooms.py

## Problem

Users from one organization must never access another organization's
rooms.

------------------------------------------------------------------------

## Fix

All room queries now validate:

    Room.id == requested_room_id

    AND

    Room.org_id == current_user.org_id

Unauthorized cross organization access returns:

    404 ROOM_NOT_FOUND

------------------------------------------------------------------------

# 10. Admin Usage Report Validation

## File

    app/routers/admin.py

## Problem

Invalid date ranges were accepted.

Example:

    from = 2026-07-10

    to = 2026-07-09

------------------------------------------------------------------------

## Fix

Added validation:

    from_date <= to_date

Invalid ranges return:

    400 INVALID_BOOKING_WINDOW

------------------------------------------------------------------------

# 11. Database Integrity Improvement

## File

    app/models.py

## Problem

Booking reference codes could potentially duplicate.

------------------------------------------------------------------------

## Fix

Added database uniqueness constraint.

Guarantees:

-   Every booking has a unique reference
-   Duplicate booking references are rejected
-   Concurrent creation remains safe

------------------------------------------------------------------------

# Testing and Verification

## Automated Test Command

    python -m pytest -v

## Final Result

    5 passed

------------------------------------------------------------------------

## Verified Scenarios

### Authentication

✓ Refresh token single-use\
✓ Logout invalidates access token

### Booking

✓ Booking creation works\
✓ Conflict validation works

### Security

✓ Cross organization access blocked

### Reporting

✓ Invalid admin date range rejected

### Statistics

✓ Database-backed room statistics verified

------------------------------------------------------------------------

# Final Status

All identified bugs were fixed successfully.

The final system maintains:

-   Secure authentication
-   Correct JWT lifecycle
-   Reliable booking rules
-   Accurate financial calculations
-   Multi-tenant isolation
-   Database consistency
-   Stable API behavior

The application successfully passes automated validation and is ready
for evaluation.
