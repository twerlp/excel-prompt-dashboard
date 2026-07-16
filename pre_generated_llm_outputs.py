"""
Pre-generated high-quality LLM outputs for the initial demo run.
Each entry maps a story_id + prompt_name -> generated content.

In production, these would come from live LLM API calls.  This file
serves as a test fixture and a quality baseline for evaluating live
LLM outputs against.
"""

import json

PRE_GENERATED = {
    # ── US-001: User Registration ─────────────────────────────────────
    ("US-001", "frs_few_shot"): (
        "FR-160: The system shall provide a self-service registration form "
        "with fields: full_name (string, 2–100 chars), email (RFC 5322 format), "
        "and password (masked input).\n"
        "FR-161: The system shall enforce password complexity: minimum 8 characters, "
        "at least 1 uppercase letter (A–Z), at least 1 digit (0–9), and shall reject "
        "inputs violating any rule with field-level validation errors.\n"
        "FR-162: The system shall validate the email address against RFC 5322 format "
        "and query the user store for duplicates; if a duplicate is found the server "
        "shall return HTTP 409 with message 'An account with this email already exists.'\n"
        "FR-163: The system shall generate a cryptographically random 6-digit numeric "
        "verification token with a TTL of 10 minutes, stored hashed (SHA-256) alongside "
        "the user record.\n"
        "FR-164: The system shall transmit the token via the configured SMTP email "
        "service within 60 seconds of account creation and log the send attempt "
        "(success/failure) to the email audit table.\n"
        "FR-165: The system shall allow up to 3 resend requests per registration session; "
        "each resend generates a fresh token and resets the 10-minute TTL.  The 4th "
        "request shall be rejected with message 'Maximum resend attempts reached.'\n"
        "FR-166: The system shall hash passwords using bcrypt with a cost factor of "
        "≥ 10 before persisting to the users table.\n"
        "FR-167: The system shall provide POST /auth/verify-email accepting { token, "
        "registration_id }; on match, the account status transitions from 'pending' to "
        "'active' and a welcome email is dispatched.\n"
        "FR-168: The system shall log every registration, verification, and resend "
        "event to a security audit table including timestamp, IP address, and user-agent."
    ),
    ("US-001", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-001-G01",
            "description": "Verify successful registration with valid input and email verification.",
            "test_type": "Functional",
            "steps": (
                "1. Navigate to the registration page.\n"
                "2. Enter valid name 'Jane Doe', unique email 'jane@example.com', and password 'Pass1234'.\n"
                "3. Submit the form.\n"
                "4. Retrieve the 6-digit code from the test email inbox.\n"
                "5. Enter the code on the verification screen and submit."
            ),
            "expected": (
                "Account created with status 'pending'.  Verification email sent within 60s.  "
                "After code entry, status transitions to 'active'.  User can authenticate."
            ),
        },
        {
            "tc_id": "TC-001-G02",
            "description": "Verify duplicate email registration is rejected.",
            "test_type": "Functional",
            "steps": (
                "1. Register an account with email 'dupe@example.com'.\n"
                "2. Attempt a second registration with the same email.\n"
                "3. Submit the form."
            ),
            "expected": (
                "HTTP 409 returned.  Response body contains 'An account with this email "
                "already exists.'  No second record is persisted."
            ),
        },
        {
            "tc_id": "TC-001-G03",
            "description": "Verify weak password validation rules.",
            "test_type": "Functional",
            "steps": (
                "1. Open the registration form.\n"
                "2. Enter password 'short' (too few characters, no uppercase, no digit).\n"
                "3. Submit the form."
            ),
            "expected": (
                "Form submission blocked with field-level errors listing each unmet rule: "
                "'Minimum 8 characters required', 'At least 1 uppercase letter required', "
                "'At least 1 digit required'."
            ),
        },
        {
            "tc_id": "TC-001-G04",
            "description": "Verify expired verification token is rejected.",
            "test_type": "Functional",
            "steps": (
                "1. Initiate registration and obtain the token.\n"
                "2. Wait 11 minutes (beyond the 10-minute TTL).\n"
                "3. Enter the correct but expired token on the verification screen."
            ),
            "expected": (
                "Error displayed: 'Verification code has expired. Request a new one.'  "
                "Account remains in 'pending' state.  User can request a new code."
            ),
        },
        {
            "tc_id": "TC-001-G05",
            "description": "Verify resend limit enforcement (max 3 resends).",
            "test_type": "Boundary",
            "steps": (
                "1. On the verification screen, click 'Resend Code' 4 times in sequence.\n"
                "2. Observe the system response on the 4th click."
            ),
            "expected": (
                "Clicks 1–3: new 6-digit code sent successfully, TTL reset to 10 minutes.\n"
                "Click 4: blocked with message 'Maximum resend attempts reached.'  "
                "No further codes sent.  Audit log reflects the blocked attempt."
            ),
        },
        {
            "tc_id": "TC-001-G06",
            "description": "Verify password is stored as bcrypt hash (not plaintext).",
            "test_type": "Security",
            "steps": (
                "1. Register a user with password 'SecurePass9'.\n"
                "2. Query the users table directly for the password_hash column.\n"
                "3. Inspect application logs for the password value."
            ),
            "expected": (
                "password_hash column contains a bcrypt string prefixed with '$2b$' "
                "(or '$2a$').  No plaintext password appears in database columns, "
                "application logs, or API responses."
            ),
        },
    ], indent=2),

    # ── US-002: Shopping Cart ──────────────────────────────────────────
    ("US-002", "frs_few_shot"): (
        "FR-170: The system shall maintain a cart data structure keyed by anonymous "
        "session ID for guest users and by user ID for authenticated users, stored "
        "in a Redis hash with a TTL of 7 days for guest carts.\n"
        "FR-171: The system shall merge a guest cart into the persistent user cart "
        "upon successful login: items with matching SKUs shall have their quantities "
        "summed, non-conflicting items shall be appended.\n"
        "FR-172: The system shall expose REST endpoints: POST /cart/items (add), "
        "PATCH /cart/items/{sku} (update quantity), and DELETE /cart/items/{sku} "
        "(remove).\n"
        "FR-173: The add-item endpoint shall accept { sku: string, quantity: integer }; "
        "if the SKU already exists in the cart, quantity shall be incremented rather "
        "than duplicated.\n"
        "FR-174: The system shall validate quantity constraints: minimum 1 (setting "
        "to 0 shall prompt a removal confirmation), maximum the current inventory count "
        "for the SKU as returned by the inventory service.\n"
        "FR-175: The system shall recalculate the cart subtotal server-side after every "
        "mutation (unit_price × quantity for each line item) and return the updated totals "
        "in the API response.\n"
        "FR-176: The header shopping-cart icon shall display the total unique SKU count "
        "as a badge; the count shall be updated via a WebSocket push or, as fallback, a "
        "client-side poll every 15 seconds.\n"
        "FR-177: The system shall emit 'cart:updated' events to an event bus on each "
        "mutation so that analytics, recommendation, and abandonment-recovery services "
        "can react asynchronously."
    ),
    ("US-002", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-002-G01",
            "description": "Verify adding a new product to an empty cart.",
            "test_type": "Functional",
            "steps": (
                "1. As a guest, browse the product listing.\n"
                "2. Click 'Add to Cart' for SKU 'PROD-A' (unit price $29.99).\n"
                "3. Open the cart drawer."
            ),
            "expected": (
                "Cart displays 1 × PROD-A.  Subtotal shows $29.99.  "
                "Header cart badge displays '1'."
            ),
        },
        {
            "tc_id": "TC-002-G02",
            "description": "Verify adding an existing item increments quantity.",
            "test_type": "Functional",
            "steps": (
                "1. Cart contains 1 × PROD-A.\n"
                "2. Navigate back to the product page and click 'Add to Cart' for PROD-A again.\n"
                "3. Open the cart drawer."
            ),
            "expected": (
                "Cart shows 2 × PROD-A.  Subtotal = $59.98.  "
                "No duplicate line item — only one row for PROD-A."
            ),
        },
        {
            "tc_id": "TC-002-G03",
            "description": "Verify quantity cannot exceed available inventory.",
            "test_type": "Boundary",
            "steps": (
                "1. Inventory for SKU 'PROD-B' = 10 units.\n"
                "2. In the cart, manually type quantity 11 and blur the input field.\n"
                "3. Observe the system response."
            ),
            "expected": (
                "Quantity snaps back to 10 (the max).  A warning toast appears: "
                "'Only 10 units available.'  Subtotal reflects 10 × unit_price."
            ),
        },
        {
            "tc_id": "TC-002-G04",
            "description": "Verify item removal updates cart and badge.",
            "test_type": "Functional",
            "steps": (
                "1. Cart contains items A and B.\n"
                "2. Click the remove icon (trash) on item A.\n"
                "3. Confirm in the confirmation toast.\n"
                "4. Observe the cart drawer and header badge."
            ),
            "expected": (
                "Item A is removed.  Subtotal recalculated to reflect only item B.  "
                "Header badge decrements by 1."
            ),
        },
        {
            "tc_id": "TC-002-G05",
            "description": "Verify guest cart merges into authenticated cart on login.",
            "test_type": "Integration",
            "steps": (
                "1. As a guest, add PROD-C (qty 2) to the cart.\n"
                "2. Log in to an account that already has PROD-C (qty 1) and PROD-D (qty 1).\n"
                "3. Open the cart after login."
            ),
            "expected": (
                "Cart shows 3 × PROD-C (guest qty 2 + existing qty 1) and 1 × PROD-D.  "
                "Subtotal reflects combined quantities.  GUEST cart is cleared."
            ),
        },
        {
            "tc_id": "TC-002-G06",
            "description": "Verify cart survives page refresh for authenticated user.",
            "test_type": "Functional",
            "steps": (
                "1. Log in, add items to the cart.\n"
                "2. Perform a hard browser refresh (Ctrl+Shift+R).\n"
                "3. Open the cart drawer."
            ),
            "expected": (
                "Cart contents are restored exactly as before the refresh.  "
                "No items lost.  Subtotal unchanged."
            ),
        },
    ], indent=2),

    # ── US-003: Payment Processing ─────────────────────────────────────
    ("US-003", "frs_few_shot"): (
        "FR-180: The system shall integrate Stripe Elements on the checkout page to "
        "collect and tokenize card details client-side, ensuring no raw PAN, CVC, or "
        "expiry data traverses the application server (PCI-DSS SAQ-A compliance).\n"
        "FR-181: The system shall provide POST /checkout accepting { payment_method_id: "
        "string (Stripe PM), order_id: string, idempotency_key: string }; it shall "
        "create a PaymentIntent via the Stripe SDK and return the client_secret for "
        "frontend confirmation.\n"
        "FR-182: The server shall register webhook endpoints for Stripe events "
        "payment_intent.succeeded, payment_intent.payment_failed, and "
        "payment_intent.processing; each webhook shall verify the Stripe signature "
        "before processing.\n"
        "FR-183: On payment_intent.succeeded, the system shall update the order status "
        "to 'paid', decrement inventory atomically in a database transaction, enqueue "
        "a confirmation email, and return HTTP 200 to Stripe.\n"
        "FR-184: On payment_intent.payment_failed, the system shall update the order "
        "status to 'payment_failed', store the decline code and message, and notify "
        "the user via email with remedial instructions.\n"
        "FR-185: The system shall enforce idempotency by deriving the idempotency key "
        "from the order ID (e.g., order_{order_id}); if the same key is used within "
        "24 hours the Stripe SDK shall return the existing PaymentIntent rather than "
        "creating a duplicate.\n"
        "FR-186: All payment lifecycle events shall be recorded in an immutable "
        "payment_audit table with columns: order_id, stripe_payment_intent_id, event_type, "
        "amount, currency, status, raw_event (stripped of sensitive data), and created_at.\n"
        "FR-187: The confirmation/receipt email shall include the order summary, "
        "transaction reference, purchase date, and a link to a downloadable PDF receipt."
    ),
    ("US-003", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-003-G01",
            "description": "Verify successful payment with valid Stripe test card.",
            "test_type": "Functional",
            "steps": (
                "1. Add items to cart and proceed to checkout.\n"
                "2. In the Stripe Elements iframe, enter test card 4242 4242 4242 4242, "
                "any future expiry, any CVC.\n"
                "3. Click 'Pay $XX.XX'."
            ),
            "expected": (
                "PaymentIntent status = 'succeeded'.  Order status transitions to 'paid'.  "
                "Inventory quantities decremented.  Confirmation email received.  "
                "User redirected to order success page showing the order reference."
            ),
        },
        {
            "tc_id": "TC-003-G02",
            "description": "Verify payment fails gracefully with declined card.",
            "test_type": "Functional",
            "steps": (
                "1. Proceed to checkout.\n"
                "2. Enter Stripe test card 4000 0000 0000 0002 (generic decline).\n"
                "3. Submit the payment."
            ),
            "expected": (
                "Error message displayed: 'Your card was declined.'  Order status remains "
                "'pending'.  No inventory changes.  No charge appears in Stripe dashboard."
            ),
        },
        {
            "tc_id": "TC-003-G03",
            "description": "Verify idempotency prevents duplicate charges on double submit.",
            "test_type": "Functional",
            "steps": (
                "1. Submit a payment with idempotency key 'order_98765'.\n"
                "2. Before the first request completes, send an identical second request "
                "with the same idempotency key.\n"
                "3. Check Stripe dashboard for charge count."
            ),
            "expected": (
                "Only one PaymentIntent is created.  Both API responses return the same "
                "client_secret and status.  Exactly one charge record exists in Stripe.  "
                "Order status transitions once."
            ),
        },
        {
            "tc_id": "TC-003-G04",
            "description": "Verify webhook idempotency — duplicate webhook does not double-process.",
            "test_type": "Integration",
            "steps": (
                "1. Trigger a successful payment.\n"
                "2. Manually re-deliver the same payment_intent.succeeded webhook from "
                "the Stripe dashboard to the application endpoint.\n"
                "3. Check the order status and inventory."
            ),
            "expected": (
                "Webhook returns HTTP 200.  Order status and inventory are not altered "
                "(idempotent processing).  Only one notification email sent.  "
                "Duplicate event logged as a no-op in payment_audit."
            ),
        },
        {
            "tc_id": "TC-003-G05",
            "description": "Verify no sensitive card data in application logs or database.",
            "test_type": "Security",
            "steps": (
                "1. Complete a full payment flow.\n"
                "2. Grep application logs for patterns matching PAN (\\d{13,19}), "
                "CVC (\\d{3,4}), and expiry date.\n"
                "3. Query the orders and payment_audit tables for card data."
            ),
            "expected": (
                "Zero matches for raw card data in application logs.  Database columns "
                "contain only Stripe token/payment-method IDs (e.g., 'pm_xxx', 'pi_xxx').  "
                "PCI-DSS SAQ-A compliance maintained."
            ),
        },
    ], indent=2),

    # ── US-004: Search with Filters ────────────────────────────────────
    ("US-004", "frs_few_shot"): (
        "FR-190: The system shall provide GET /products accepting query parameters: "
        "q (string, full-text), category (comma-separated IDs), min_price (decimal), "
        "max_price (decimal), min_rating (float 1.0–5.0), page (integer, default 1), "
        "and limit (integer, default 20, max 100).\n"
        "FR-191: The system shall perform full-text search against product name and "
        "description columns using PostgreSQL tsvector/tsquery with a GIN index; "
        "results shall be ranked by ts_rank descending.\n"
        "FR-192: The system shall cache popular search results (top 1000 queries by "
        "frequency) in Redis with a TTL of 5 minutes, using a normalized cache key "
        "derived from the canonicalized query parameters.\n"
        "FR-193: The response shall include a metadata envelope: { total_count, page, "
        "total_pages, limit, products: [{ id, name, price, rating, thumbnail_url, "
        "category_name }] }.\n"
        "FR-194: The client shall debounce the search input by 300 ms before firing "
        "the API request, and shall abort in-flight XHR/fetch requests if a new query "
        "is initiated.\n"
        "FR-195: GET /categories shall return all active categories as [{ id, name, "
        "parent_id }] for populating the category filter multi-select.\n"
        "FR-196: When a query returns zero results, the API response shall include a "
        "'suggestions' array of related queries computed from a synonym/typo-tolerance "
        "index, along with a flag 'empty: true' for the client to render the empty-state UI."
    ),
    ("US-004", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-004-G01",
            "description": "Verify keyword search returns matching products.",
            "test_type": "Functional",
            "steps": (
                "1. Navigate to the search page.\n"
                "2. Type 'wireless headphones' in the search bar.\n"
                "3. Wait for results to load."
            ),
            "expected": (
                "Results contain products whose name or description includes 'wireless' "
                "and 'headphones'.  Results are relevance-sorted (most relevant first).  "
                "Total count and pagination metadata are present."
            ),
        },
        {
            "tc_id": "TC-004-G02",
            "description": "Verify combined filters (category + price + rating) narrow results correctly.",
            "test_type": "Functional",
            "steps": (
                "1. Search for 'laptop'.\n"
                "2. Select category 'Electronics' from the multi-select dropdown.\n"
                "3. Set price range $500 – $1,500.\n"
                "4. Toggle rating filter to 4 stars and above.\n"
                "5. Observe the filtered results."
            ),
            "expected": (
                "All displayed products belong to the 'Electronics' category, are priced "
                "between $500 and $1,500 inclusive, and have an average rating ≥ 4.0.  "
                "Total count reflects the intersection."
            ),
        },
        {
            "tc_id": "TC-004-G03",
            "description": "Verify pagination navigation and URL state.",
            "test_type": "Functional",
            "steps": (
                "1. Execute a search that returns 45 results (limit=20).\n"
                "2. Observe page 1 showing items 1–20.\n"
                "3. Click 'Page 2' and then 'Page 3' in the pagination control."
            ),
            "expected": (
                "Page 2: items 21–40 displayed.  Page 3: items 41–45 displayed.  "
                "URL query string includes 'page=3'.  Pagination shows pages [1] [2] [3] "
                "with current page highlighted."
            ),
        },
        {
            "tc_id": "TC-004-G04",
            "description": "Verify empty search results show helpful suggestions.",
            "test_type": "Functional",
            "steps": (
                "1. Search for 'unicorn-teleporter-9000'.\n"
                "2. Observe the results area."
            ),
            "expected": (
                "Message displayed: 'No products found for \"unicorn-teleporter-9000\".'  "
                "Suggestions may include popular alternative searches.  "
                "A 'Clear All Filters' link is visible and clickable, resetting all params."
            ),
        },
        {
            "tc_id": "TC-004-G05",
            "description": "Verify search response time SLA under load (100k products).",
            "test_type": "Performance",
            "steps": (
                "1. Seed the product catalog with 100,000 products.\n"
                "2. Warm the cache with 50 random search queries.\n"
                "3. Execute 100 concurrent search requests via k6 or JMeter.\n"
                "4. Measure p95 and p99 response times."
            ),
            "expected": (
                "p95 latency ≤ 500 ms.  p99 latency ≤ 800 ms.  "
                "Zero HTTP 5xx errors.  Redis cache-hit ratio ≥ 80%."
            ),
        },
    ], indent=2),

    # ── US-005: RBAC ──────────────────────────────────────────────────
    ("US-005", "frs_few_shot"): (
        "FR-200: The system shall implement Role-Based Access Control (RBAC) with "
        "three core entities: User, Role, and Permission, each having dedicated "
        "database tables with UUID primary keys.\n"
        "FR-201: Permissions shall be stored as 'resource:action' tuples (e.g., "
        "'user:create', 'report:read', 'billing:delete') in a permissions table; "
        "the system shall load all defined permissions at startup from the database "
        "for validation.\n"
        "FR-202: A Role shall be a named collection of permissions linked via a "
        "many-to-many join table (role_permissions).\n"
        "FR-203: A User shall be assigned one or more roles via a user_roles join "
        "table; effective permissions shall be the union of all assigned roles' "
        "permissions, computed at authentication time and cached in the session/JWT.\n"
        "FR-204: The API middleware shall intercept every authenticated request, "
        "extract the required permission from route metadata (e.g., @RequirePermission('user:create')), "
        "and compare against the user's effective permissions; mismatches shall "
        "return HTTP 403 with body { error: 'Forbidden', required_permission: 'user:create' }.\n"
        "FR-205: The frontend shall fetch the user's permission set during login and "
        "store it in the application state; a directive (e.g., *can="'user:delete'" or "
        "v-if=\"$can('user:delete')\") shall conditionally render UI elements.\n"
        "FR-206: Every denied access attempt shall be logged to the audit_log table "
        "with user_id, resource, action, timestamp, IP address, and user_agent.\n"
        "FR-207: Administrative CRUD endpoints (POST/PUT/DELETE /admin/roles, "
        "PUT /admin/users/{id}/roles) shall be restricted to users possessing the "
        "'admin:manage_roles' permission."
    ),
    ("US-005", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-005-G01",
            "description": "Verify Viewer role is denied access to admin pages.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as a user with only the 'Viewer' role.\n"
                "2. Directly navigate to /admin/users via the browser address bar.\n"
                "3. Observe the server response."
            ),
            "expected": (
                "HTTP 403 returned.  User redirected to an 'Access Denied' page with "
                "a message explaining the required permission.  Audit log entry created "
                "with user_id, resource='/admin/users', action='read', and timestamp."
            ),
        },
        {
            "tc_id": "TC-005-G02",
            "description": "Verify Admin can create a new custom role with granular permissions.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as Admin.\n"
                "2. Navigate to Admin → Roles → 'New Role'.\n"
                "3. Name it 'Auditor', check 'report:read' and 'user:read'.\n"
                "4. Click 'Save'."
            ),
            "expected": (
                "Role 'Auditor' appears in the role list.  Expanding it shows the two "
                "assigned permissions.  API returns HTTP 201.  "
                "The role is immediately available for user assignment."
            ),
        },
        {
            "tc_id": "TC-005-G03",
            "description": "Verify UI elements are hidden when user lacks permission.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as Viewer (permissions: 'report:read', 'user:read').\n"
                "2. Navigate to the Reports page.\n"
                "3. Inspect the DOM / visible UI elements."
            ),
            "expected": (
                "'Create Report' and 'Delete Report' buttons are not rendered.  "
                "'Export CSV' button is visible (requires only 'report:read').  "
                "No gaps where hidden elements would appear."
            ),
        },
        {
            "tc_id": "TC-005-G04",
            "description": "Verify permission changes take effect after role reassignment.",
            "test_type": "Functional",
            "steps": (
                "1. Admin adds 'Editor' role to a previously Viewer-only user.\n"
                "2. Viewer user refreshes the page or logs out and back in.\n"
                "3. Observe the UI and attempt a previously forbidden action."
            ),
            "expected": (
                "After refresh/re-login, the user now sees 'Create Report' button.  "
                "POST to /api/reports succeeds with HTTP 201.  "
                "JWT/claims are refreshed to include new permissions."
            ),
        },
        {
            "tc_id": "TC-005-G05",
            "description": "Verify direct API call without authentication returns 401.",
            "test_type": "Security",
            "steps": (
                "1. Without any auth token, send GET /admin/users via curl.\n"
                "2. Observe the HTTP status and response body."
            ),
            "expected": (
                "HTTP 401 Unauthorized.  Response body: { error: 'Authentication required' }.  "
                "No data leaked.  Audit log records the unauthenticated attempt."
            ),
        },
        {
            "tc_id": "TC-005-G06",
            "description": "Verify Admin cannot delete their own admin role (self-lockout prevention).",
            "test_type": "Boundary",
            "steps": (
                "1. Log in as the only Admin user.\n"
                "2. Navigate to their own user profile → Roles.\n"
                "3. Attempt to remove the 'Admin' role from their own account."
            ),
            "expected": (
                "System blocks the action with message: 'Cannot remove the last Admin "
                "role from your own account.'  Admin role remains assigned.  "
                "HTTP 422 returned."
            ),
        },
    ], indent=2),

    # ── US-006: Funds Transfer (Banking) ───────────────────────────────
    ("US-006", "frs_few_shot"): (
        "FR-210: The system shall provide POST /transfer accepting: "
        "source_account_id (UUID), destination_account_id or beneficiary_id "
        "(UUID), amount (decimal, > 0), currency (ISO 4217, default USD), and "
        "optional note (string, max 200 chars).\n"
        "FR-211: The system shall execute intra-bank transfers synchronously "
        "within a database transaction: debit source account, credit destination "
        "account, insert an immutable transaction record with status 'completed'.\n"
        "FR-212: The system shall enqueue inter-bank (external) transfers to the "
        "NEFT/ACH batch processing pipeline with settlement occurring in the next "
        "clearing window; the transfer status shall be 'pending_external' until "
        "the settlement confirmation is received via the core banking callback.\n"
        "FR-213: The system shall validate available balance (including any pending "
        "holds) before authorizing a debit; if insufficient, return HTTP 422 with "
        "message 'Insufficient funds. Available balance: {amount}'.\n"
        "FR-214: The system shall enforce a rolling 24-hour cumulative transfer "
        "limit per account, defaulting to $50,000 with tier-based overrides "
        "configurable via a feature-flag service.\n"
        "FR-215: For transfers exceeding the configurable 2FA threshold (default "
        "$5,000), the system shall trigger a secondary authentication challenge "
        "(OTP via SMS or push notification) before executing the transfer.\n"
        "FR-216: The system shall generate a PDF receipt upon transfer completion "
        "containing: transaction reference (UUID), source/destination masked "
        "account numbers, amount, currency, timestamp, and bank logo; served via "
        "GET /transactions/{id}/receipt.\n"
        "FR-217: The system shall record all transfer lifecycle events in a "
        "transaction_audit table and emit a 'transfer.completed' event to the "
        "event bus for downstream fraud detection and analytics services."
    ),
    ("US-006", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-006-G01",
            "description": "Verify successful intra-bank transfer between own accounts.",
            "test_type": "Functional",
            "steps": (
                "1. Log in to online banking.\n"
                "2. Select source account 'Savings' ($10,000) and destination account 'Checking' ($500).\n"
                "3. Enter transfer amount $1,000 and optional note 'Monthly transfer'.\n"
                "4. Submit transfer."
            ),
            "expected": (
                "Savings balance → $9,000. Checking balance → $1,500. Transaction record "
                "created with status 'completed'. Receipt PDF available. Confirmation "
                "appears on screen with transaction reference."
            ),
        },
        {
            "tc_id": "TC-006-G02",
            "description": "Verify transfer blocked for insufficient funds.",
            "test_type": "Functional",
            "steps": (
                "1. Account 'Savings' has balance $500.\n"
                "2. Initiate transfer of $1,000 to 'Checking'.\n"
                "3. Submit the transfer."
            ),
            "expected": (
                "HTTP 422 returned. Error message: 'Insufficient funds. Available balance: "
                "$500.00.' No debit or credit executed. No transaction record created."
            ),
        },
        {
            "tc_id": "TC-006-G03",
            "description": "Verify 24-hour rolling transfer limit enforcement.",
            "test_type": "Boundary",
            "steps": (
                "1. Transfer $49,000 from Savings (within the $50,000 daily limit).\n"
                "2. Immediately initiate a second transfer of $2,000.\n"
                "3. Observe the result."
            ),
            "expected": (
                "First transfer succeeds. Second transfer blocked with message: "
                "'Daily transfer limit exceeded. Remaining available: $1,000.' "
                "Audit log records the blocked attempt."
            ),
        },
        {
            "tc_id": "TC-006-G04",
            "description": "Verify 2FA challenge required for high-value transfer.",
            "test_type": "Functional",
            "steps": (
                "1. Initiate transfer of $6,000 (above the $5,000 2FA threshold).\n"
                "2. Submit the transfer.\n"
                "3. Complete the OTP challenge sent via SMS."
            ),
            "expected": (
                "System prompts for OTP verification after initial submission. Transfer "
                "only proceeds after correct OTP entry. Receipt generated. "
                "Without OTP, transfer remains in 'pending_mfa' state for 5 minutes, "
                "then expires."
            ),
        },
        {
            "tc_id": "TC-006-G05",
            "description": "Verify transaction atomicity — no partial state on DB failure.",
            "test_type": "Reliability",
            "steps": (
                "1. Initiate intra-bank transfer.\n"
                "2. Simulate database connection failure after the debit executes "
                "but before the credit completes.\n"
                "3. Query both account balances."
            ),
            "expected": (
                "Transaction fully rolled back. Both accounts retain original balances. "
                "No orphan transaction records. Error logged and alert triggered."
            ),
        },
    ], indent=2),

    # ── US-007: Patient Appointment Booking (Healthcare) ───────────────
    ("US-007", "frs_few_shot"): (
        "FR-220: The system shall provide GET /doctors/{id}/slots?date=YYYY-MM-DD "
        "returning available time windows with status (available, locked, booked) "
        "and lock expiry timestamps.\n"
        "FR-221: When a patient selects a slot, the system shall acquire a "
        "pessimistic database-level advisory lock for 5 minutes; the slot status "
        "transitions to 'locked' with locked_until = now + 5 minutes, preventing "
        "any other patient from selecting it.\n"
        "FR-222: The booking endpoint POST /appointments shall accept doctor_id, "
        "slot_id, patient_id, and reason (string, max 500 chars); it shall verify "
        "the slot is still locked by the requesting patient before confirming the "
        "booking and transitioning status to 'booked'.\n"
        "FR-223: The reschedule endpoint PUT /appointments/{id} shall cancel the "
        "existing slot and book the new slot within a single database transaction; "
        "if the new slot becomes unavailable mid-transaction, the operation shall "
        "roll back fully and return HTTP 409.\n"
        "FR-224: The cancellation endpoint DELETE /appointments/{id} shall check "
        "the 24-hour rule: if the appointment start time is more than 24 hours away, "
        "cancellation is free; if less than 24 hours, a $25 late-cancellation fee "
        "record is created on the patient's billing account.\n"
        "FR-225: The system shall dispatch transactional notifications (email + SMS) "
        "via the notification service for: booking confirmation, reschedule "
        "confirmation, and cancellation with fee breakdown if applicable.\n"
        "FR-226: The appointment history endpoint GET /appointments shall accept "
        "query parameters start_date, end_date, and status filter returning "
        "paginated results with doctor_name, date, start_time, end_time, status, "
        "and location."
    ),
    ("US-007", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-007-G01",
            "description": "Verify booking an available time slot.",
            "test_type": "Functional",
            "steps": (
                "1. Select doctor 'Dr. Smith', date '2026-08-15'.\n"
                "2. Choose available slot 10:00–10:30 AM.\n"
                "3. Enter reason 'Annual checkup'.\n"
                "4. Click 'Confirm Booking'."
            ),
            "expected": (
                "Slot status transitions to 'booked'. Confirmation email and SMS received. "
                "Appointment appears in patient history with status 'confirmed'. "
                "Doctor's calendar reflects the booking."
            ),
        },
        {
            "tc_id": "TC-007-G02",
            "description": "Verify slot lock prevents double-booking.",
            "test_type": "Functional",
            "steps": (
                "1. Patient A selects the 10:00 AM slot (lock acquired).\n"
                "2. Within 5 minutes, Patient B queries the same doctor and date.\n"
                "3. Patient B attempts to select the 10:00 AM slot."
            ),
            "expected": (
                "Patient B sees the slot as 'locked' (grayed out, not selectable). "
                "Tooltip or message: 'This slot is temporarily reserved by another patient.'"
            ),
        },
        {
            "tc_id": "TC-007-G03",
            "description": "Verify locked slot releases after 5-minute timeout.",
            "test_type": "Functional",
            "steps": (
                "1. Patient A selects a slot but does not confirm.\n"
                "2. Wait 6 minutes for the lock to expire.\n"
                "3. Patient B refreshes and selects the same slot."
            ),
            "expected": (
                "After 6 minutes, slot status reverts to 'available'. Patient B can "
                "successfully select and book the slot. No lock conflict."
            ),
        },
        {
            "tc_id": "TC-007-G04",
            "description": "Verify late cancellation fee (within 24 hours).",
            "test_type": "Functional",
            "steps": (
                "1. Book an appointment for 9:00 AM tomorrow (less than 24 hours away).\n"
                "2. Cancel the appointment via the patient portal.\n"
                "3. Check the patient's billing account."
            ),
            "expected": (
                "Cancellation confirmed. $25 fee added to patient billing account with "
                "description 'Late cancellation fee — Appointment 2026-07-16 09:00'. "
                "Slot immediately becomes available for re-booking."
            ),
        },
        {
            "tc_id": "TC-007-G05",
            "description": "Verify atomic reschedule — no orphan state on concurrent booking.",
            "test_type": "Functional",
            "steps": (
                "1. Reschedule existing appointment from Slot A to Slot B.\n"
                "2. Simulate Slot B being taken by another patient between validation "
                "and commit phases.\n"
                "3. Observe the transaction outcome."
            ),
            "expected": (
                "Transaction rolls back. Original appointment on Slot A remains intact. "
                "Error returned: 'Selected slot is no longer available. Please choose another.' "
                "HTTP 409 Conflict."
            ),
        },
    ], indent=2),

    # ── US-008: HIPAA Patient Data Export (Healthcare) ─────────────────
    ("US-008", "frs_few_shot"): (
        "FR-230: The system shall provide POST /export-requests that creates an "
        "export job with status 'queued' and enqueues it to a background worker "
        "queue; the response shall include a job_id for status tracking.\n"
        "FR-231: The export worker shall aggregate patient data from downstream "
        "services (allergies, medications, lab results, immunizations, visit "
        "summaries) and serialize into a FHIR R4-compliant JSON Bundle resource.\n"
        "FR-232: The worker shall render a human-readable PDF summary containing "
        "patient demographics, visit history table, lab results grid, and medication "
        "list using a templating engine with the clinic's branding.\n"
        "FR-233: Generated files (FHIR JSON + PDF) shall be compressed into a ZIP "
        "archive and uploaded to encrypted object storage (S3 with SSE-KMS, AES-256); "
        "a presigned download URL valid for 24 hours and limited to 1 access shall "
        "be generated.\n"
        "FR-234: The system shall send the download link via the notification service "
        "and record the export event in a HIPAA-compliant audit table with columns: "
        "patient_id, timestamp, export_type ('full'), requester_ip, user_agent, "
        "success/failure status.\n"
        "FR-235: The download endpoint GET /exports/{id}/download shall require "
        "re-authentication (password verification or TOTP if MFA is enabled) before "
        "serving the presigned URL redirect; the presigned URL shall be validated "
        "for expiry and single-use constraints.\n"
        "FR-236: The system shall enforce access control so that only the requesting "
        "patient, a delegated guardian (verified via patient-guardian relationship), "
        "or an authorized provider with 'export:access' permission can download the export."
    ),
    ("US-008", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-008-G01",
            "description": "Verify successful export generation and download.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as a patient.\n"
                "2. Navigate to My Records → Request Data Export.\n"
                "3. Wait for status to change to 'Ready' (polling the status endpoint).\n"
                "4. Open the email with the download link.\n"
                "5. Click the link, re-authenticate with password.\n"
                "6. Download and open the ZIP file."
            ),
            "expected": (
                "ZIP contains: patient_summary.pdf (human-readable) and fhir_bundle.json "
                "(FHIR R4 compliant). Audit log entry created. Download link consumed "
                "(single-use). All data categories present and accurate."
            ),
        },
        {
            "tc_id": "TC-008-G02",
            "description": "Verify download link expires after 24 hours.",
            "test_type": "Functional",
            "steps": (
                "1. Request and complete an export.\n"
                "2. Advance system clock by 25 hours.\n"
                "3. Attempt to download using the original presigned URL."
            ),
            "expected": (
                "Error message: 'This download link has expired. Please request a new "
                "export.' Presigned URL returns HTTP 403 from S3. Audit log records "
                "the attempted expired access."
            ),
        },
        {
            "tc_id": "TC-008-G03",
            "description": "Verify download link is single-use (cannot be reused).",
            "test_type": "Functional",
            "steps": (
                "1. Complete an export and download successfully.\n"
                "2. Attempt to download again with the same link (same browser or "
                "different device)."
            ),
            "expected": (
                "Error: 'This download link has already been used.' No file served. "
                "Audit log records the duplicate access attempt."
            ),
        },
        {
            "tc_id": "TC-008-G04",
            "description": "Verify cross-patient access is blocked (horizontal privilege).",
            "test_type": "Security",
            "steps": (
                "1. Patient A requests and completes an export.\n"
                "2. Log in as Patient B.\n"
                "3. Attempt to access GET /exports/{PatientA_export_id}/download."
            ),
            "expected": (
                "HTTP 403 Forbidden. Message: 'You are not authorized to access this "
                "export.' Patient B's audit log records the unauthorized attempt. "
                "No data leaked."
            ),
        },
        {
            "tc_id": "TC-008-G05",
            "description": "Verify re-authentication gate before download.",
            "test_type": "Security",
            "steps": (
                "1. Click a download link while having a session older than 30 minutes.\n"
                "2. Observe the authentication challenge.\n"
                "3. Enter incorrect password, then correct password."
            ),
            "expected": (
                "System redirects to password re-verification page. Incorrect password "
                "shows error and does not download. After correct password, download "
                "proceeds normally. Failed attempts logged to audit."
            ),
        },
    ], indent=2),

    # ── US-009: Social Media Feed (Social Media) ───────────────────────
    ("US-009", "frs_few_shot"): (
        "FR-240: The system shall implement a feed-ranking service that computes "
        "a relevance score for each candidate post using the formula: score = "
        "0.3 × recency_score + 0.4 × engagement_score + 0.3 × affinity_score, "
        "with all weights configurable via a feature-flag service.\n"
        "FR-241: Recency score shall use exponential decay: e^(-λ × age_hours) "
        "where λ is a configurable decay coefficient (default 0.05).\n"
        "FR-242: Engagement score shall normalize (min-max scaling) the sum of "
        "weighted signals: likes × 1.0 + comments × 2.0 + shares × 3.0 + "
        "view_duration_seconds × 0.1, aggregated over the trailing 24 hours.\n"
        "FR-243: Affinity score shall be derived from a collaborative-filtering "
        "user embedding similarity score (cosine similarity between user vectors "
        "in the recommendation model) with a fallback to topic-tag overlap count.\n"
        "FR-244: The GET /feed endpoint shall accept ranking_mode (algorithmic|"
        "chronological, default algorithmic), cursor (opaque string for pagination), "
        "and limit (default 20, max 50); chronological mode shall sort by "
        "created_at DESC only.\n"
        "FR-245: The system shall pre-compute and cache the top 200 ranked posts "
        "per active user in Redis with a TTL of 5 minutes; on cache miss, the "
        "feed shall be computed synchronously with a timeout of 2 seconds, "
        "falling back to a globally popular feed on timeout.\n"
        "FR-246: The system shall filter out posts authored by users in the "
        "requesting user's muted or blocked lists at query time using a NOT IN "
        "subquery against the user_relationships table.\n"
        "FR-247: The client shall implement infinite scroll using the Intersection "
        "Observer API on a sentinel DOM element; when visible, the next cursor "
        "page is fetched and appended to the feed list without full re-render."
    ),
    ("US-009", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-009-G01",
            "description": "Verify algorithmic feed ranks by computed relevance score.",
            "test_type": "Functional",
            "steps": (
                "1. Seed test data: Post A (new, high engagement, high affinity), "
                "Post B (old, low engagement, low affinity), Post C (new, low affinity).\n"
                "2. Load feed for User X (has affinity with Post A's author).\n"
                "3. Observe post order."
            ),
            "expected": (
                "Posts ranked in descending order of computed score. Post A appears "
                "first (high affinity + engagement). Post B appears last. Post C "
                "appears in middle."
            ),
        },
        {
            "tc_id": "TC-009-G02",
            "description": "Verify chronological feed toggle and persistence.",
            "test_type": "Functional",
            "steps": (
                "1. Load the algorithmic feed.\n"
                "2. Toggle the feed mode selector from 'Algorithmic' to 'Chronological'.\n"
                "3. Observe post order.\n"
                "4. Refresh the page."
            ),
            "expected": (
                "Post order switches to strictly reverse-chronological (newest first). "
                "Toggle preference persists in user settings across page refresh. "
                "API call includes ranking_mode=chronological."
            ),
        },
        {
            "tc_id": "TC-009-G03",
            "description": "Verify muted user's posts are excluded from feed.",
            "test_type": "Functional",
            "steps": (
                "1. User A mutes User B.\n"
                "2. User B creates a new post.\n"
                "3. User A loads their feed and scrolls through all pages."
            ),
            "expected": (
                "User B's post does not appear at any scroll depth. Total feed count "
                "excludes muted users' posts. No blank/gap where the post would be."
            ),
        },
        {
            "tc_id": "TC-009-G04",
            "description": "Verify infinite scroll loads next page without duplicates.",
            "test_type": "Functional",
            "steps": (
                "1. Load the feed (20 posts).\n"
                "2. Scroll to the bottom.\n"
                "3. Observe the loading spinner → next 20 posts appended.\n"
                "4. Repeat for page 3."
            ),
            "expected": (
                "Pages append seamlessly. No duplicate posts between pages. URL "
                "fragment updated for deep-linking. Scroll position maintained."
            ),
        },
        {
            "tc_id": "TC-009-G05",
            "description": "Verify feed load time SLA with cache miss.",
            "test_type": "Performance",
            "steps": (
                "1. Flush Redis feed cache.\n"
                "2. Load feed for a user with 500k candidate posts.\n"
                "3. Measure Time to First Byte (TTFB)."
            ),
            "expected": (
                "p95 TTFB ≤ 1000 ms for algorithmic feed. If compute exceeds 2s, "
                "fallback to globally popular feed returned. Redis cache-hit ratio "
                "≥ 95% after 5-minute warm-up."
            ),
        },
    ], indent=2),

    # ── US-010: Employee Leave Management (HR & Payroll) ────────────────
    ("US-010", "frs_few_shot"): (
        "FR-250: The system shall provide POST /leave-requests accepting: "
        "leave_type (enum: sick, casual, earned, unpaid), start_date, end_date "
        "(ISO 8601), reason (string, max 1000 chars), and optional attachment_url.\n"
        "FR-251: The server shall validate the request: start_date ≤ end_date, "
        "dates not in the past, no overlap with existing approved leave for the "
        "same employee, and available leave balance sufficient for the number of "
        "working days in the range.\n"
        "FR-252: On successful validation, the system shall create a leave "
        "request record with status 'pending' and push a notification to the "
        "employee's reporting manager via the organization hierarchy service and "
        "notification hub (email + push notification).\n"
        "FR-253: The manager decision endpoint PUT /leave-requests/{id}/decision "
        "shall accept { status: 'approved'|'rejected', comments: string }; on "
        "'approved', the leave-balance service shall be called to decrement "
        "the employee's leave entitlement for the appropriate leave type.\n"
        "FR-254: The system shall send the decision notification to the employee's "
        "registered email and push-enabled devices; the notification body shall "
        "include the manager's comments.\n"
        "FR-255: A scheduled job shall run every 30 minutes to identify leave "
        "requests with status 'pending' older than 48 hours; for each such "
        "request, an escalation notification shall be sent to the skip-level "
        "manager and the original manager shall be flagged as 'missed_sla'.\n"
        "FR-256: The team calendar endpoint GET /leave-calendar?month=YYYY-MM&"
        "department_id=X shall return all approved leave entries for the "
        "department, aggregated by date with employee name, leave type, and "
        "duration for rendering in the team calendar view."
    ),
    ("US-010", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-010-G01",
            "description": "Verify successful leave application and approval flow.",
            "test_type": "Functional",
            "steps": (
                "1. Employee logs in and navigates to Leave → Apply.\n"
                "2. Select 'Casual Leave', dates Dec 20–22 (3 days), reason 'Family event'.\n"
                "3. Submit the request.\n"
                "4. Manager receives notification → reviews → clicks 'Approve' with comment 'Enjoy!'.\n"
                "5. Employee refreshes their dashboard."
            ),
            "expected": (
                "Status → 'Approved'. Leave balance decremented by 3 days. Employee "
                "receives approval notification with manager's comment. Leave appears "
                "in team calendar."
            ),
        },
        {
            "tc_id": "TC-010-G02",
            "description": "Verify manager rejection with comments.",
            "test_type": "Functional",
            "steps": (
                "1. Employee applies for leave.\n"
                "2. Manager clicks 'Reject', enters comment 'Critical sprint — please reschedule after Dec 25'.\n"
                "3. Employee checks status."
            ),
            "expected": (
                "Status → 'Rejected'. Employee notified with rejection reason. Leave "
                "balance unchanged. Employee can reapply for other dates."
            ),
        },
        {
            "tc_id": "TC-010-G03",
            "description": "Verify overlapping leave prevention.",
            "test_type": "Functional",
            "steps": (
                "1. Employee has approved leave Dec 10–12.\n"
                "2. Attempt to apply for new leave Dec 11–14."
            ),
            "expected": (
                "Validation error: 'Request overlaps with existing approved leave "
                "(Dec 10–Dec 12).' Request not submitted. Form highlights the "
                "conflicting dates."
            ),
        },
        {
            "tc_id": "TC-010-G04",
            "description": "Verify escalation to skip-level manager after 48 hours.",
            "test_type": "Functional",
            "steps": (
                "1. Employee submits leave request.\n"
                "2. Original manager takes no action.\n"
                "3. Advance system clock 49 hours and trigger the escalation job.\n"
                "4. Check skip-level manager's notifications and original manager's flags."
            ),
            "expected": (
                "Skip-level manager receives escalation notification: 'Leave request "
                "for [Employee Name] awaits action — original manager [Name] missed "
                "48h SLA.' Original manager dashboard shows SLA breach flag. "
                "Request remains pending for skip-level action."
            ),
        },
        {
            "tc_id": "TC-010-G05",
            "description": "Verify team calendar shows department-wide absences.",
            "test_type": "Functional",
            "steps": (
                "1. Two employees in the same department have approved leave: "
                "Emp1 Dec 5–6, Emp2 Dec 5–8.\n"
                "2. Open the team calendar for December.\n"
                "3. Observe Dec 5 view."
            ),
            "expected": (
                "Dec 5 shows both Emp1 and Emp2 as absent. Dec 6 shows both. "
                "Dec 7–8 show only Emp2. Tooltip on each shows leave type. "
                "Department summary shows '2 of 10 on leave' for Dec 5."
            ),
        },
        {
            "tc_id": "TC-010-G06",
            "description": "Verify insufficient leave balance warning.",
            "test_type": "Boundary",
            "steps": (
                "1. Employee has 2 remaining casual leave days.\n"
                "2. Apply for 5 days casual leave.\n"
                "3. Observe the form validation."
            ),
            "expected": (
                "Warning displayed: 'You only have 2 casual leave day(s) remaining. "
                "The remaining 3 days will be marked as unpaid.' Request is still "
                "submittable with a confirmation checkbox acknowledging the warning."
            ),
        },
    ], indent=2),

    # ── US-011: Real-Time Dashboard (Analytics / BI) ────────────────────
    ("US-011", "frs_few_shot"): (
        "FR-260: The system shall establish a WebSocket connection at "
        "wss://<host>/ws/dashboard authenticated via a JWT token passed in the "
        "connection query string and validated on the server before upgrading.\n"
        "FR-261: The server shall push aggregated KPI updates from a Kafka/event-stream "
        "topic to all connected dashboard clients at a maximum frequency of once per "
        "second per client, using a publish-subscribe pattern.\n"
        "FR-262: The server shall implement a fallback HTTP polling endpoint "
        "GET /dashboard/kpis?range={today|week|month} returning the same KPI payload "
        "structure for clients where WebSocket is unavailable.\n"
        "FR-263: The client shall detect WebSocket disconnection events and reconnect "
        "using exponential backoff with jitter: initial delay 1 second, maximum delay "
        "30 seconds, with a cap of 10 retries before falling back to polling.\n"
        "FR-264: KPI computation shall be performed by a stream processor "
        "(Kafka Streams or Apache Flink) that aggregates raw event data into "
        "rolling-window metrics: revenue (sum), active_users (count distinct), "
        "order_volume (count), conversion_rate (ratio), avg_order_value (average), "
        "cart_abandonment (ratio).\n"
        "FR-265: Sparkline data shall be fetched via GET /dashboard/sparklines?metric={name}"
        "&range={range} returning an array of {timestamp: ISO 8601, value: number} at "
        "5-minute intervals for the trailing 24 hours.\n"
        "FR-266: The data freshness monitor shall compare the timestamp of the last "
        "successfully processed event against the current wall-clock time; indicator "
        "states: green (≤ 30s latency), amber (30s–5min), red (> 5min).\n"
        "FR-267: The KPI percent-change calculation shall compare the current period "
        "aggregate against the same-duration previous period (today vs yesterday, "
        "this-week vs last-week) and display the delta with a green/red arrow indicator."
    ),
    ("US-011", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-011-G01",
            "description": "Verify KPI cards update in real-time via WebSocket.",
            "test_type": "Functional",
            "steps": (
                "1. Open the dashboard in a WebSocket-capable browser.\n"
                "2. Send a simulated 'order_placed' event to the event stream.\n"
                "3. Observe the Orders KPI card within 2 seconds."
            ),
            "expected": (
                "Orders KPI increments by 1. Revenue KPI updates in the same push cycle. "
                "Active Users count reflects the new session. All 6 KPI cards reflect "
                "the updated data without page refresh."
            ),
        },
        {
            "tc_id": "TC-011-G02",
            "description": "Verify WebSocket reconnects with exponential backoff on disconnect.",
            "test_type": "Functional",
            "steps": (
                "1. Open the dashboard with an active WebSocket connection.\n"
                "2. Stop the WebSocket server.\n"
                "3. Observe the connection status indicator for 35 seconds.\n"
                "4. Restart the WebSocket server."
            ),
            "expected": (
                "Connection indicator changes to 'Disconnected'. Client retries at "
                "intervals of ~1s, ~2s, ~4s, ~8s, ~16s, ~30s. Reconnects within seconds "
                "of server restart. No data gap due to event replay from Kafka offset."
            ),
        },
        {
            "tc_id": "TC-011-G03",
            "description": "Verify HTTP polling fallback when WebSocket is unavailable.",
            "test_type": "Functional",
            "steps": (
                "1. Block the WebSocket port at the network level.\n"
                "2. Open the dashboard.\n"
                "3. Observe the data update mechanism."
            ),
            "expected": (
                "WebSocket connection attempt fails after timeout. Client falls back to "
                "HTTP polling every 5 seconds. All 6 KPI cards display and update. "
                "Polling continues until WebSocket becomes available again."
            ),
        },
        {
            "tc_id": "TC-011-G04",
            "description": "Verify sparkline chart renders 24-hour history at 5-min intervals.",
            "test_type": "Functional",
            "steps": (
                "1. Load the dashboard.\n"
                "2. Locate the sparkline chart embedded in the Revenue KPI card.\n"
                "3. Hover over multiple data points on the sparkline."
            ),
            "expected": (
                "Sparkline chart renders 288 data points (24h / 5min). Hovering each point "
                "shows a tooltip with the precise timestamp and value. Chart is responsive "
                "and uses the dashboard color theme."
            ),
        },
        {
            "tc_id": "TC-011-G05",
            "description": "Verify freshness indicator transitions through green/amber/red states.",
            "test_type": "Functional",
            "steps": (
                "1. Load dashboard with healthy event pipeline → green indicator.\n"
                "2. Pause the event pipeline for 35 seconds → observe.\n"
                "3. Pause the event pipeline for 6 minutes → observe."
            ),
            "expected": (
                "At t=0: indicator is green, tooltip 'Live'.\n"
                "At t=30s: indicator turns amber, tooltip 'Delayed — last update 35s ago'.\n"
                "At t=5min: indicator turns red, tooltip 'Stale — last update 6m ago'.\n"
                "When pipeline resumes, indicator returns to green."
            ),
        },
        {
            "tc_id": "TC-011-G06",
            "description": "Verify time-range selector updates all KPIs and sparklines.",
            "test_type": "Functional",
            "steps": (
                "1. Load the dashboard (default 'Today').\n"
                "2. Switch to 'This Week'.\n"
                "3. Switch to 'This Month'.\n"
                "4. Switch to 'Custom' and select a 15-day range."
            ),
            "expected": (
                "Each range change triggers new API calls for KPIs and sparklines. "
                "Data reflects the selected period. Percent-change comparisons update "
                "accordingly (e.g., 'This Week' vs 'Last Week'). Custom date picker "
                "works without page reload."
            ),
        },
    ], indent=2),

    # ── US-012: MFA Enrollment (Cybersecurity) ──────────────────────────
    ("US-012", "frs_few_shot"): (
        "FR-270: The system shall generate a TOTP secret (RFC 6238) per user, "
        "store it AES-256-GCM encrypted in the user_mfa table, and present it as "
        "a QR code encoded as an otpauth:// URI with issuer label and account name.\n"
        "FR-271: The system shall support FIDO2/WebAuthn credential registration by "
        "generating a cryptographically random challenge, receiving the attestation "
        "response from the client authenticator, verifying the signature, and storing "
        "credential_id and public_key in the user_mfa table.\n"
        "FR-272: All MFA enrollment operations shall require re-verification of the "
        "user's current password before the enrollment flow begins; the password "
        "check endpoint POST /auth/verify-password shall return a time-limited "
        "enrollment session token (TTL 5 minutes).\n"
        "FR-273: Upon successful enrollment of the first MFA method, the system "
        "shall generate 10 cryptographically random recovery codes (8 alphanumeric "
        "characters each, charset excluding ambiguous characters I/l/0/O), hash them "
        "with SHA-256, and store only the hashes.\n"
        "FR-274: Recovery codes shall be displayed to the user exactly once with a "
        "prominent warning and a 'Download as TXT' button; the plaintext codes shall "
        "not be stored or retrievable after the initial display.\n"
        "FR-275: The MFA management dashboard GET /user/security/mfa shall list all "
        "enrolled methods with type (totp|webauthn), label, and created_at; "
        "DELETE /user/security/mfa/{method_id} shall remove a method after password "
        "re-verification and automatically invalidate associated recovery codes if "
        "the last method is removed.\n"
        "FR-276: On the next login after MFA enrollment, the authentication flow "
        "shall present an MFA challenge step after successful password verification; "
        "the MFA token shall be validated with a ±1 step window for TOTP and standard "
        "WebAuthn assertion verification for FIDO2 credentials."
    ),
    ("US-012", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-012-G01",
            "description": "Verify TOTP enrollment with QR code scan and confirmation.",
            "test_type": "Functional",
            "steps": (
                "1. Log in to the application.\n"
                "2. Navigate to Security Settings → 'Enable Two-Factor Authentication'.\n"
                "3. Re-enter current password when prompted.\n"
                "4. Scan the displayed QR code using Google Authenticator.\n"
                "5. Enter the 6-digit TOTP code shown in the authenticator app.\n"
                "6. Save and download recovery codes."
            ),
            "expected": (
                "TOTP method enrolled with label 'Google Authenticator'. Recovery codes "
                "displayed as a 10-code list with download option. On next login, user "
                "is prompted for TOTP code after password. Login succeeds with valid code."
            ),
        },
        {
            "tc_id": "TC-012-G02",
            "description": "Verify login with recovery code when authenticator is unavailable.",
            "test_type": "Functional",
            "steps": (
                "1. At the MFA challenge screen, click 'Use Recovery Code'.\n"
                "2. Enter a valid recovery code from the saved list.\n"
                "3. Attempt to reuse the same recovery code on a subsequent login."
            ),
            "expected": (
                "First login succeeds with valid recovery code. The used code is "
                "invalidated. Second attempt with same code shows 'Invalid or already "
                "used recovery code.' Remaining unused codes still work."
            ),
        },
        {
            "tc_id": "TC-012-G03",
            "description": "Verify TOTP code rejected after 3 consecutive invalid attempts.",
            "test_type": "Boundary",
            "steps": (
                "1. At MFA challenge, enter an incorrect 6-digit code.\n"
                "2. Repeat for the 2nd and 3rd attempts.\n"
                "3. Attempt a 4th time."
            ),
            "expected": (
                "Attempts 1–3 show 'Invalid code. X attempts remaining.' "
                "4th attempt locks the account for 15 minutes with message: "
                "'Too many failed attempts. Account temporarily locked. Try again in 15 minutes.' "
                "Audit log records each failed attempt."
            ),
        },
        {
            "tc_id": "TC-012-G04",
            "description": "Verify MFA method revocation disables MFA challenge.",
            "test_type": "Functional",
            "steps": (
                "1. Remove the TOTP method from Security Settings (re-verify password).\n"
                "2. Log out.\n"
                "3. Log in again with username and password."
            ),
            "expected": (
                "Login succeeds after password only — no MFA challenge presented. "
                "Recovery codes are invalidated. Security Settings shows no enrolled "
                "MFA methods. Audit log records the method removal."
            ),
        },
        {
            "tc_id": "TC-012-G05",
            "description": "Verify password re-verification is required before any MFA changes.",
            "test_type": "Security",
            "steps": (
                "1. Log in (session is valid).\n"
                "2. Directly call POST /user/security/mfa/totp/enroll without password.\n"
                "3. Enter an incorrect password when the re-verification prompt appears."
            ),
            "expected": (
                "API call returns HTTP 401 with message 'Password re-verification required.' "
                "When prompted, incorrect password blocks enrollment with error 'Password "
                "is incorrect.' Audit log records the failed re-verification attempt."
            ),
        },
    ], indent=2),

    # ── US-013: Bulk CSV Import (Supply Chain) ──────────────────────────
    ("US-013", "frs_few_shot"): (
        "FR-280: The system shall provide POST /inventory/import accepting a "
        "multipart/form-data body with a CSV file (max 10 MB) and returning a "
        "job_id for asynchronous processing status tracking.\n"
        "FR-281: The server shall validate CSV header rows against the required "
        "schema: SKU (string, non-empty), Name (string, max 200 chars), Quantity "
        "(non-negative integer), UnitPrice (positive decimal ≤ 999,999.99), "
        "Warehouse (string matching a known warehouse code); reject the entire "
        "import with HTTP 400 if headers are missing or malformed.\n"
        "FR-282: For each data row, the system shall apply field-level validation: "
        "SKU must be non-empty and unique within the system (or within the batch "
        "for new SKUs); Quantity must be a non-negative integer; UnitPrice must be "
        "a positive decimal; Warehouse must match a valid code from the warehouses table.\n"
        "FR-283: Valid rows shall be upserted into the inventory table using "
        "INSERT ... ON CONFLICT (sku) DO UPDATE within a batch database transaction "
        "of 500 rows per commit.\n"
        "FR-284: Invalid rows shall be aggregated with row_number, the original "
        "row data, and an error_message array; at job completion, the system shall "
        "generate a downloadable error CSV accessible via "
        "GET /inventory/imports/{job_id}/errors for 7 days.\n"
        "FR-285: Job progress shall be exposed via GET /inventory/imports/{job_id}/status "
        "returning { status: pending|processing|completed|failed, total_rows: int, "
        "processed_rows: int, error_count: int }.\n"
        "FR-286: File uploads exceeding the 10 MB limit shall be rejected at the "
        "API gateway/middleware level with HTTP 413 Payload Too Large before any "
        "background processing begins.\n"
        "FR-287: Import history GET /inventory/imports shall return a paginated list "
        "of past imports with metadata: import_id, filename, uploaded_by, uploaded_at, "
        "status, total_rows, success_count, error_count."
    ),
    ("US-013", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-013-G01",
            "description": "Verify successful CSV import with all valid rows.",
            "test_type": "Functional",
            "steps": (
                "1. Prepare a CSV with 5 rows, all valid: unique SKUs, valid quantities, "
                "valid warehouse codes, correct headers.\n"
                "2. Upload the file via POST /inventory/import.\n"
                "3. Poll GET /inventory/imports/{job_id}/status until status='completed'.\n"
                "4. Query the inventory table for the imported SKUs."
            ),
            "expected": (
                "Job status transitions: pending → processing → completed. All 5 rows "
                "processed with 0 errors. All 5 SKUs present in inventory with correct "
                "Name, Quantity, UnitPrice, and Warehouse. Progress bar showed 100%."
            ),
        },
        {
            "tc_id": "TC-013-G02",
            "description": "Verify partial success with error report for invalid rows.",
            "test_type": "Functional",
            "steps": (
                "1. Upload a CSV with 8 rows: 5 valid, 2 with negative quantity, "
                "1 with invalid warehouse code.\n"
                "2. Wait for job completion.\n"
                "3. Download the error CSV from GET /inventory/imports/{job_id}/errors."
            ),
            "expected": (
                "Job status = 'completed'. 5 rows processed successfully. 3 rows in "
                "error CSV with row_number, original data, and specific error messages "
                "(e.g., 'Quantity must be non-negative', 'Warehouse code X99 not found'). "
                "Progress shows 5/8 rows processed."
            ),
        },
        {
            "tc_id": "TC-013-G03",
            "description": "Verify 10 MB file size limit enforced.",
            "test_type": "Boundary",
            "steps": (
                "1. Generate a CSV file of 10.5 MB (exceeds the 10 MB limit).\n"
                "2. Attempt to upload via POST /inventory/import.\n"
                "3. Also upload a file of exactly 10 MB (at the limit)."
            ),
            "expected": (
                "10.5 MB: HTTP 413 Payload Too Large returned immediately. File not "
                "processed. 10 MB file: accepted and processed normally."
            ),
        },
        {
            "tc_id": "TC-013-G04",
            "description": "Verify missing or incorrect headers reject entire import.",
            "test_type": "Functional",
            "steps": (
                "1. Upload CSV with headers: SKU, Name, Price (missing Quantity and Warehouse, "
                "UnitPrice renamed to Price).\n"
                "2. Observe the job status."
            ),
            "expected": (
                "Job status → 'failed'. Error message: 'Missing required columns: Quantity, "
                "Warehouse.' or 'Unknown column: Price. Expected: SKU, Name, Quantity, "
                "UnitPrice, Warehouse.' No rows processed."
            ),
        },
        {
            "tc_id": "TC-013-G05",
            "description": "Verify upsert — existing SKU is updated, not duplicated.",
            "test_type": "Functional",
            "steps": (
                "1. Pre-populate inventory with SKU 'WIDGET-001', quantity 50.\n"
                "2. Upload CSV with row: SKU='WIDGET-001', quantity=200.\n"
                "3. After job completion, query inventory for 'WIDGET-001'."
            ),
            "expected": (
                "SKU 'WIDGET-001' quantity updated to 200 (not 250, not duplicated). "
                "Only one row for 'WIDGET-001' in inventory table. Upsert behaved as expected."
            ),
        },
    ], indent=2),

    # ── US-014: Push Notification Preferences (Mobile / Engagement) ─────
    ("US-014", "frs_few_shot"): (
        "FR-290: The system shall maintain a user_notification_prefs record with "
        "boolean columns for each category: promotions, order_updates, social_activity, "
        "product_recommendations, account_alerts, defaulting all to true for new users.\n"
        "FR-291: The PATCH /user/preferences/notifications endpoint shall accept a "
        "partial update payload (JSON); only provided fields are updated; attempts to "
        "set order_updates to false shall be rejected with HTTP 422.\n"
        "FR-292: The notification dispatch service shall filter recipients by checking "
        "their preferences before sending any non-transactional notification; "
        "order-triggered notifications (shipped, delivered, cancelled) shall bypass "
        "this filter irrespective of the order_updates preference.\n"
        "FR-293: Quiet-hours configuration shall be stored as start_time (HH:MM 24h), "
        "end_time (HH:MM 24h), and timezone (IANA string); notifications queued during "
        "quiet hours shall be held in a 'deferred' queue and delivered at end_time in "
        "the user's configured timezone.\n"
        "FR-294: On preferences update, the server shall publish a 'user:prefs:updated' "
        "event to the real-time channel (WebSocket/SSE) to sync across the user's "
        "active sessions and devices within 5 seconds.\n"
        "FR-295: New user accounts shall be provisioned with a default preferences "
        "record (all categories true, no quiet hours) as part of the account creation "
        "transaction.\n"
        "FR-296: The notification settings UI shall render a locked toggle for "
        "'Order Updates' that is always ON and disabled (grayed out) with a tooltip: "
        "'Transactional notifications cannot be disabled.'"
    ),
    ("US-014", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-014-G01",
            "description": "Verify disabling a notification category stops delivery.",
            "test_type": "Functional",
            "steps": (
                "1. Go to Settings → Notifications.\n"
                "2. Toggle 'Promotions' to OFF.\n"
                "3. Trigger a promotional campaign notification batch.\n"
                "4. Check the user's device for the notification."
            ),
            "expected": (
                "Promotional notification is NOT delivered to this user. Other categories "
                "(e.g., 'Social Activity') still deliver if toggled ON. Dispatch log shows "
                "'filtered: category=promotions, user_pref=false'."
            ),
        },
        {
            "tc_id": "TC-014-G02",
            "description": "Verify 'Order Updates' toggle is locked ON.",
            "test_type": "Functional",
            "steps": (
                "1. Navigate to Notification Settings.\n"
                "2. Observe the 'Order Updates' toggle.\n"
                "3. Send PATCH /user/preferences/notifications with {\"order_updates\": false}."
            ),
            "expected": (
                "UI: toggle is ON and visually disabled. Tooltip on hover: 'Transactional "
                "notifications cannot be disabled.' API: HTTP 422 with message "
                "'order_updates cannot be disabled.' Preference remains true."
            ),
        },
        {
            "tc_id": "TC-014-G03",
            "description": "Verify quiet hours defer non-critical notifications.",
            "test_type": "Functional",
            "steps": (
                "1. Set quiet hours: 22:00–07:00, timezone America/New_York.\n"
                "2. At 23:00 EST, trigger a promotional notification for this user.\n"
                "3. Check device at 23:05 and then at 07:01."
            ),
            "expected": (
                "At 23:05: no notification delivered on device. At 07:01: notification "
                "arrives (delivered from deferred queue). Order update notifications "
                "still deliver immediately (bypass quiet hours)."
            ),
        },
        {
            "tc_id": "TC-014-G04",
            "description": "Verify cross-device sync of notification preferences.",
            "test_type": "Functional",
            "steps": (
                "1. Log in on Device A (mobile) and Device B (desktop).\n"
                "2. On Device A, toggle 'Social Activity' to OFF.\n"
                "3. Within 5 seconds, observe Device B's Notification Settings screen."
            ),
            "expected": (
                "Device B reflects the updated preference within 5 seconds without "
                "manual refresh. The toggle switch updates in real-time via WebSocket/SSE. "
                "API confirms the change was persisted server-side."
            ),
        },
        {
            "tc_id": "TC-014-G05",
            "description": "Verify new user gets default preferences (all enabled, no quiet hours).",
            "test_type": "Functional",
            "steps": (
                "1. Register a brand-new user account.\n"
                "2. Log in and navigate to Notification Settings.\n"
                "3. Query the database directly for the preferences record."
            ),
            "expected": (
                "All 5 category toggles are ON. Quiet hours are unset. Database record "
                "confirms all boolean fields are true. User receives notifications for "
                "all categories until they change preferences."
            ),
        },
    ], indent=2),

    # ── US-015: Automated Invoice Generation (Finance / Billing) ────────
    ("US-015", "frs_few_shot"): (
        "FR-300: The system shall have a scheduled cron job (0 2 1 * *) that queries "
        "all active subscriptions from the billing database and enqueues an invoice "
        "generation task for each subscription to the background job queue.\n"
        "FR-301: Each invoice generation task shall compute line items from the "
        "subscription's usage records for the previous billing period (start_date to "
        "end_date), apply the customer's jurisdiction tax rate, and compute "
        "subtotal, tax_amount, and total.\n"
        "FR-302: Invoice numbers shall be generated atomically using a PostgreSQL "
        "sequence; format: INV-{YYYYMM}-{5-digit zero-padded sequence}, e.g., "
        "INV-202607-00001.\n"
        "FR-303: The system shall render the invoice as a PDF using a templating "
        "engine (Gotenberg or equivalent); the PDF shall include: company logo, "
        "invoice number, billing period dates, line items table (description, "
        "quantity, unit_price, total), subtotal, tax, grand total, payment due date "
        "(net-30 from invoice date).\n"
        "FR-304: Generated PDFs shall be stored in durable object storage (S3) and "
        "linked to the invoice record via an invoice_files table; the system shall "
        "send a transactional email with the PDF as a base64 attachment or via a "
        "presigned download URL valid for 30 days.\n"
        "FR-305: Failed invoice generation shall be retried by the job framework with "
        "exponential backoff (1 minute, 5 minutes, 15 minutes); after the 3rd failure, "
        "an incident shall be created via the PagerDuty/Opsgenie integration and the "
        "invoice status shall be set to 'failed'.\n"
        "FR-306: Ad-hoc invoice generation shall be triggered via "
        "POST /invoices/generate with a subscription_id parameter, restricted to users "
        "with the 'finance:invoice' permission; the generated invoice shall carry "
        "source='manual'."
    ),
    ("US-015", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-015-G01",
            "description": "Verify scheduled monthly invoice generation for active subscriptions.",
            "test_type": "Functional",
            "steps": (
                "1. Seed the database with 5 active subscriptions and usage records for "
                "the previous month.\n"
                "2. Advance the system clock to the 1st of the next month at 02:00.\n"
                "3. Monitor the job queue and observe invoice generation.\n"
                "4. Inspect generated invoices and emails."
            ),
            "expected": (
                "5 invoices generated with sequential numbers INV-202608-00001 through "
                "INV-202608-00005. Each PDF correctly itemizes usage. 5 emails sent "
                "with PDF attachments. Invoice records in database with status 'sent'."
            ),
        },
        {
            "tc_id": "TC-015-G02",
            "description": "Verify invoice number uniqueness and sequence continuity.",
            "test_type": "Functional",
            "steps": (
                "1. Generate 15 invoices in the same month.\n"
                "2. Query invoice_numbers from the database.\n"
                "3. Cross-check for duplicates or gaps."
            ),
            "expected": (
                "Numbers run contiguously: INV-202607-00001 through INV-202607-00015. "
                "No duplicates. No gaps. The PostgreSQL sequence increments atomically "
                "even under concurrent generation."
            ),
        },
        {
            "tc_id": "TC-015-G03",
            "description": "Verify PDF contains all required fields with accurate calculations.",
            "test_type": "Functional",
            "steps": (
                "1. Generate an invoice for a subscription with: base $200 + usage $45.\n"
                "2. Tax rate for the jurisdiction is 8%.\n"
                "3. Open the generated PDF."
            ),
            "expected": (
                "PDF displays: Line items ($200 + $45), subtotal $245, tax $19.60, "
                "total $264.60. Due date is 30 days from invoice date. Company logo and "
                "branding present. Customer billing address and invoice number visible."
            ),
        },
        {
            "tc_id": "TC-015-G04",
            "description": "Verify retry and alerting after 3 consecutive generation failures.",
            "test_type": "Reliability",
            "steps": (
                "1. Configure the PDF rendering service to return HTTP 500 for a specific "
                "subscription.\n"
                "2. Trigger invoice generation.\n"
                "3. Observe the job retry behavior.\n"
                "4. Monitor PagerDuty/Opsgenie after the 3rd failure."
            ),
            "expected": (
                "Job retries at 1 min, 5 min, and 15 min intervals. After the 3rd "
                "failure, invoice status → 'failed'. PagerDuty/Opsgenie alert fired "
                "with subscription_id and error details. No further retries. Finance "
                "team notified to manually process."
            ),
        },
        {
            "tc_id": "TC-015-G05",
            "description": "Verify ad-hoc invoice generation by finance team member.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as a user with 'finance:invoice' permission.\n"
                "2. POST /invoices/generate with {\"subscription_id\": \"SUB-789\"}.\n"
                "3. Observe the generated invoice and email delivery."
            ),
            "expected": (
                "Invoice generated and sent immediately without waiting for the monthly "
                "schedule. Invoice carries source='manual'. Invoice number follows "
                "standard sequence. Email dispatched. Appears in invoice history."
            ),
        },
        {
            "tc_id": "TC-015-G06",
            "description": "Verify unauthorized user cannot trigger ad-hoc generation.",
            "test_type": "Security",
            "steps": (
                "1. Log in as a regular user without 'finance:invoice' permission.\n"
                "2. Send POST /invoices/generate with a valid subscription_id.\n"
                "3. Observe the HTTP response."
            ),
            "expected": (
                "HTTP 403 Forbidden. Response: { error: 'Forbidden', required_permission: "
                "'finance:invoice' }. No invoice created. Audit log records the "
                "unauthorized attempt."
            ),
        },
    ], indent=2),

    # ── US-016: Rate Limiting (Platform / Infrastructure) ────────────────
    ("US-016", "frs_few_shot"): (
        "FR-310: The system shall implement a rate-limiting middleware using the "
        "sliding-window algorithm with Redis sorted sets, keyed by user_id:endpoint, "
        "to enforce per-user request quotas across a distributed API gateway cluster.\n"
        "FR-311: The default rate limit shall be 100 requests per rolling 60-second "
        "window per user; endpoint-specific overrides shall be configurable via a "
        "rate_limits configuration table supporting per-endpoint and per-tier limits.\n"
        "FR-312: When a request exceeds the rate limit, the middleware shall respond "
        "with HTTP 429 Too Many Requests and a Retry-After header indicating the "
        "number of seconds until the window resets; the response body shall include "
        "{\"error\": \"rate_limit_exceeded\", \"retry_after\": <seconds>}.\n"
        "FR-313: Every API response shall include the following rate-limit headers: "
        "X-RateLimit-Limit (int), X-RateLimit-Remaining (int), X-RateLimit-Reset (Unix "
        "epoch seconds).\n"
        "FR-314: Rate limit consumption shall be atomic in a distributed environment "
        "using a Redis Lua script (EVAL) that atomically trims expired entries from "
        "the sorted set, counts current-window entries, adds the new request timestamp, "
        "and returns remaining count — all in one atomic operation.\n"
        "FR-315: When a user exceeds 80% of their rate limit, a warning event shall be "
        "emitted to the monitoring system; when the limit is fully exhausted, an abuse "
        "event shall be published to the security event pipeline for potential automated "
        "response.\n"
        "FR-316: Administrative endpoints (GET /admin/rate-limits, POST /admin/rate-limits) "
        "shall allow viewing current rate limit configurations and temporarily overriding "
        "limits for specific users or IP addresses; access restricted to users with the "
        "'admin:rate_limits' permission."
    ),
    ("US-016", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-016-G01",
            "description": "Verify rate limit enforced at 100 RPM with HTTP 429 response.",
            "test_type": "Functional",
            "steps": (
                "1. Send 100 authenticated requests to /api/resource within 60 seconds.\n"
                "2. Send the 101st request immediately after.\n"
                "3. Inspect the response headers and body."
            ),
            "expected": (
                "Requests 1–100 succeed with HTTP 2xx/4xx. 101st returns HTTP 429. "
                "Response body: {error: 'rate_limit_exceeded', retry_after: <N>}. "
                "Retry-After header present. X-RateLimit-Remaining = 0."
            ),
        },
        {
            "tc_id": "TC-016-G02",
            "description": "Verify sliding-window allows requests after old entries age out.",
            "test_type": "Functional",
            "steps": (
                "1. Send 80 requests at t=0s.\n"
                "2. Wait until t=61s (old entries slide out of the 60s window).\n"
                "3. Send 50 more requests."
            ),
            "expected": (
                "At t=0s: 80 requests succeed, X-RateLimit-Remaining = 20.\n"
                "At t=61s+: 50 requests succeed. The first 80 have aged out of the "
                "sliding window. Remaining count reflects only the 50 new entries."
            ),
        },
        {
            "tc_id": "TC-016-G03",
            "description": "Verify endpoint-specific rate limit overrides default.",
            "test_type": "Functional",
            "steps": (
                "1. Configure /api/search limit = 30 RPM in the rate_limits table.\n"
                "2. Send 30 requests to /api/search.\n"
                "3. Send 31st request to /api/search and 1 request to /api/profile."
            ),
            "expected": (
                "31st /api/search request returns HTTP 429 (limit 30). Request to "
                "/api/profile succeeds (still at 1/100). Endpoint-specific configuration "
                "overrides the global default without side effects on other endpoints."
            ),
        },
        {
            "tc_id": "TC-016-G04",
            "description": "Verify rate limit isolation between different users/api keys.",
            "test_type": "Functional",
            "steps": (
                "1. User A exhausts their rate limit (100 RPM).\n"
                "2. User B (with a different API key) sends requests to the same endpoint."
            ),
            "expected": (
                "User A: 101st request returns HTTP 429. User B: requests succeed "
                "normally. Rate limits are keyed by user_id, not globally. Redis keys "
                "include user_id in their prefix."
            ),
        },
        {
            "tc_id": "TC-016-G05",
            "description": "Verify rate-limit response headers are present on every response.",
            "test_type": "Functional",
            "steps": (
                "1. Send a single request to any API endpoint.\n"
                "2. Inspect the response headers.\n"
                "3. Send a second request and compare header values."
            ),
            "expected": (
                "Headers present: X-RateLimit-Limit (e.g., 100), X-RateLimit-Remaining "
                "(e.g., 99), X-RateLimit-Reset (Unix timestamp). Remaining decrements "
                "by 1 on the second request. All values are integers."
            ),
        },
    ], indent=2),

    # ── US-017: GDPR Data Export (Data Privacy / Compliance) ────────────
    ("US-017", "frs_few_shot"): (
        "FR-320: The system shall provide POST /privacy/export-request that initiates "
        "a GDPR data portability workflow for the authenticated user, creating an "
        "export job with status 'pending_confirmation'.\n"
        "FR-321: After receiving the request, the system shall send a confirmation "
        "email containing a unique, time-limited verification link (JWT, TTL 1 hour); "
        "the export process shall not begin until the user clicks the verification link "
        "and the token is validated.\n"
        "FR-322: The export worker shall query all data stores associated with the user "
        "ID: profile (users table), orders (orders + order_items), payment history "
        "(masked PAN only), product reviews, support tickets, login history (audit_logs), "
        "and consent records (consent_ledger).\n"
        "FR-323: Collected data shall be serialized into a structured JSON document "
        "conforming to a versioned schema where each entity is a top-level key "
        "(profile, orders, payments, reviews, tickets, logins, consents) containing "
        "an array of records with all available fields.\n"
        "FR-324: The JSON file shall be compressed (gzip, .json.gz) and uploaded to "
        "encrypted object storage (S3 SSE-KMS, AES-256); a presigned download URL "
        "shall be generated with a 7-day validity and single-use constraint.\n"
        "FR-325: Export status shall be queryable via GET /privacy/export-requests "
        "returning { status: pending_confirmation|in_progress|completed|failed, "
        "progress_percent: int, created_at, completed_at, download_url_expires_at }.\n"
        "FR-326: The completed notification email shall include the presigned download "
        "link, the expiration date, and instructions for opening the gzipped JSON file.\n"
        "FR-327: The account deletion endpoint POST /privacy/delete-account shall "
        "initiate a workflow: immediately soft-delete the account (status=pending_deletion, "
        "data retained for 30 days), provide a reactivation link, then permanently "
        "anonymize or delete all PII after 30 days. Anonymized records shall replace "
        "name, email, phone with irreversible hashes."
    ),
    ("US-017", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-017-G01",
            "description": "Verify full GDPR export workflow from request to download.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as a user with extensive data history.\n"
                "2. Go to Privacy Settings → 'Request Data Export'.\n"
                "3. Open the confirmation email and click the verification link.\n"
                "4. Wait for the export job to complete (poll status endpoint).\n"
                "5. Click the download link in the completion email.\n"
                "6. Unzip and inspect the JSON file."
            ),
            "expected": (
                "Status transitions: pending_confirmation → in_progress → completed. "
                "JSON contains all data categories: profile, orders, payments (masked), "
                "reviews, tickets, logins, consents. All records accurate and complete. "
                "No other user's data present. Download link single-use only."
            ),
        },
        {
            "tc_id": "TC-017-G02",
            "description": "Verify export does not start without email confirmation.",
            "test_type": "Security",
            "steps": (
                "1. Request a data export.\n"
                "2. Do NOT click the email verification link.\n"
                "3. Wait 30 minutes and check the export status.\n"
                "4. After 1 hour, the verification link expires — attempt to use it."
            ),
            "expected": (
                "Status remains 'pending_confirmation'. No background job started. "
                "No data collected or compressed. After 1 hour: expired link shows "
                "'Verification link has expired. Please submit a new request.' "
                "Only the verified email owner can trigger the export."
            ),
        },
        {
            "tc_id": "TC-017-G03",
            "description": "Verify download link expires after 7 days.",
            "test_type": "Functional",
            "steps": (
                "1. Complete a data export.\n"
                "2. Advance the system clock by 8 days.\n"
                "3. Attempt to download using the original presigned URL."
            ),
            "expected": (
                "Error: 'This download link has expired. Please submit a new export request.' "
                "S3 presigned URL returns HTTP 403 AccessDenied. No data served."
            ),
        },
        {
            "tc_id": "TC-017-G04",
            "description": "Verify 72-hour GDPR SLA is tracked and breaches are alerted.",
            "test_type": "Functional",
            "steps": (
                "1. Confirm an export request.\n"
                "2. Monitor the status tracker showing elapsed time.\n"
                "3. Simulate the export job taking > 72 hours to complete.\n"
                "4. Check the DPO dashboard and alerting system."
            ),
            "expected": (
                "Status tracker displays elapsed time since confirmation. At 72h, SLA "
                "breach alert triggered to DPO dashboard with user_id, request_id, and "
                "elapsed time. The job still completes when resources are available, "
                "but the breach is permanently recorded in the compliance audit log."
            ),
        },
        {
            "tc_id": "TC-017-G05",
            "description": "Verify account deletion with 30-day reversal window.",
            "test_type": "Functional",
            "steps": (
                "1. Request account deletion via Privacy Settings.\n"
                "2. Confirm via email verification link.\n"
                "3. Within 30 days: try to log in.\n"
                "4. Click the 'Reactivate Account' link from the warning email.\n"
                "5. After 30+ days: verify PII is permanently anonymized."
            ),
            "expected": (
                "Within 30 days: login redirects to 'Account scheduled for deletion' "
                "with reactivation option. Reactivation restores full access, PII intact. "
                "After 30 days: user record shows name='ANONYMIZED_XXXXX', "
                "email='deleted+XXXXX@anonymous.example', phone=NULL. "
                "Orders and transactions are retained for legal reasons but all PII "
                "columns are irreversibly hashed."
            ),
        },
    ], indent=2),

    # ── US-018: Dark Mode Toggle (UI/UX) ────────────────────────────────
    ("US-018", "frs_few_shot"): (
        "FR-330: The system shall support three theme modes: 'light', 'dark', and "
        "'system' (auto-detect via the prefers-color-scheme CSS media query); the "
        "default for new/unauthenticated users shall be 'system'.\n"
        "FR-331: The theme toggle shall be accessible as a segmented control or radio "
        "group in the user dropdown menu and on the dedicated Settings → Appearance page.\n"
        "FR-332: On theme change, the client shall set a data-theme attribute ('light' "
        "or 'dark') on the <html> element and update all CSS custom properties "
        "(e.g., --bg-primary, --text-primary) from the :root and [data-theme='dark'] "
        "selector blocks.\n"
        "FR-333: The client shall listen for the prefers-color-scheme media query "
        "change event (window.matchMedia listener) and dynamically switch the theme in "
        "real time when the mode is set to 'system', without requiring a page reload.\n"
        "FR-334: For authenticated users, the theme preference shall be persisted via "
        "PATCH /user/preferences { theme: 'light'|'dark'|'system' } and restored "
        "during SSR/initial render to prevent a flash of incorrect theme (FOIT).\n"
        "FR-335: For unauthenticated users, the preference shall be stored in "
        "localStorage under key 'app-theme' and applied on the client before the first "
        "paint via an inline <script> block in the <head>.\n"
        "FR-336: Color transitions between themes shall use CSS transition on "
        "background-color and color properties with duration 300ms and easing ease-in-out "
        "for a smooth visual handoff; all UI components (buttons, modals, tables, forms, "
        "charts) must define both light and dark color tokens."
    ),
    ("US-018", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-018-G01",
            "description": "Verify dark mode toggle applies correctly across all pages.",
            "test_type": "Functional",
            "steps": (
                "1. Log in as an authenticated user.\n"
                "2. Navigate to Settings → Appearance.\n"
                "3. Select 'Dark' mode.\n"
                "4. Navigate to Dashboard, Reports, Profile, and Settings pages."
            ),
            "expected": (
                "All pages render in dark color palette: dark background (#1a1a2e or "
                "similar), light text, appropriately darkened table rows, form inputs, "
                "modals, and buttons. No white flash or partially themed components. "
                "Charts and data visualizations adjust their color scheme."
            ),
        },
        {
            "tc_id": "TC-018-G02",
            "description": "Verify 'System' mode follows OS-level theme changes in real time.",
            "test_type": "Functional",
            "steps": (
                "1. Set theme to 'System'.\n"
                "2. Switch the OS appearance from Light to Dark.\n"
                "3. Observe the application.\n"
                "4. Switch OS back to Light."
            ),
            "expected": (
                "Application theme changes dynamically to Dark when OS switches, then "
                "back to Light. Transition happens within 1 second of OS change. No page "
                "reload required. The segmented control remains on 'System' throughout."
            ),
        },
        {
            "tc_id": "TC-018-G03",
            "description": "Verify theme preference persists across logout/login sessions.",
            "test_type": "Functional",
            "steps": (
                "1. Log in, set theme to 'Dark'.\n"
                "2. Log out.\n"
                "3. Close the browser completely.\n"
                "4. Reopen the browser and log in again."
            ),
            "expected": (
                "Application loads in dark mode from the persisted user preference. "
                "No flash of light theme (SSR sends the correct data-theme attribute). "
                "The theme toggle reflects 'Dark' as the active selection."
            ),
        },
        {
            "tc_id": "TC-018-G04",
            "description": "Verify logged-out user sees theme based on localStorage.",
            "test_type": "Functional",
            "steps": (
                "1. As a logged-out user, navigate to the marketing homepage.\n"
                "2. Open the theme toggle in the header and select 'Dark'.\n"
                "3. Reload the page.\n"
                "4. Check localStorage value for 'app-theme'."
            ),
            "expected": (
                "Marketing page renders in dark mode after reload. localStorage "
                "'app-theme' = 'dark'. No theme flash on reload. Theme persists even "
                "for unauthenticated sessions."
            ),
        },
        {
            "tc_id": "TC-018-G05",
            "description": "Verify smooth CSS transition animates theme switch.",
            "test_type": "Functional",
            "steps": (
                "1. Open the application in light mode.\n"
                "2. Toggle to dark mode.\n"
                "3. Record a performance profile or visually inspect the transition."
            ),
            "expected": (
                "Background-color and color properties animate smoothly over ~300ms. "
                "No jarring flash or instantaneous jump. Transition easing is visible. "
                "All visible elements participate in the transition."
            ),
        },
    ], indent=2),

    # ── US-019: Two-Way SMS Customer Support (Customer Support) ─────────
    ("US-019", "frs_few_shot"): (
        "FR-340: The system shall integrate with a telephony API (Twilio/MessageBird) "
        "by registering a webhook endpoint POST /webhooks/sms/inbound that receives "
        "incoming SMS messages with fields: From (phone number), To (support number), "
        "Body (text), and optional MediaUrl array.\n"
        "FR-341: On first inbound message from an unknown number, the system shall "
        "look up the customer by phone number in the contacts table; if not found, "
        "create a provisional contact record with phone number and timestamp, flagged "
        "as 'unverified'.\n"
        "FR-342: The system shall create (or append to) a support ticket/case linked "
        "to the customer contact; a unique case number shall be generated (format "
        "CS-{6-digit sequence}) and returned to the customer in an auto-reply SMS "
        "acknowledging receipt.\n"
        "FR-343: Incoming SMS messages shall be pushed to the agent dashboard in "
        "real-time via WebSocket/SSE; the agent chat UI shall render a threaded "
        "conversation view with customer name, phone number (masked last 4 digits), "
        "message bubbles, and timestamps.\n"
        "FR-344: Agent outbound messages typed in the dashboard shall be sent via "
        "POST to the telephony API's Messages resource to deliver as SMS to the "
        "customer's phone number; the sent message shall be appended to the "
        "conversation thread in real time.\n"
        "FR-345: Inbound MMS media URLs (images) shall be downloaded by the server, "
        "scanned for malware using ClamAV or an equivalent service, and stored in "
        "the case attachments storage; the agent UI shall render images inline with "
        "a click-to-enlarge overlay.\n"
        "FR-346: A scheduled job (every 5 minutes) shall check business hours "
        "(configurable per location in the business_hours table); messages received "
        "outside operating hours shall receive an auto-reply containing the business "
        "hours schedule and remain in the 'open' queue with the SLA clock paused "
        "until the next business day start."
    ),
    ("US-019", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-019-G01",
            "description": "Verify inbound SMS creates case, auto-reply, and appears in agent dashboard.",
            "test_type": "Functional",
            "steps": (
                "1. From a test phone (+1-555-0100), send SMS 'My order #1234 is missing' "
                "to the support number.\n"
                "2. Check the phone for auto-reply.\n"
                "3. Open the agent dashboard and locate the new conversation."
            ),
            "expected": (
                "Auto-reply SMS received within 10 seconds: 'Thanks for contacting us! "
                "Your case #CS-789012 has been created.' Agent dashboard shows a new "
                "thread with the message, customer phone (masked as +1-555-0100), and "
                "a linked customer profile if the number is recognized."
            ),
        },
        {
            "tc_id": "TC-019-G02",
            "description": "Verify agent reply delivered as SMS to customer's phone.",
            "test_type": "Functional",
            "steps": (
                "1. In the agent dashboard, open the active conversation for +1-555-0100.\n"
                "2. Type 'Let me check your order #1234 right away.'\n"
                "3. Click 'Send'.\n"
                "4. Check the customer's phone."
            ),
            "expected": (
                "Customer's phone receives SMS from the support number with the agent's "
                "message. Agent dashboard thread updates to show the sent message as an "
                "outgoing bubble. Timestamp accurate. No duplicate message sent."
            ),
        },
        {
            "tc_id": "TC-019-G03",
            "description": "Verify existing customer profile is linked on recognized phone number.",
            "test_type": "Functional",
            "steps": (
                "1. Customer Jane Doe (registered with phone +1-555-0100) sends an SMS.\n"
                "2. Agent opens the conversation and inspects the sidebar."
            ),
            "expected": (
                "Agent sidebar shows Jane Doe's full profile: name, email, loyalty tier, "
                "recent orders, past support tickets. Conversation is automatically "
                "linked to the existing customer record (not duplicated as a new contact)."
            ),
        },
        {
            "tc_id": "TC-019-G04",
            "description": "Verify MMS image is displayed inline for the agent.",
            "test_type": "Functional",
            "steps": (
                "1. From the test phone, send an MMS with a photo of a damaged product "
                "to the support number.\n"
                "2. Open the conversation in the agent dashboard.\n"
                "3. Click the image thumbnail."
            ),
            "expected": (
                "Image appears inline in the chat thread as a thumbnail. Clicking "
                "opens a full-size overlay. Image is stored in case attachments. "
                "Malware scan passed (log shows 'clean' result). Image is accessible "
                "for the case lifetime."
            ),
        },
        {
            "tc_id": "TC-019-G05",
            "description": "Verify after-hours auto-reply with SLA clock pause.",
            "test_type": "Functional",
            "steps": (
                "1. Set business hours to 08:00–20:00 EST.\n"
                "2. Send an SMS at 23:00 EST.\n"
                "3. Check the auto-reply and the case in the agent dashboard at 08:01 EST."
            ),
            "expected": (
                "Auto-reply: 'Our support team is currently offline. Business hours are "
                "8 AM–8 PM EST, Mon–Fri. We'll respond first thing in the morning. "
                "Case #CS-789013.' In dashboard: case status 'open', SLA clock shows "
                "0h 0m elapsed (paused during off-hours). At 08:01 EST, SLA clock "
                "starts ticking. Agent sees the case in the morning queue."
            ),
        },
    ], indent=2),

    # ── US-020: Automated Regression Suite on PR (DevOps / QA) ──────────
    ("US-020", "frs_few_shot"): (
        "FR-350: The CI/CD pipeline configuration shall define a 'regression' job "
        "triggered on pull_request events (opened, synchronize, reopened) targeting "
        "the main branch; the job shall be a required status check enforced by branch "
        "protection rules.\n"
        "FR-351: The test runner shall distribute tests across N parallel shards "
        "(default 10) using a consistent hashing strategy (test file path modulo N) "
        "to balance execution time; shard execution status shall be reported "
        "independently.\n"
        "FR-352: Test results shall be output in JUnit XML format and published as "
        "a CI pipeline artifact; a summary comment shall be created on the pull "
        "request via the SCM API (GitHub/GitLab/Bitbucket REST API) containing: "
        "total tests, passed, failed, skipped counts, execution duration, and a link "
        "to the full CI run.\n"
        "FR-353: Branch protection rules shall be configured so that the 'regression' "
        "status check must pass before merge; the SCM shall enforce this blocking via "
        "its native branch protection feature, preventing the merge button from being "
        "enabled until the check passes.\n"
        "FR-354: The system shall implement flaky test detection by tracking per-test "
        "outcomes across the last 10 CI runs; a test that passed on retry but failed "
        "on initial execution in ≥ 3 of the last 10 runs shall be flagged as 'flaky'.\n"
        "FR-355: Flagged flaky tests shall be automatically moved from the main test "
        "suite to a quarantine suite (excluded from the merge-blocking check); an "
        "auto-created issue shall be filed in the project backlog with the test name, "
        "file path, and flaky score.\n"
        "FR-356: All test artifacts (JUnit XML reports, screenshots, logs, video "
        "recordings) shall be retained in CI storage (artifact repository) for 30 days; "
        "after 30 days, artifacts shall be automatically purged."
    ),
    ("US-020", "tc_few_shot"): json.dumps([
        {
            "tc_id": "TC-020-G01",
            "description": "Verify regression suite triggers automatically on PR creation.",
            "test_type": "Functional",
            "steps": (
                "1. Create a feature branch with a code change.\n"
                "2. Open a PR against the main branch.\n"
                "3. Observe the CI pipeline execution.\n"
                "4. Check the PR for the automated test results comment."
            ),
            "expected": (
                "'regression' job starts automatically within seconds of PR creation. "
                "All 10 shards execute in parallel. PR receives a comment: 'Regression "
                "Suite — 1,850 passed, 0 failed, 5 skipped. [View Full Report]'. "
                "Status check shows green checkmark on the PR."
            ),
        },
        {
            "tc_id": "TC-020-G02",
            "description": "Verify merge is blocked when regression tests fail.",
            "test_type": "Functional",
            "steps": (
                "1. Create a PR with a change that causes a test assertion failure.\n"
                "2. Wait for CI to complete.\n"
                "3. Attempt to merge the PR via the UI and via API."
            ),
            "expected": (
                "Merge button is grayed out with tooltip: 'Required status check "
                "'regression' is failing.' API merge attempt returns HTTP 405 or "
                "similar with message indicating branch protection rules block the merge. "
                "Only after fixing the test and getting a green CI run can the PR be merged."
            ),
        },
        {
            "tc_id": "TC-020-G03",
            "description": "Verify flaky test detection and quarantine flow.",
            "test_type": "Functional",
            "steps": (
                "1. Create a test that passes 70% of the time (nondeterministic failure).\n"
                "2. Run the PR CI pipeline 10 times.\n"
                "3. After the 3rd flaky occurrence, observe the test status.\n"
                "4. Check the issue tracker for an auto-created ticket."
            ),
            "expected": (
                "After 3 flaky failures in the last 10 runs, test is flagged in CI "
                "output as 'FLAKY: spec/models/user_spec.rb:42'. Test is moved to "
                "quarantine suite (excluded from merge-blocking check). A new issue is "
                "auto-created in the backlog with title 'Flaky test: user_spec.rb:42' "
                "and the flaky score. Subsequent PRs are not blocked by this test."
            ),
        },
        {
            "tc_id": "TC-020-G04",
            "description": "Verify test execution time SLA (≤ 30 min with 10 shards).",
            "test_type": "Performance",
            "steps": (
                "1. Run the full regression suite on a PR with 2,000 test cases.\n"
                "2. Measure total wall-clock duration from job start to completion.\n"
                "3. Check individual shard execution times."
            ),
            "expected": (
                "Total suite execution ≤ 30 minutes. No single shard exceeds 35 minutes "
                "(10% tolerance over the per-shard target of 3 minutes per 200 tests). "
                "CI job summary shows per-shard timing breakdown."
            ),
        },
        {
            "tc_id": "TC-020-G05",
            "description": "Verify test artifacts are archived and retrievable for 30 days.",
            "test_type": "Functional",
            "steps": (
                "1. Run the regression suite on a PR.\n"
                "2. Download the CI artifacts (JUnit XML, screenshots, logs).\n"
                "3. Advance the clock by 15 days → verify artifacts are still downloadable.\n"
                "4. Advance by 31 days → verify artifacts are purged."
            ),
            "expected": (
                "Day 0: All artifacts downloadable. Day 15: all artifacts still "
                "available. Day 31: artifacts return 404 or 'expired'. The retention "
                "policy correctly enforces the 30-day TTL."
            ),
        },
    ], indent=2),
}


