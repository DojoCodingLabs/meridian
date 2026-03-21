#!/usr/bin/env python3
"""
Meridian Quick Start Example
============================

Demonstrates a minimal product profitability prediction simulation.
10 agents evaluate a SaaS product with 3 competitors over 10 timesteps.

Usage:
    pip install meridian
    python examples/quick_start.py

Requirements:
    - OpenAI API key (set OPENAI_API_KEY env var)
    - Python 3.10+
"""

import asyncio
import json
import os
import sys
import random
from datetime import datetime

# Add parent to path for development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meridian.market_agent.economic_behavior import (
    EconomicProfile,
    EconomicGate,
    PropensityEngine,
    SatisfactionEngine,
)
from meridian.market_agent.segment import (
    ALL_SEGMENTS,
    LATAM_PPP,
    generate_agent_population,
)


def demo_economic_gate():
    """Demonstrate Tier 1: Hard budget constraints."""
    print("\n" + "=" * 60)
    print("TIER 1: Economic Gate (Hard Budget Constraints)")
    print("=" * 60)

    # Create a price-sensitive Colombian junior dev
    santiago = EconomicProfile(
        monthly_income=150.0,
        current_monthly_spend=15.0,
        budget_flexibility=0.3,
        currency_ppp=0.35,  # Colombia PPP
        adoption_curve="early_adopter",
        price_sensitivity=0.85,
    )

    print(f"\nSantiago (Colombia, ${santiago.monthly_income}/mo income):")
    print(f"  Remaining budget: ${santiago.remaining_budget:.0f}/mo")
    print(f"  Max single subscription: ${santiago.max_single_subscription:.0f}")
    print(f"  Budget ceiling: ${santiago.budget_ceiling:.0f}")

    products = {
        "dojos_pro": {"base_price": 47.0},
        "dojos_vip": {"base_price": 297.0},
        "platzi": {"base_price": 49.0},
        "udemy": {"base_price": 15.0},
    }

    print(f"\n  Can afford DojoOS Pro ($47/mo)? {EconomicGate.can_afford(santiago, 47.0)}")
    print(f"  Can afford DojoOS VIP ($297/mo)? {EconomicGate.can_afford(santiago, 297.0)}")
    print(f"  Can afford Udemy ($15/mo)? {EconomicGate.can_afford(santiago, 15.0)}")
    print(f"  Pro exceeds single-item cap? {EconomicGate.exceeds_single_item_cap(santiago, 47.0)}")

    # Create a well-off Costa Rican founder
    lucia = EconomicProfile(
        monthly_income=800.0,
        current_monthly_spend=120.0,
        budget_flexibility=0.7,
        currency_ppp=0.55,  # Costa Rica PPP
        adoption_curve="innovator",
        price_sensitivity=0.2,
    )

    print(f"\nLucia (Costa Rica, ${lucia.monthly_income}/mo income):")
    print(f"  Remaining budget: ${lucia.remaining_budget:.0f}/mo")
    print(f"  Can afford DojoOS Pro ($47/mo)? {EconomicGate.can_afford(lucia, 47.0)}")
    print(f"  Can afford DojoOS VIP ($297/mo)? {EconomicGate.can_afford(lucia, 297.0)}")


def demo_propensity_engine():
    """Demonstrate Tier 2: Stochastic calibrated scoring."""
    print("\n" + "=" * 60)
    print("TIER 2: Propensity Engine (Calibrated Probability)")
    print("=" * 60)

    # Run 1000 simulated trial-to-paid decisions for each segment
    segments = {
        "innovator": EconomicProfile(adoption_curve="innovator", price_sensitivity=0.2, monthly_income=400),
        "early_adopter": EconomicProfile(adoption_curve="early_adopter", price_sensitivity=0.4, monthly_income=300),
        "early_majority": EconomicProfile(adoption_curve="early_majority", price_sensitivity=0.6, monthly_income=200),
        "late_majority": EconomicProfile(adoption_curve="late_majority", price_sensitivity=0.8, monthly_income=150),
        "laggard": EconomicProfile(adoption_curve="laggard", price_sensitivity=0.95, monthly_income=100),
    }

    product_price = 47.0  # DojoOS Pro
    n_trials = 1000

    print(f"\nSimulating {n_trials} trial-to-paid decisions per segment (DojoOS Pro @ ${product_price}/mo):\n")

    for name, profile in segments.items():
        conversions = sum(
            1 for _ in range(n_trials)
            if PropensityEngine.evaluate(
                PropensityEngine.trial_to_paid_propensity(
                    profile, product_price, satisfaction=7.0, social_proof_count=3
                )
            )
        )
        rate = conversions / n_trials * 100
        print(f"  {name:15s}: {rate:5.1f}% conversion ({conversions}/{n_trials})")

    print("\n  Target benchmark: 15-25% trial-to-paid (education market)")

    # Churn simulation
    print(f"\nSimulating {n_trials} monthly churn decisions per segment:\n")

    for name, profile in segments.items():
        churns = sum(
            1 for _ in range(n_trials)
            if PropensityEngine.evaluate(
                PropensityEngine.churn_propensity(
                    profile, product_price, satisfaction=6.0, months_subscribed=3
                )
            )
        )
        rate = churns / n_trials * 100
        print(f"  {name:15s}: {rate:5.1f}% monthly churn ({churns}/{n_trials})")

    print("\n  Target benchmark: 5-7% monthly churn (B2C SaaS)")


