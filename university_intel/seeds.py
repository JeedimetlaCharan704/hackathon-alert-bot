"""Seed data: official public homepages of Telangana universities & institutions.

URLs are best-effort official homepages. Event/RSS/innovation pages are found
automatically at scan time by the discovery tool, so a homepage is enough to
get started. This list is easy to extend for other states (just add more dicts).

To add other states later: add entries with a different `state` value. The
classifier, adapters and routing all read `state`, so nothing else changes.
"""

from __future__ import annotations

import logging

from university_intel.db import add_university, has_any_university
from university_intel.models import University

logger = logging.getLogger(__name__)

UNIVERSITIES: list[dict] = [
    # --- Central / premier institutes -------------------------------------
    {"name": "IIT Hyderabad", "city": "Sangareddy", "website": "https://iith.ac.in/"},
    {"name": "IIIT Hyderabad", "city": "Hyderabad", "website": "https://www.iiit.ac.in/"},
    {"name": "University of Hyderabad", "city": "Hyderabad", "website": "https://uohyd.ac.in/"},
    {"name": "NIT Warangal", "city": "Warangal", "website": "https://www.nitw.ac.in/"},
    {"name": "BITS Pilani Hyderabad Campus", "city": "Hyderabad", "website": "https://www.bits-pilani.ac.in/hyderabad"},
    {"name": "RGUKT", "city": "Basar", "website": "https://www.rgukt.in/"},
    # --- State universities ------------------------------------------------
    {"name": "Osmania University", "city": "Hyderabad", "website": "https://www.osmania.ac.in/"},
    {"name": "JNTU Hyderabad", "city": "Hyderabad", "website": "https://jntuh.ac.in/"},
    {"name": "Kakatiya University", "city": "Warangal", "website": "https://www.kakatiya.ac.in/"},
    {"name": "Palamuru University", "city": "Mahabubnagar", "website": "https://www.palamuruuniversity.ac.in/"},
    {"name": "Satavahana University", "city": "Karimnagar", "website": "https://satavahana.ac.in/"},
    {"name": "Telangana University", "city": "Nizamabad", "website": "https://www.telanganauniversity.ac.in/"},
    {"name": "Mahatma Gandhi University", "city": "Nalgonda", "website": "https://www.mguniversity.ac.in/"},
    {"name": "Dr. B.R. Ambedkar Open University", "city": "Hyderabad", "website": "https://www.braou.ac.in/"},
    {"name": "JNAFAU", "city": "Hyderabad", "website": "https://jnafau.ac.in/"},
    # --- Deemed / private universities --------------------------------------
    {"name": "Mahindra University", "city": "Hyderabad", "website": "https://www.mahindrauniversity.edu.in/"},
    {"name": "Woxsen University", "city": "Hyderabad", "website": "https://woxsen.edu.in/"},
    {"name": "SR University", "city": "Warangal", "website": "https://sru.edu.in/"},
    {"name": "ICFAI Foundation for Higher Education", "city": "Hyderabad", "website": "https://www.ifheindia.org/"},
    # --- Autonomous engineering colleges (Hyderabad) -------------------------
    {"name": "Chaitanya Bharathi Institute of Technology", "city": "Hyderabad", "website": "https://www.cbit.ac.in/"},
    {"name": "VNR Vignana Jyothi Institute of Engineering and Technology", "city": "Hyderabad", "website": "https://www.vnrvjiet.in/"},
    {"name": "Vasavi College of Engineering", "city": "Hyderabad", "website": "https://www.vasavi.ac.in/"},
    {"name": "Muffakham Jah College of Engineering and Technology", "city": "Hyderabad", "website": "https://www.mjcollege.ac.in/"},
    {"name": "G. Narayanamma Institute of Technology and Science", "city": "Hyderabad", "website": "https://www.gnits.ac.in/"},
    {"name": "Mahatma Gandhi Institute of Technology", "city": "Hyderabad", "website": "https://www.mgit.ac.in/"},
    {"name": "Vardhaman College of Engineering", "city": "Hyderabad", "website": "https://vardhaman.org/"},
    {"name": "CMR College of Engineering and Technology", "city": "Hyderabad", "website": "https://cmrcet.ac.in/"},
    {"name": "Keshav Memorial Institute of Technology", "city": "Hyderabad", "website": "https://kmit.in/"},
    {"name": "MLR Institute of Technology", "city": "Hyderabad", "website": "https://mlrinstitutions.ac.in/"},
    {"name": "Methodist College of Engineering and Technology", "city": "Hyderabad", "website": "https://www.methodist.edu.in/"},
    {"name": "Stanley College of Engineering and Technology", "city": "Hyderabad", "website": "https://www.stanley.edu.in/"},
    {"name": "Sreenidhi Institute of Science and Technology", "city": "Hyderabad", "website": "https://www.sreenidhi.edu.in/"},
    {"name": "CVR College of Engineering", "city": "Hyderabad", "website": "https://cvr.ac.in/"},
    {"name": "Gokaraju Rangaraju Institute of Engineering and Technology", "city": "Hyderabad", "website": "https://www.griet.ac.in/"},
    {"name": "Institute of Aeronautical Engineering", "city": "Hyderabad", "website": "https://iare.ac.in/"},
    {"name": "J.B. Institute of Engineering and Technology", "city": "Hyderabad", "website": "https://www.jbiet.edu.in/"},
    {"name": "Vallurupalli Nageswara Rao Vignana Jyothi Institute of Engineering and Technology", "city": "Hyderabad", "website": "https://vbit.ac.in/"},
    {"name": "Bhoj Reddy Engineering College for Women", "city": "Hyderabad", "website": "https://www.brce.ac.in/"},
    {"name": "Matrusri Engineering College", "city": "Hyderabad", "website": "https://www.matrusri.edu.in/"},
    {"name": "Malla Reddy College of Engineering and Technology", "city": "Hyderabad", "website": "https://mrcet.ac.in/"},
    {"name": "Nalla Malla Reddy Engineering College", "city": "Hyderabad", "website": "https://www.nmrec.edu.in/"},
    {"name": "Anurag University", "city": "Hyderabad", "website": "https://anurag.edu.in/"},
    {"name": "Lords Institute of Engineering and Technology", "city": "Hyderabad", "website": "https://www.lords.ac.in/"},
    # --- Engineering colleges (Warangal region) ------------------------------
    {"name": "Kakatiya Institute of Technology and Science", "city": "Warangal", "website": "https://www.kitsw.ac.in/"},
]


def seed_universities() -> int:
    """Insert seed universities (ignore existing). Returns count added."""
    added = 0
    for data in UNIVERSITIES:
        uid = add_university(
            University(
                id=None,
                name=data["name"],
                state="Telangana",
                city=data.get("city"),
                website=data["website"],
            )
        )
        if uid:
            added += 1
    logger.info("Seed complete: %d new university(s) added.", added)
    return added


def seed_if_empty() -> bool:
    """Seed on first run if the table is empty. Returns True if seeded."""
    if not has_any_university():
        seed_universities()
        return True
    return False
