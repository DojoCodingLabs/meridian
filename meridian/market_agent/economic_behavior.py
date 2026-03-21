"""
Economic behavior engine for Meridian market agents.

Implements a three-tier hybrid decision architecture:
- Tier 1: Hard budget constraints (deterministic, no LLM)
- Tier 2: Propensity scoring (stochastic, calibrated to benchmarks)
- Tier 3: LLM reasoning (narrative generation for triggered decisions)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EconomicProfile:
    """Economic profile for a market agent.

    Inspired by SRD Framework persona wallet profiles:
    income, plan progression, upgrade triggers, LTV.
    """
    # Financial identity
    monthly_income: float = 100.0
    current_monthly_spend: float = 0.0
    budget_flexibility: float = 0.5
    currency_ppp: float = 1.0  # Purchasing power parity multiplier

    # Behavioral segmentation
    adoption_curve: str = "early_majority"  # innovator|early_adopter|early_majority|late_majority|laggard
    price_sensitivity: float = 0.5  # 0=insensitive, 1=extremely sensitive
    social_influence_weight: float = 0.5  # 0=independent, 1=follows crowd
    brand_loyalty_inertia: float = 0.5  # 0=switches easily, 1=never switches
    quality_expectation: float = 0.5  # 0=low bar, 1=perfectionist

    # Current product landscape
    current_subscriptions: list = field(default_factory=list)
    pain_points: list = field(default_factory=list)
    unmet_needs: list = field(default_factory=list)

    # Decision state (mutable per tick)
    funnel_stages: dict = field(default_factory=dict)  # product_id -> stage
    satisfaction_scores: dict = field(default_factory=dict)  # product_id -> score
    value_perceptions: dict = field(default_factory=dict)  # product_id -> score
    social_proof_counts: dict = field(default_factory=dict)  # product_id -> count
    review_sentiments: dict = field(default_factory=dict)  # product_id -> avg sentiment

    @property
    def remaining_budget(self) -> float:
        return max(0, self.monthly_income - self.current_monthly_spend)

    @property
    def max_single_subscription(self) -> float:
        """No single subscription should exceed 25% of income."""
        return self.monthly_income * 0.25

    @property
    def budget_ceiling(self) -> float:
        """Total subscriptions shouldn't exceed 20% of income (adjustable by flexibility)."""
        return self.monthly_income * (0.20 + self.budget_flexibility * 0.10)


class EconomicGate:
    """Tier 1: Deterministic hard constraints.

    Filters economically impossible actions BEFORE presenting to LLM.
    An agent with $30 remaining budget never sees 'Subscribe $47/mo'.
    """

    @staticmethod
    def can_afford(profile: EconomicProfile, price: float) -> bool:
        """Check if agent can afford a subscription at this price."""
        effective_price = price / profile.currency_ppp if profile.currency_ppp > 0 else price
        return effective_price <= profile.remaining_budget * (1 + profile.budget_flexibility)

    @staticmethod
    def exceeds_single_item_cap(profile: EconomicProfile, price: float) -> bool:
        """Check if price exceeds max single subscription threshold."""
        return price > profile.max_single_subscription

    @staticmethod
    def would_exceed_budget_ceiling(profile: EconomicProfile, price: float) -> bool:
        """Check if subscribing would push total spend over budget ceiling."""
        return (profile.current_monthly_spend + price) > profile.budget_ceiling

    @staticmethod
    def is_already_subscribed(profile: EconomicProfile, product_id: int) -> bool:
        """Check if agent already has an active subscription to this product."""
        return any(
            sub.get("product_id") == product_id and sub.get("status") == "active"
            for sub in profile.current_subscriptions
        )

    @staticmethod
    def filter_available_actions(profile: EconomicProfile, actions: list,
                                  products: dict = None) -> list:
        """Remove economically impossible actions before presenting to LLM.

        Args:
            profile: Agent's economic profile
            actions: List of available action types
            products: Dict of product_id -> product info with prices
        """
        if products is None:
            return actions

        filtered = []
        for action in actions:
            action_name = action.value if hasattr(action, 'value') else str(action)

            if action_name in ("subscribe", "upgrade_tier"):
                # Only keep if agent can afford at least one product
                can_afford_any = any(
                    EconomicGate.can_afford(profile, p.get("base_price", 0))
                    and not EconomicGate.exceeds_single_item_cap(profile, p.get("base_price", 0))
                    for p in products.values()
                )
                if not can_afford_any:
                    continue

            filtered.append(action)
        return filtered


