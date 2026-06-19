"""
FinAgent Demo Seed Data
Run this script to populate the database with realistic demo data.

Usage:
    python scripts/seed_data.py
"""

import asyncio
import httpx

API_BASE = "http://localhost:8000/api/v1"


# ── Demo Vendors ──────────────────────────────────────────────────────────────
VENDORS = [
    {
        "name": "TechFlow Solutions",
        "email": "billing@techflow.com",
        "tax_id": "TAX-TF-001",
        "payment_terms_days": 30,
        "categories": ["software", "cloud-services"]
    },
    {
        "name": "CloudBase Infrastructure",
        "email": "invoices@cloudbase.io",
        "tax_id": "TAX-CB-002",
        "payment_terms_days": 45,
        "categories": ["infrastructure", "hosting"]
    },
    {
        "name": "DataSync Analytics",
        "email": "accounts@datasync.com",
        "tax_id": "TAX-DS-003",
        "payment_terms_days": 30,
        "categories": ["analytics", "data"]
    },
    {
        "name": "SecureNet Consulting",
        "email": "billing@securenet.com",
        "tax_id": "TAX-SN-004",
        "payment_terms_days": 14,
        "categories": ["security", "consulting"]
    },
    {
        "name": "OfficeSupply Pro",
        "email": "orders@officesupply.com",
        "tax_id": "TAX-OS-005",
        "payment_terms_days": 30,
        "categories": ["supplies", "office"]
    },
]


# ── Demo Invoices ─────────────────────────────────────────────────────────────
INVOICES = [
    # TechFlow — normal invoices
    {
        "text": """INVOICE
From: TechFlow Solutions
Invoice Number: TF-2024-001
Date: 2024-01-15
Due Date: 2027-02-15
Items:
- Software License Enterprise x1 @ $2,500.00 = $2,500.00
- Support Package x1 @ $500.00 = $500.00
Total Due: $3,000.00"""
    },
    {
        "text": """INVOICE
From: TechFlow Solutions
Invoice Number: TF-2024-002
Date: 2024-02-10
Due Date: 2027-03-10
Items:
- Software License Enterprise x1 @ $2,500.00 = $2,500.00
- Additional Users x5 @ $100.00 = $500.00
Total Due: $3,000.00"""
    },
    # CloudBase — normal invoices
    {
        "text": """INVOICE
From: CloudBase Infrastructure
Invoice Number: CB-2024-001
Date: 2024-01-20
Due Date: 2027-03-05
Items:
- Cloud Hosting x3 months @ $800.00 = $2,400.00
- CDN Services x3 months @ $200.00 = $600.00
Total Due: $3,000.00"""
    },
    {
        "text": """INVOICE
From: CloudBase Infrastructure
Invoice Number: CB-2024-002
Date: 2024-02-20
Due Date: 2027-04-05
Items:
- Cloud Hosting x3 months @ $800.00 = $2,400.00
- Storage Upgrade x1 @ $400.00 = $400.00
Total Due: $2,800.00"""
    },
    # DataSync — normal invoice
    {
        "text": """INVOICE
From: DataSync Analytics
Invoice Number: DS-2024-001
Date: 2024-01-25
Due Date: 2027-02-25
Items:
- Analytics Platform License x1 @ $1,800.00 = $1,800.00
- Data Pipeline Setup x1 @ $700.00 = $700.00
Total Due: $2,500.00"""
    },
    # SecureNet — normal invoice
    {
        "text": """INVOICE
From: SecureNet Consulting
Invoice Number: SN-2024-001
Date: 2024-01-30
Due Date: 2027-02-13
Items:
- Security Audit x1 @ $3,500.00 = $3,500.00
- Penetration Testing x1 @ $1,500.00 = $1,500.00
Total Due: $5,000.00"""
    },
    # OfficeSupply — normal invoice
    {
        "text": """INVOICE
From: OfficeSupply Pro
Invoice Number: OS-2024-001
Date: 2024-02-01
Due Date: 2027-03-01
Items:
- Office Chairs x10 @ $250.00 = $2,500.00
- Standing Desks x5 @ $400.00 = $2,000.00
- Monitor Stands x10 @ $80.00 = $800.00
Total Due: $5,300.00"""
    },
    # Suspicious invoices — for demo anomaly detection
    {
        "text": """INVOICE
From: TechFlow Solutions
Invoice Number: TF-2024-009
Date: 2024-03-01
Due Date: 2027-04-01
Items:
- Enterprise Platform Upgrade x1 @ $10,000.00 = $10,000.00
Total Due: $10,000.00"""
    },
    {
        "text": """INVOICE
From: CloudBase Infrastructure
Invoice Number: CB-2024-009
Date: 2024-03-05
Due Date: 2027-04-05
Items:
- Emergency Infrastructure Scaling x1 @ $8,000.00 = $8,000.00
Total Due: $8,000.00"""
    },
]


# ── Main Seeder ───────────────────────────────────────────────────────────────

async def seed():
    print("🌱 FinAgent Demo Data Seeder")
    print("=" * 40)

    async with httpx.AsyncClient(timeout=60.0) as client:

        # Step 1 — Register vendors
        print("\n📋 Registering vendors...")
        vendor_ids = {}

        for vendor in VENDORS:
            try:
                response = await client.post(
                    f"{API_BASE}/vendors/",
                    json=vendor
                )
                if response.status_code == 200:
                    data = response.json()
                    vendor_ids[vendor["name"]] = data["id"]
                    print(f"  ✅ {vendor['name']}")
                elif response.status_code == 400:
                    print(f"  ⚠️  {vendor['name']} already exists — skipping")
                else:
                    print(f"  ❌ {vendor['name']} failed: {response.text}")
            except Exception as e:
                print(f"  ❌ {vendor['name']} error: {str(e)}")

        # Step 2 — Verify all vendors
        print("\n✅ Verifying vendors...")
        vendors_response = await client.get(f"{API_BASE}/vendors/")
        all_vendors = vendors_response.json()

        for vendor in all_vendors:
            if not vendor["is_verified"]:
                await client.patch(
                    f"{API_BASE}/vendors/{vendor['id']}",
                    json={"is_verified": True}
                )
                print(f"  ✅ Verified: {vendor['name']}")

        # Step 3 — Submit invoices
        print("\n📄 Submitting invoices...")
        for i, invoice in enumerate(INVOICES):
            try:
                response = await client.post(
                    f"{API_BASE}/invoices/text",
                    params={"raw_text": invoice["text"]}
                )
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    vendor = data.get("vendor_name", "unknown")
                    amount = data.get("amount", 0)
                    print(f"  ✅ Invoice {i+1}: {vendor} — ${amount} — {status}")
                else:
                    print(f"  ❌ Invoice {i+1} failed: {response.text}")
            except Exception as e:
                print(f"  ❌ Invoice {i+1} error: {str(e)}")

        # Step 4 — Final stats
        print("\n📊 Final Statistics")
        print("=" * 40)

        invoices_response = await client.get(f"{API_BASE}/invoices/?limit=100")
        invoices_data = invoices_response.json()
        print(f"Total invoices: {invoices_data.get('total', 0)}")

        queue_response = await client.get(f"{API_BASE}/queue/stats/summary")
        queue_data = queue_response.json()
        print(f"Pending review: {queue_data.get('pending_review', 0)}")
        print(f"Total amount pending: ${queue_data.get('total_amount_pending', 0):,.2f}")

        print("\n✅ Seeding complete!")
        print(f"🌐 Dashboard: http://localhost:8501")
        print(f"📚 API Docs:  http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(seed())