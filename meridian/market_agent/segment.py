"""
Market segment definitions for Meridian.

Based on the technology adoption lifecycle (Rogers, 1962)
with economic parameters calibrated from SRD Framework benchmarks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from meridian.market_agent.economic_behavior import EconomicProfile


@dataclass
class MarketSegment:
    """Defines a market segment with statistical distributions for agent generation."""

    name: str
    population_share: float  # Share of total agent population

    # Economic parameter distributions (mean, std_dev)
    monthly_income_range: tuple[float, float] = (100.0, 500.0)
    price_sensitivity_range: tuple[float, float] = (0.3, 0.7)
    social_influence_range: tuple[float, float] = (0.3, 0.7)
    brand_loyalty_range: tuple[float, float] = (0.3, 0.7)
    quality_expectation_range: tuple[float, float] = (0.3, 0.7)
    risk_tolerance_range: tuple[float, float] = (0.3, 0.7)
    tech_savviness_range: tuple[float, float] = (0.3, 0.7)

    adoption_curve: str = "early_majority"

    # Persona traits for LLM prompt generation
    archetype_description: str = ""
    typical_pain_points: list[str] = field(default_factory=list)
    typical_needs: list[str] = field(default_factory=list)

    def generate_profile(self, currency_ppp: float = 1.0) -> EconomicProfile:
        """Generate a random economic profile from this segment's distributions."""
        return EconomicProfile(
            monthly_income=random.uniform(*self.monthly_income_range),
            current_monthly_spend=random.uniform(0, self.monthly_income_range[0] * 0.15),
            budget_flexibility=random.uniform(0.2, 0.6),
            currency_ppp=currency_ppp,
            adoption_curve=self.adoption_curve,
            price_sensitivity=random.uniform(*self.price_sensitivity_range),
            social_influence_weight=random.uniform(*self.social_influence_range),
            brand_loyalty_inertia=random.uniform(*self.brand_loyalty_range),
            quality_expectation=random.uniform(*self.quality_expectation_range),
            pain_points=list(self.typical_pain_points),
            unmet_needs=list(self.typical_needs),
        )


# Technology Adoption Lifecycle segments
INNOVATORS = MarketSegment(
    name="innovator",
    population_share=0.025,
    monthly_income_range=(200.0, 800.0),
    price_sensitivity_range=(0.1, 0.3),
    social_influence_range=(0.2, 0.4),
    brand_loyalty_range=(0.1, 0.3),
    quality_expectation_range=(0.3, 0.5),
    risk_tolerance_range=(0.8, 1.0),
    tech_savviness_range=(0.8, 1.0),
    adoption_curve="innovator",
    archetype_description="Tech enthusiast who tries everything new. Tolerates bugs and rough edges. Values novelty over polish.",
    typical_pain_points=["boredom with existing tools", "want cutting-edge features"],
    typical_needs=["early access", "beta features", "novel approaches"],
)

EARLY_ADOPTERS = MarketSegment(
    name="early_adopter",
    population_share=0.135,
    monthly_income_range=(150.0, 600.0),
    price_sensitivity_range=(0.2, 0.5),
    social_influence_range=(0.3, 0.6),
    brand_loyalty_range=(0.2, 0.4),
    quality_expectation_range=(0.4, 0.6),
    risk_tolerance_range=(0.6, 0.8),
    tech_savviness_range=(0.7, 0.9),
    adoption_curve="early_adopter",
    archetype_description="Visionary who sees potential in new products. Willing to accept imperfections if the vision is compelling.",
    typical_pain_points=["current tools don't match ambition", "want to be ahead of peers"],
    typical_needs=["clear product vision", "responsive team", "community of like-minded users"],
)