def demo_satisfaction_evolution():
    """Demonstrate satisfaction dynamics over time."""
    print("\n" + "=" * 60)
    print("SATISFACTION EVOLUTION (10 Months)")
    print("=" * 60)

    satisfaction = 7.5  # Post-trial satisfaction
    quality = 0.70  # DojoOS quality score

    print(f"\n  Month | Satisfaction | Event")
    print(f"  ------|-------------|------")

    events = [
        (True, False, False, False, False, "Used product"),
        (True, True, False, False, False, "Used + friend praised"),
        (True, False, False, False, False, "Used product"),
        (False, False, True, False, False, "Didn't use, saw negative review"),
        (True, False, False, False, False, "Used product"),
        (True, False, False, True, False, "Used but price increased"),
        (False, False, False, False, True, "Didn't use, competitor launched feature"),
        (True, True, False, False, False, "Used + friend praised"),
        (True, False, False, False, False, "Used product"),
        (False, False, False, False, False, "Didn't use (disengaged)"),
    ]

    for month, (used, praised, negative, price_up, competitor, event) in enumerate(events, 1):
        satisfaction = SatisfactionEngine.update_satisfaction(
            current=satisfaction,
            quality_score=quality,
            used_this_tick=used,
            friend_praised=praised,
            saw_negative_review=negative,
            price_increased=price_up,
            competitor_launched_feature=competitor,
            social_influence_weight=0.6,
            price_sensitivity=0.5,
        )
        bar = "#" * int(satisfaction * 3)
        print(f"  {month:5d} | {satisfaction:11.2f} | {event:30s} {bar}")


def demo_population_generation():
    """Demonstrate agent population generation."""
    print("\n" + "=" * 60)
    print("AGENT POPULATION GENERATION")
    print("=" * 60)

    latam_distribution = {
        "Costa Rica": 0.20,
        "Colombia": 0.20,
        "Mexico": 0.20,
        "Argentina": 0.10,
        "Peru": 0.10,
        "Guatemala": 0.05,
        "Panama": 0.05,
        "Chile": 0.05,
        "Brazil": 0.05,
    }

    agents = generate_agent_population(
        total_agents=200,
        country_distribution=latam_distribution,
    )

    # Segment distribution
    segment_counts = {}
    country_counts = {}
    for agent in agents:
        segment_counts[agent["segment"]] = segment_counts.get(agent["segment"], 0) + 1
        country_counts[agent["country"]] = country_counts.get(agent["country"], 0) + 1

    print(f"\n  Generated {len(agents)} agents\n")

    print("  Segment Distribution:")
    for seg in ["innovator", "early_adopter", "early_majority", "late_majority", "laggard"]:
        count = segment_counts.get(seg, 0)
        pct = count / len(agents) * 100
        bar = "#" * int(pct)
        print(f"    {seg:15s}: {count:3d} ({pct:4.1f}%) {bar}")

    print("\n  Country Distribution:")
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        pct = count / len(agents) * 100
        ppp = LATAM_PPP.get(country, 1.0)
        print(f"    {country:15s}: {count:3d} ({pct:4.1f}%) PPP={ppp}")

    # Income distribution by segment
    print("\n  Average Monthly Income by Segment:")
    for seg in ["innovator", "early_adopter", "early_majority", "late_majority", "laggard"]:
        seg_agents = [a for a in agents if a["segment"] == seg]
        if seg_agents:
            avg_income = sum(a["profile"].monthly_income for a in seg_agents) / len(seg_agents)
            avg_sensitivity = sum(a["profile"].price_sensitivity for a in seg_agents) / len(seg_agents)
            print(f"    {seg:15s}: ${avg_income:6.0f}/mo  sensitivity={avg_sensitivity:.2f}")


def main():
    """Run all Meridian demos."""
    print("=" * 60)
    print("  MERIDIAN — Product Profitability Prediction Engine")
    print("  Quick Start Demo")
    print("=" * 60)

    demo_economic_gate()
    demo_propensity_engine()
    demo_satisfaction_evolution()
    demo_population_generation()

    print("\n" + "=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Set OPENAI_API_KEY environment variable")
    print("  2. Run a full simulation: meridian simulate --config presets/dojos/config.yaml")
    print("  3. Generate report: meridian report --project dojos")
    print("  4. Compare scenarios: meridian compare --scenarios pro_at_29,pro_at_37")


if __name__ == "__main__":
    main()
