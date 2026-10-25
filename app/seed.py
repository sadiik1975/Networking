from datetime import date

from sqlalchemy.orm import Session

from app.geo import ZIP_CENTROIDS
from app.models_db import Lead, LeadStatus, ProjectScale, Trade

_SEED_LEADS = [
    dict(
        id="LEAD-1001",
        trade=Trade.ELECTRICAL,
        project_type="Commercial panel upgrade",
        description="200A service upgrade for a retail fit-out on a ground-floor commercial unit.",
        address_line1="145 W 27th St",
        zip_code="10001",
        issue_date=date(2026, 8, 12),
        estimated_value=48000.0,
        project_scale=ProjectScale.MEDIUM,
        permit_number="NYC-EL-2026-00931",
        status=LeadStatus.OPEN,
        contact_name="Dept. of Buildings - Manhattan",
        contact_phone="(212) 555-0110",
        contact_email="permits.manhattan@example-city.gov",
    ),
    dict(
        id="LEAD-1002",
        trade=Trade.ROOFING,
        project_type="Full roof replacement",
        description="Tear-off and replacement of a 12,000 sq ft flat commercial roof, TPO membrane.",
        address_line1="220 Livingston St",
        zip_code="11201",
        issue_date=date(2026, 9, 2),
        estimated_value=210000.0,
        project_scale=ProjectScale.LARGE,
        permit_number="NYC-RF-2026-04471",
        status=LeadStatus.OPEN,
        contact_name="Dept. of Buildings - Brooklyn",
        contact_phone="(718) 555-0142",
        contact_email="permits.brooklyn@example-city.gov",
    ),
    dict(
        id="LEAD-1003",
        trade=Trade.PLUMBING,
        project_type="Restaurant kitchen rough-in",
        description="New grease trap and kitchen rough-in plumbing for a 3,200 sq ft restaurant build-out.",
        address_line1="88 Hudson St",
        zip_code="07302",
        issue_date=date(2026, 8, 25),
        estimated_value=62000.0,
        project_scale=ProjectScale.MEDIUM,
        permit_number="JC-PL-2026-01187",
        status=LeadStatus.OPEN,
        contact_name="Jersey City Buildings Dept.",
        contact_phone="(201) 555-0176",
        contact_email="permits@jerseycity-example.gov",
    ),
    dict(
        id="LEAD-1004",
        trade=Trade.HVAC,
        project_type="Rooftop unit replacement",
        description="Replacement of two 10-ton rooftop HVAC units for an office building.",
        address_line1="1 Federal St",
        zip_code="02108",
        issue_date=date(2026, 9, 10),
        estimated_value=95000.0,
        project_scale=ProjectScale.LARGE,
        permit_number="BOS-HV-2026-00765",
        status=LeadStatus.OPEN,
        contact_name="Boston Inspectional Services",
        contact_phone="(617) 555-0198",
        contact_email="permits@boston-example.gov",
    ),
    dict(
        id="LEAD-1005",
        trade=Trade.GENERAL_CONTRACTING,
        project_type="Office fit-out",
        description="Tenant improvement build-out of 8,000 sq ft office space, new partitions and finishes.",
        address_line1="1201 F St NW",
        zip_code="20001",
        issue_date=date(2026, 9, 15),
        estimated_value=340000.0,
        project_scale=ProjectScale.LARGE,
        permit_number="DC-GC-2026-02290",
        status=LeadStatus.OPEN,
        contact_name="DC Dept. of Consumer & Regulatory Affairs",
        contact_phone="(202) 555-0133",
        contact_email="permits@dc-example.gov",
    ),
    dict(
        id="LEAD-1006",
        trade=Trade.SOLAR,
        project_type="Rooftop solar array",
        description="150kW commercial rooftop solar installation on a warehouse.",
        address_line1="500 W Peachtree St",
        zip_code="30303",
        issue_date=date(2026, 8, 30),
        estimated_value=180000.0,
        project_scale=ProjectScale.LARGE,
        permit_number="ATL-SL-2026-00512",
        status=LeadStatus.OPEN,
        contact_name="Atlanta Office of Buildings",
        contact_phone="(404) 555-0121",
        contact_email="permits@atlanta-example.gov",
    ),
    dict(
        id="LEAD-1007",
        trade=Trade.FLOORING,
        project_type="Commercial flooring replacement",
        description="Epoxy flooring installation for a 6,000 sq ft warehouse renovation.",
        address_line1="900 Biscayne Blvd",
        zip_code="33101",
        issue_date=date(2026, 9, 5),
        estimated_value=27000.0,
        project_scale=ProjectScale.SMALL,
        permit_number="MIA-FL-2026-00874",
        status=LeadStatus.OPEN,
        contact_name="Miami Building Dept.",
        contact_phone="(305) 555-0155",
        contact_email="permits@miami-example.gov",
    ),
    dict(
        id="LEAD-1008",
        trade=Trade.ELECTRICAL,
        project_type="EV charging station install",
        description="Installation of 8 Level-2 EV charging stations in a commercial parking garage.",
        address_line1="333 S Wabash Ave",
        zip_code="60601",
        issue_date=date(2026, 9, 18),
        estimated_value=54000.0,
        project_scale=ProjectScale.MEDIUM,
        permit_number="CHI-EL-2026-03321",
        status=LeadStatus.OPEN,
        contact_name="Chicago Dept. of Buildings",
        contact_phone="(312) 555-0187",
        contact_email="permits@chicago-example.gov",
    ),
    dict(
        id="LEAD-1009",
        trade=Trade.ROOFING,
        project_type="Storm damage re-roof",
        description="Insurance-approved re-roof of a 4,500 sq ft strip mall after storm damage.",
        address_line1="1500 Elm St",
        zip_code="75201",
        issue_date=date(2026, 9, 20),
        estimated_value=88000.0,
        project_scale=ProjectScale.MEDIUM,
        permit_number="DAL-RF-2026-01654",
        status=LeadStatus.OPEN,
        contact_name="Dallas Development Services",
        contact_phone="(214) 555-0169",
        contact_email="permits@dallas-example.gov",
    ),
    dict(
        id="LEAD-1010",
        trade=Trade.PLUMBING,
        project_type="Multi-unit repipe",
        description="Full repipe of a 24-unit residential building's domestic water lines.",
        address_line1="2100 16th St",
        zip_code="80202",
        issue_date=date(2026, 8, 28),
        estimated_value=132000.0,
        project_scale=ProjectScale.LARGE,
        permit_number="DEN-PL-2026-00998",
        status=LeadStatus.OPEN,
        contact_name="Denver Community Planning & Development",
        contact_phone="(303) 555-0144",
        contact_email="permits@denver-example.gov",
    ),
    dict(
        id="LEAD-1011",
        trade=Trade.REMODELING,
        project_type="Retail interior remodel",
        description="Interior remodel of a 5,000 sq ft retail storefront including new storefront glazing.",
        address_line1="1201 3rd Ave",
        zip_code="98101",
        issue_date=date(2026, 9, 8),
        estimated_value=115000.0,
        project_scale=ProjectScale.MEDIUM,
        permit_number="SEA-RM-2026-00432",
        status=LeadStatus.OPEN,
        contact_name="Seattle Dept. of Construction & Inspections",
        contact_phone="(206) 555-0129",
        contact_email="permits@seattle-example.gov",
    ),
    dict(
        id="LEAD-1012",
        trade=Trade.LANDSCAPING,
        project_type="Commercial site landscaping",
        description="Hardscape and landscaping build-out for a new corporate campus entrance.",
        address_line1="401 Congress Ave",
        zip_code="78701",
        issue_date=date(2026, 9, 12),
        estimated_value=41000.0,
        project_scale=ProjectScale.SMALL,
        permit_number="AUS-LS-2026-00287",
        status=LeadStatus.OPEN,
        contact_name="Austin Development Services Dept.",
        contact_phone="(512) 555-0163",
        contact_email="permits@austin-example.gov",
    ),
    dict(
        id="LEAD-1013",
        trade=Trade.GENERAL_CONTRACTING,
        project_type="Historic commercial renovation",
        description="Structural repairs and adaptive reuse work for a historic commercial building.",
        address_line1="35 High Street",
        zip_code="12601",
        issue_date=date(2026, 9, 22),
        estimated_value=175000.0,
        project_scale=ProjectScale.LARGE,
        permit_number="HV-GC-2026-00013",
        status=LeadStatus.OPEN,
        contact_name="Precision Contractor",
        contact_phone="(914) 456-6336",
        contact_email="contact@precisioncontractor.com",
        ownership_category="Minority-Owned",
        certification_details="NYS Minority-Owned Business Certified",
        source_url="https://www.precisioncontractor.com/",
    ),
]