EARLY_MAJORITY = MarketSegment(
    name="early_majority",
    population_share=0.34,
    monthly_income_range=(100.0, 400.0),
    price_sensitivity_range=(0.4, 0.7),
    social_influence_range=(0.5, 0.8),
    brand_loyalty_range=(0.3, 0.5),
    quality_expectation_range=(0.5, 0.7),
    risk_tolerance_range=(0.3, 0.5),
    tech_savviness_range=(0.5, 0.7),
    adoption_curve="early_majority",
    archetype_description="Pragmatist who needs social proof before committing. Wants proven value and peer validation.",
    typical_pain_points=["need to see others succeed first", "cautious with spending"],
    typical_needs=["testimonials", "proven track record", "easy onboarding", "clear ROI"],
)

LATE_MAJORITY = MarketSegment(
    name="late_majority",
    population_share=0.34,
    monthly_income_range=(80.0, 300.0),
    price_sensitivity_range=(0.6, 0.9),
    social_influence_range=(0.6, 0.9),
    brand_loyalty_range=(0.5, 0.7),
    quality_expectation_range=(0.6, 0.8),
    risk_tolerance_range=(0.1, 0.3),
    tech_savviness_range=(0.3, 0.5),
    adoption_curve="late_majority",
    archetype_description="Skeptic who only adopts when the majority already has. Very price-conscious and risk-averse.",
    typical_pain_points=["overwhelmed by choices", "worried about wasting money"],
    typical_needs=["simplicity", "low price", "peer pressure", "risk-free guarantee"],
)

LAGGARDS = MarketSegment(
    name="laggard",
    population_share=0.16,
    monthly_income_range=(50.0, 200.0),
    price_sensitivity_range=(0.8, 1.0),
    social_influence_range=(0.1, 0.4),
    brand_loyalty_range=(0.7, 0.9),
    quality_expectation_range=(0.2, 0.4),
    risk_tolerance_range=(0.0, 0.15),
    tech_savviness_range=(0.1, 0.3),
    adoption_curve="laggard",
    archetype_description="Traditionalist who resists change. Only adopts when forced or when there's truly no alternative.",
    typical_pain_points=["don't like change", "current approach works fine"],
    typical_needs=["absolute necessity", "zero learning curve", "free or very cheap"],
)

# All segments in lifecycle order
ALL_SEGMENTS = [INNOVATORS, EARLY_ADOPTERS, EARLY_MAJORITY, LATE_MAJORITY, LAGGARDS]


# LatAm-specific PPP multipliers (for DojoOS preset)
LATAM_PPP = {
    "US": 1.0,
    "Costa Rica": 0.55,
    "Colombia": 0.35,
    "Mexico": 0.45,
    "Argentina": 0.30,
    "Peru": 0.35,
    "Guatemala": 0.30,
    "Panama": 0.50,
    "Chile": 0.50,
    "Brazil": 0.40,
}


def generate_agent_population(
    total_agents: int,
    segments: list[MarketSegment] = None,
    country_distribution: dict[str, float] = None,
) -> list[dict]:
    """Generate a population of agent profiles from segment distributions.

    Args:
        total_agents: Total number of agents to generate
        segments: Market segments to use (defaults to ALL_SEGMENTS)
        country_distribution: Country -> share mapping (optional)

    Returns:
        List of dicts with 'segment', 'country', 'ppp', 'profile' keys
    """
    if segments is None:
        segments = ALL_SEGMENTS

    if country_distribution is None:
        country_distribution = {"US": 1.0}

    agents = []

    for segment in segments:
        count = max(1, round(total_agents * segment.population_share))

        for _ in range(count):
            # Pick country based on distribution
            country = random.choices(
                list(country_distribution.keys()),
                weights=list(country_distribution.values()),
                k=1
            )[0]
            ppp = LATAM_PPP.get(country, 1.0)

            profile = segment.generate_profile(currency_ppp=ppp)

            agents.append({
                "segment": segment.name,
                "country": country,
                "ppp": ppp,
                "profile": profile,
                "archetype": segment.archetype_description,
                "pain_points": segment.typical_pain_points,
                "needs": segment.typical_needs,
            })

    random.shuffle(agents)
    return agents[:total_agents]  # Trim to exact count