class PropensityEngine:
    """Tier 2: Stochastic calibrated scoring.

    Determines WHETHER an economic event fires using probability functions
    calibrated to real-world SaaS benchmarks:
    - Free-to-paid: 2-5% (education: 5-10%)
    - Monthly churn: 5-7%
    - Trial-to-paid: 15-25%

    Benchmarks from SRD Framework revenue modeling.
    """

    # Adoption curve multipliers (technology adoption lifecycle)
    ADOPTION_MULTIPLIERS = {
        "innovator": 3.0,
        "early_adopter": 2.0,
        "early_majority": 1.0,
        "late_majority": 0.5,
        "laggard": 0.1,
    }

    @staticmethod
    def awareness_propensity(profile: EconomicProfile,
                              post_relevance: float = 0.5,
                              is_from_friend: bool = False) -> float:
        """Probability of becoming aware of a product from a post.

        Args:
            profile: Agent's economic profile
            post_relevance: How relevant the post is to agent's needs (0-1)
            is_from_friend: Whether the post is from someone they follow
        """
        base = 0.15  # 15% base chance of noticing a product mention

        adoption_mult = PropensityEngine.ADOPTION_MULTIPLIERS.get(
            profile.adoption_curve, 1.0)
        friend_mult = 2.0 if is_from_friend else 1.0
        relevance_mult = 0.5 + post_relevance

        return min(1.0, base * adoption_mult * friend_mult * relevance_mult)

    @staticmethod
    def interest_propensity(profile: EconomicProfile,
                             product_id: int,
                             social_proof_count: int = 0,
                             avg_review_rating: float = 0.0) -> float:
        """Probability of moving from aware to interested.

        Driven by social proof and need-product fit.
        """
        base = 0.10  # 10% base

        # Social proof effect
        social_mult = 1.0 + min(2.0, social_proof_count * 0.1 * profile.social_influence_weight)

        # Review effect
        review_mult = 1.0 + (avg_review_rating - 3.0) * 0.2 if avg_review_rating > 0 else 1.0

        # Need match (check if product addresses pain points)
        need_mult = 1.5 if profile.unmet_needs else 1.0

        # Adoption curve
        adoption_mult = PropensityEngine.ADOPTION_MULTIPLIERS.get(
            profile.adoption_curve, 1.0)

        return min(1.0, base * social_mult * review_mult * need_mult * adoption_mult)

    @staticmethod
    def trial_start_propensity(profile: EconomicProfile,
                                product_price: float,
                                has_trial: bool = True) -> float:
        """Probability of starting a free trial."""
        if not has_trial:
            return 0.0

        base = 0.25  # 25% of interested users start trials

        # Even free trials have friction — price sensitivity affects willingness
        price_friction = 1.0 - profile.price_sensitivity * 0.3

        # Adoption curve
        adoption_mult = PropensityEngine.ADOPTION_MULTIPLIERS.get(
            profile.adoption_curve, 1.0)

        return min(1.0, base * price_friction * adoption_mult)

    @staticmethod
    def trial_to_paid_propensity(profile: EconomicProfile,
                                  product_price: float,
                                  satisfaction: float = 5.0,
                                  social_proof_count: int = 0) -> float:
        """Probability of converting from trial to paid subscription.

        Calibrated to produce 15-25% trial-to-paid (education market).
        """
        base = 0.20  # 20% base trial-to-paid (education benchmark)

        # Adoption curve
        adoption_mult = PropensityEngine.ADOPTION_MULTIPLIERS.get(
            profile.adoption_curve, 1.0)

        # Price fit: how affordable is this relative to income?
        effective_price = product_price / profile.currency_ppp if profile.currency_ppp > 0 else product_price
        price_ratio = effective_price / profile.monthly_income if profile.monthly_income > 0 else 1.0
        price_fit = max(0.1, 1.0 - price_ratio * 5 * profile.price_sensitivity)

        # Satisfaction during trial
        satisfaction_mult = satisfaction / 10.0 * 2.0  # 0-2x multiplier

        # Social proof
        social_mult = 1.0 + min(1.0, social_proof_count * 0.05 * profile.social_influence_weight)

        propensity = base * adoption_mult * price_fit * satisfaction_mult * social_mult
        return min(1.0, max(0.0, propensity))

    @staticmethod
    def churn_propensity(profile: EconomicProfile,
                          product_price: float,
                          satisfaction: float = 5.0,
                          months_subscribed: int = 1,
                          social_proof_count: int = 0) -> float:
        """Probability of churning in a given period.

        Calibrated to produce 5-7% monthly churn (B2C SaaS benchmark).
        """
        base = 0.06  # 6% base monthly churn

        # Satisfaction inversely affects churn (low satisfaction = high churn)
        satisfaction_factor = max(0.1, (10.0 - satisfaction) / 5.0)

        # Budget pressure
        spend_ratio = profile.current_monthly_spend / profile.monthly_income if profile.monthly_income > 0 else 1.0
        budget_pressure = 1.0 + max(0, (spend_ratio - 0.15) * 5)

        # Social anchoring (friends using it reduces churn)
        social_anchor = max(0.3, 1.0 - social_proof_count * 0.05 * profile.social_influence_weight)

        # Tenure loyalty (longer subscribers churn less)
        tenure_factor = max(0.4, 1.0 - months_subscribed * 0.03)

        # Brand loyalty
        loyalty_factor = max(0.3, 1.0 - profile.brand_loyalty_inertia * 0.5)

        propensity = base * satisfaction_factor * budget_pressure * social_anchor * tenure_factor * loyalty_factor
        return min(1.0, max(0.0, propensity))

    @staticmethod
    def referral_propensity(profile: EconomicProfile,
                             satisfaction: float = 5.0) -> float:
        """Probability of referring a friend."""
        if satisfaction < 7.0:
            return 0.0  # Only satisfied users refer

        base = 0.05  # 5% base referral rate
        satisfaction_mult = (satisfaction - 7.0) / 3.0  # 0-1 for scores 7-10
        social_mult = 0.5 + profile.social_influence_weight * 0.5

        return min(0.3, base * satisfaction_mult * social_mult)

    @staticmethod
    def review_propensity(profile: EconomicProfile,
                           satisfaction: float = 5.0,
                           months_subscribed: int = 1) -> float:
        """Probability of writing a review."""
        if months_subscribed < 1:
            return 0.0  # Need at least 1 month experience

        base = 0.03  # 3% base review rate per month

        # Extreme satisfaction (very happy or very unhappy) drives reviews
        extremity = abs(satisfaction - 5.0) / 5.0
        extremity_mult = 1.0 + extremity * 2.0

        return min(0.2, base * extremity_mult)

    @staticmethod
    def evaluate(propensity: float) -> bool:
        """Roll the dice against a propensity score."""
        return random.random() < propensity


