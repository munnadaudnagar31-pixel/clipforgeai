"""ClipForge AI â€” Stripe Webhook Handler

Handles Stripe billing events: checkout completed, subscription deleted,
payment failed. Uses plain string plan values (no PlanEnum).
"""
import os
import sys
# Inject workspace paths to fix IDE red lines and Render imports
_app_dir = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_app_dir) != 'app' and _app_dir != os.path.dirname(_app_dir):
    _app_dir = os.path.dirname(_app_dir)
_backend_dir = os.path.dirname(_app_dir)
_root_dir = os.path.dirname(_backend_dir)
if _backend_dir not in sys.path: sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path: sys.path.insert(0, _root_dir)


from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import update, select

from backend.app.config import settings
from backend.app.database import AsyncSessionLocal
from backend.app.models.models import User

router = APIRouter()

# Price ID â†’ plan string mapping (set in .env)
def _price_to_plan() -> dict:
    return {
        settings.STRIPE_PRICE_PRO:     "pro",
        settings.STRIPE_PRICE_CREATOR: "creator",
        settings.STRIPE_PRICE_AGENCY:  "agency",
    }


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Verify Stripe webhook signature and process billing events."""
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Only import stripe if the secret key is configured
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe is not configured on this server.")

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ImportError:
        raise HTTPException(503, "stripe package is not installed.")
    except Exception:
        raise HTTPException(400, "Invalid Stripe signature or malformed event.")

    price_map = _price_to_plan()

    async with AsyncSessionLocal() as db:
        event_type = event.get("type", "")

        if event_type == "checkout.session.completed":
            session_obj  = event["data"]["object"]
            customer_id  = session_obj.get("customer")
            sub_id       = session_obj.get("subscription")
            price_id     = session_obj.get("metadata", {}).get("price_id", "")
            new_plan     = price_map.get(price_id, "free")

            await db.execute(
                update(User)
                .where(User.stripe_customer_id == customer_id)
                .values(plan=new_plan, stripe_subscription_id=sub_id)
            )

        elif event_type == "customer.subscription.deleted":
            sub          = event["data"]["object"]
            customer_id  = sub.get("customer")
            await db.execute(
                update(User)
                .where(User.stripe_customer_id == customer_id)
                .values(plan="free", stripe_subscription_id=None)
            )

        elif event_type == "invoice.payment_failed":
            invoice     = event["data"]["object"]
            customer_id = invoice.get("customer")
            print(f"[Webhook] Payment failed for customer: {customer_id}")

        await db.commit()

    return {"received": True}

