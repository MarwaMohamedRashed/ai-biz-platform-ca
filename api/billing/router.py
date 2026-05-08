"""
Billing — Stripe Checkout + Webhooks + Customer Portal
========================================================
Handles subscription lifecycle: checkout, renewals, cancellations.
"""
import os
import logging
import datetime
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user
from pydantic import BaseModel
from typing import Literal


logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_STARTER  = os.getenv("STRIPE_PRICE_STARTER")
STRIPE_PRICE_PRO      = os.getenv("STRIPE_PRICE_PRO")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:3000")


class CheckoutRequest(BaseModel):
    plan: Literal["starter", "pro"]
    locale: str = "en"


class PortalRequest(BaseModel):
    locale: str = "en"


def _price_to_tier(price_id: str) -> str:
    """Map Stripe price ID → DB plan_tier enum value."""
    return "starter" if price_id == STRIPE_PRICE_STARTER else "pro"


def _get_stripe_customer_id(business_id: str) -> str | None:
    """Look up the Stripe customer ID from the subscriptions table."""
    result = (
        supabase_admin.table("subscriptions")
        .select("stripe_customer_id")
        .eq("business_id", business_id)
        .limit(1)
        .execute()
    )
    return result.data[0].get("stripe_customer_id") if result.data else None


@router.post("/checkout-session")
async def create_checkout_session(body: CheckoutRequest, user=Depends(get_current_user)):
    business = await get_business_by_user(user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    stripe_customer_id = _get_stripe_customer_id(business["id"])
    if not stripe_customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"business_id": str(business["id"])},
        )
        stripe_customer_id = customer.id
        supabase_admin.table("subscriptions").update(
            {"stripe_customer_id": stripe_customer_id}
        ).eq("business_id", business["id"]).execute()

    price_id = STRIPE_PRICE_STARTER if body.plan == "starter" else STRIPE_PRICE_PRO

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=stripe_customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"business_id": str(business["id"])},
        subscription_data={
            "trial_period_days": 14,
            "metadata": {"business_id": str(business["id"])},
        },
        success_url=f"{WEB_BASE_URL}/{body.locale}/dashboard/plan/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{WEB_BASE_URL}/{body.locale}/dashboard/plan/cancel",
        allow_promotion_codes=True,
        billing_address_collection="auto",
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event.type == "checkout.session.completed":
        session = event.data.object
        subscription_id = session.get("subscription")
        customer_id = session.get("customer")
        business_id = session["metadata"].get("business_id")

        sub = stripe.Subscription.retrieve(subscription_id)
        plan_tier = _price_to_tier(sub["items"]["data"][0]["price"]["id"])

        logger.info(f"Checkout completed: sub={subscription_id} business={business_id}")
        supabase_admin.table("subscriptions").upsert(
            {
                "business_id": business_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "status": "trialing",
                "plan_tier": plan_tier,
            },
            on_conflict="business_id"
        ).execute()

    elif event.type == "customer.subscription.updated":
        subscription = event.data.object
        subscription_id = subscription.get("id")
        plan_tier = _price_to_tier(subscription["items"]["data"][0]["price"]["id"])
        current_period_end = datetime.datetime.fromtimestamp(
            subscription["current_period_end"], tz=datetime.timezone.utc
        ).isoformat()

        logger.info(f"Subscription updated: sub={subscription_id} status={subscription['status']} plan={plan_tier}")
        supabase_admin.table("subscriptions").update({
            "status": subscription["status"],
            "plan_tier": plan_tier,
            "current_period_end": current_period_end,
            "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
        }).eq("stripe_subscription_id", subscription_id).execute()

    elif event.type == "invoice.payment_failed":
        invoice = event.data.object
        subscription_id = invoice.get("subscription")
        logger.warning(f"Payment failed: sub={subscription_id}")
        supabase_admin.table("subscriptions").update(
            {"status": "past_due"}
        ).eq("stripe_subscription_id", subscription_id).execute()

    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object
        subscription_id = subscription.get("id")
        logger.info(f"Subscription canceled: sub={subscription_id}")
        supabase_admin.table("subscriptions").update(
            {"status": "canceled"}
        ).eq("stripe_subscription_id", subscription_id).execute()

    return {"status": "success"}


@router.post("/portal-session")
async def create_portal_session(body: PortalRequest, user=Depends(get_current_user)):
    business = await get_business_by_user(user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    stripe_customer_id = _get_stripe_customer_id(business["id"])
    if not stripe_customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer found for this business")

    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f"{WEB_BASE_URL}/{body.locale}/dashboard/plan",
    )
    return {"url": session.url}