class SatisfactionEngine:
    """Models satisfaction evolution over time.

    Satisfaction is dynamic per tick, influenced by:
    - Product usage and quality
    - Social signals (friend opinions, reviews)
    - Economic pressure (price vs value perception)
    - Hedonic adaptation (regression toward mean)
    """

    @staticmethod
    def update_satisfaction(current: float,
                            quality_score: float = 0.5,
                            used_this_tick: bool = False,
                            friend_praised: bool = False,
                            saw_negative_review: bool = False,
                            price_increased: bool = False,
                            competitor_launched_feature: bool = False,
                            social_influence_weight: float = 0.5,
                            price_sensitivity: float = 0.5) -> float:
        """Compute new satisfaction score after one tick.

        Returns updated satisfaction (0.0 to 10.0).
        """
        delta = 0.0

        # Product usage effect
        if used_this_tick:
            delta += 0.1 * quality_score * 2  # Scale quality_score 0-1 to 0-0.2
        else:
            delta -= 0.05  # Slight decay from non-use

        # Social signals
        if friend_praised:
            delta += 0.15 * social_influence_weight
        if saw_negative_review:
            delta -= 0.2 * social_influence_weight

        # Economic pressure
        if price_increased:
            delta -= 0.4 * price_sensitivity

        # Competitive pressure
        if competitor_launched_feature:
            delta -= 0.15

        # Hedonic adaptation (pull toward neutral 5.0)
        hedonic_decay = (current - 5.0) * 0.02
        delta -= hedonic_decay

        new_satisfaction = current + delta
        return max(0.0, min(10.0, new_satisfaction))

    @staticmethod
    def compute_value_perception(satisfaction: float,
                                  product_price: float,
                                  monthly_income: float) -> float:
        """Value perception = satisfaction adjusted for price relative to income."""
        if monthly_income <= 0:
            return satisfaction * 0.5

        price_ratio = product_price / monthly_income
        price_penalty = price_ratio * 50  # Scale to meaningful range

        return max(0.0, min(10.0, satisfaction - price_penalty))
