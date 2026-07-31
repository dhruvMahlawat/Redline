"""
Generates the small set of test leases used by eval/run_eval.py.
Run once (or whenever fixtures need to change): python3 eval/generate_fixtures.py

Each one is designed to test something specific - see the comment above each.
"""
import fitz


def make_pdf(path: str, text: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=10)
    doc.save(path)


# straightforward, numbered clauses, no red flags - the baseline case
make_pdf("eval/fixtures/lease_01_numbered_clean.pdf", """
RESIDENTIAL LEASE AGREEMENT

1. Term
This lease begins January 1, 2026 and ends December 31, 2026.

2. Rent
Tenant agrees to pay $1,800 per month, due on the 1st.

3. Security Deposit
Tenant shall pay a security deposit of $1,800, refundable within 21 days of move-out.

4. Renewal
This lease shall automatically renew for successive one-year terms unless either party
provides written notice of non-renewal at least 60 days before the term ends.
""")

# same content, but unnumbered headings - tests the fallback clause splitter
make_pdf("eval/fixtures/lease_02_unnumbered_clean.pdf", """
Residential Lease Agreement

Term
This lease begins March 1, 2026 and ends February 28, 2027.

Rent
Tenant agrees to pay $2,100 per month, due on the 1st.

Security Deposit
Tenant shall pay a security deposit of $2,100, refundable within 30 days of move-out.

Renewal
This lease automatically renews for successive one-year terms unless either party gives
90 days written notice.
""")

# has two real, plantable red flags: a very short renewal notice window, and an
# unusual recurring fee that isn't rent or a utility
make_pdf("eval/fixtures/lease_03_red_flags.pdf", """
RESIDENTIAL LEASE AGREEMENT

1. Rent
Tenant agrees to pay $1,500 per month, due on the 1st.

2. Security Deposit
Tenant shall pay a security deposit of $1,500, refundable within 21 days of move-out.

3. Renewal
This lease shall automatically renew for successive one-year terms unless either party
provides written notice of non-renewal at least 5 days before the term ends.

4. Fees
Tenant shall pay a monthly "administrative convenience fee" of $85 in addition to rent,
due alongside the monthly rent payment.
""")

# blank/unfilled template - tests that the model does NOT invent values for
# fields that are genuinely empty
make_pdf("eval/fixtures/lease_04_blank_template.pdf", """
RESIDENTIAL LEASE AGREEMENT TEMPLATE

1. Rent
Monthly Rent: $________ Due on: ____ day of each month.

2. Security Deposit
Deposit Amount: $________.

3. Renewal
This lease shall automatically renew unless either party provides written notice of
non-renewal at least ____ days before the term ends.
""")

# label-value-on-one-line layout, same shape as the doc that exposed the
# clause-splitting bug earlier - guards against that regressing
make_pdf("eval/fixtures/lease_05_label_value_layout.pdf", """
RESIDENTIAL LEASE AGREEMENT
Landlord Jane Doe
Tenant John Smith
Monthly Rent $1,350
Security Deposit $1,350
Notice Period 45 days
""")

print("fixtures generated in eval/fixtures/")
