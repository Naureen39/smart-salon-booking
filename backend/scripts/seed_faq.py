"""Seeds/refreshes the faq_documents table with a starter FAQ set for GlowDesk,
embedding each canonical question with BAAI/bge-small-en-v1.5 (docs plan §9.2).

Usage:
    python -m scripts.seed_faq
"""

import asyncio

from sqlalchemy import delete

from app.ai.embeddings import embed_passages
from app.db.models.faq_document import FaqDocument
from app.db.session import async_session_factory

FAQ_SEED_DATA = [
    (
        "What are your hours?",
        "We're open Tuesday through Saturday, 9:00 AM to 6:00 PM. We're closed Sundays and Mondays.",
    ),
    (
        "What is your cancellation policy?",
        "You can cancel or reschedule free of charge up to 24 hours before your appointment. "
        "Cancellations within 24 hours may incur a fee.",
    ),
    (
        "Is parking available?",
        "Yes — free customer parking is available directly behind the salon, with additional "
        "street parking on the block.",
    ),
    (
        "What payment methods do you accept?",
        "We accept all major credit/debit cards, Apple Pay, Google Pay, and cash. "
        "We do not accept personal checks.",
    ),
    (
        "Do you accept walk-ins?",
        "We prioritize scheduled appointments, but we're happy to accommodate walk-ins when a "
        "stylist is available. Booking ahead guarantees your slot.",
    ),
    (
        "Do you sell gift cards?",
        "Yes, gift cards are available for purchase in-salon or by phone, in any amount, and never expire.",
    ),
    (
        "Can I bring a guest to my appointment?",
        "You're welcome to bring one guest. For young children, we ask that they be supervised "
        "for everyone's safety and comfort.",
    ),
    (
        "What if I'm running late?",
        "Please call us as soon as you know — we'll do our best to accommodate you, but arriving "
        "more than 15 minutes late may require rescheduling to protect other clients' appointment times.",
    ),
    (
        "Do you offer bridal or group packages?",
        "Yes, we offer customized bridal party and group event packages. Contact us directly to "
        "discuss your event and we'll put together a quote.",
    ),
    (
        "How far in advance should I book?",
        "Popular time slots (evenings and Saturdays) fill up 1-2 weeks ahead, but we often have "
        "availability for weekday mornings and afternoons with just a day or two of notice.",
    ),
]


async def seed() -> int:
    questions = [question for question, _ in FAQ_SEED_DATA]
    embeddings = embed_passages(questions)

    async with async_session_factory() as db:
        await db.execute(delete(FaqDocument))
        for (question, answer), embedding in zip(FAQ_SEED_DATA, embeddings, strict=True):
            db.add(FaqDocument(question=question, answer=answer, embedding=embedding))
        await db.commit()

    return len(FAQ_SEED_DATA)


def main() -> None:
    count = asyncio.run(seed())
    print(f"Seeded {count} FAQ documents.")


if __name__ == "__main__":
    main()
