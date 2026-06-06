"""Seed script — creates 4 fake users with varied public Agent Cards.

Run from the backend/ directory:
    python scripts/seed_agents.py

The script prints each user's UUID.  Use these as the `X-User-Id` header when
hitting the API, or paste them into the frontend user-picker.

After seeding, trigger a matchmaking cycle with:
    curl -X POST http://localhost:8000/admin/run-matchmaking
"""
import sys
import os

# Allow importing backend modules directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, SessionLocal
from models import User, AgentCard

SEED_USERS = [
    {
        "display_name": "Priya Mehta",
        "card": {
            "display_name":  "Priya Mehta",
            "public_bio":    "Full-stack engineer turned indie founder. Love fast feedback loops.",
            "building":      "A no-code tool that lets non-technical founders build and iterate "
                             "on data pipelines without writing SQL or Python.",
            "looking_for":   "A technical co-founder or advisor with a data engineering background "
                             "who can help architect the backend and validate the roadmap.",
            "can_offer":     "Strong product intuition, design skills, early customer discovery "
                             "with 30+ interviews done, and a working MVP with 200 beta users.",
            "tags":          ["no-code", "data", "saas", "b2b"],
            "is_public":     True,
            "a2a_enabled":   True,
        },
    },
    {
        "display_name": "Kofi Asante",
        "card": {
            "display_name":  "Kofi Asante",
            "public_bio":    "Data engineer, 8 years at scale. Building in public since 2023.",
            "building":      "An open-source dbt extension that auto-generates data contracts and "
                             "lineage graphs from existing warehouse schemas.",
            "looking_for":   "A product-minded partner who understands the non-technical user "
                             "side — UX, pricing, GTM — to help turn this into a real business.",
            "can_offer":     "Deep data engineering expertise, an active OSS community of 1 200 "
                             "GitHub stars, and a prototype that already runs on BigQuery and Snowflake.",
            "tags":          ["open-source", "data", "dbt", "developer-tools"],
            "is_public":     True,
            "a2a_enabled":   True,
        },
    },
    {
        "display_name": "Lena Fischer",
        "card": {
            "display_name":  "Lena Fischer",
            "public_bio":    "Ex-academic NLP researcher. First startup. Learning fast.",
            "building":      "An AI writing assistant specifically for academic researchers — "
                             "understands citations, LaTeX, and journal style guides.",
            "looking_for":   "Marketing and distribution help. Specifically someone who knows "
                             "how to reach researchers at universities and get academic press.",
            "can_offer":     "State-of-the-art NLP fine-tuning, a working product with 800 "
                             "active researchers, and strong credibility in the academic community.",
            "tags":          ["ai", "nlp", "edtech", "academic"],
            "is_public":     True,
            "a2a_enabled":   True,
        },
    },
    {
        "display_name": "Marcus Reid",
        "card": {
            "display_name":  "Marcus Reid",
            "public_bio":    "Growth marketer with 10 years in B2B SaaS. Now building my own thing.",
            "building":      "A community-led growth platform for developer tools — structured "
                             "ambassador programmes, referral tracking, and Discord analytics.",
            "looking_for":   "A technical partner who has built developer-tool products and "
                             "understands the unique GTM dynamics of open-source communities.",
            "can_offer":     "Full-stack GTM playbook, network of 40+ developer-tool founders, "
                             "and existing partnerships with major developer newsletters.",
            "tags":          ["growth", "developer-tools", "community", "open-source"],
            "is_public":     True,
            "a2a_enabled":   True,
        },
    },
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        print("\n== Axolotl Agent Card Seed ======================================")
        for entry in SEED_USERS:
            # Check if user already exists by display_name
            existing = db.query(User).filter_by(display_name=entry["display_name"]).first()
            if existing:
                print(f"  {entry['display_name']:20s} already exists — id: {existing.id}")
                continue

            user = User(display_name=entry["display_name"])
            db.add(user)
            db.flush()  # get user.id

            card_data = {**entry["card"]}
            card = AgentCard(user_id=user.id, **card_data)
            db.add(card)

            print(f"  {entry['display_name']:20s} created — id: {user.id}")

        db.commit()
        print()
        print("All users seeded. Use their IDs as the X-User-Id header.")
        print()
        print("Trigger matchmaking:")
        print("  curl -X POST http://localhost:8000/admin/run-matchmaking")
        print()
        print("Or for a single user:")
        print("  curl -X POST http://localhost:8000/admin/run-matchmaking/<user_id>")
        print("================================================================\n")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