def seed_if_empty(db: Session) -> None:
    if db.query(Lead).first() is not None:
        return

    for entry in _SEED_LEADS:
        zip_code = entry.pop("zip_code")
        lat, lon, city, state = ZIP_CENTROIDS[zip_code]
        contact_name = entry.pop("contact_name")
        contact_phone = entry.pop("contact_phone")
        contact_email = entry.pop("contact_email")
        ownership_category = entry.pop("ownership_category", "Unverified")
        certification_details = entry.pop(
            "certification_details", "No verified ownership certification provided"
        )
        source_url = entry.pop("source_url", None)
        municipal_source_url = f"https://permits.example-city.gov/records/{entry['permit_number']}"

        lead = Lead(
            zip_code=zip_code,
            city=city,
            state=state,
            latitude=lat,
            longitude=lon,
            municipal_source_url=municipal_source_url,
            municipal_contact_name=contact_name,
            municipal_contact_phone=contact_phone,
            municipal_contact_email=contact_email,
            verified=True,
            ownership_category=ownership_category,
            certification_details=certification_details,
            source_url=source_url or municipal_source_url,
            **entry,
        )
        db.add(lead)

    db.commit()


def seed_dispatch_if_empty(db: Session) -> None:
    from app.dispatch_models import Contractor, Crew

    if db.query(Contractor).first() is not None:
        return

    contractor = Contractor(
        id="CON-1013",
        business_name="Precision Contractor",
        email="contact@precisioncontractor.com",
        phone="(914) 456-6336",
        trades=[Trade.GENERAL_CONTRACTING.value, Trade.REMODELING.value],
        service_zip="12601",
        latitude=41.7004,
        longitude=-73.9210,
        service_radius_miles=100,
        ownership_category="Minority-Owned",
        certification_details="NYS Minority-Owned Business Certified",
        source_url="https://www.precisioncontractor.com/",
        verified=True,
    )
    db.add(contractor)
    db.add(Crew(
        id="CREW-1013",
        contractor_id=contractor.id,
        name="Hudson Valley General Crew",
        trade=Trade.GENERAL_CONTRACTING.value,
        capacity=6,
    ))
    db.commit()
