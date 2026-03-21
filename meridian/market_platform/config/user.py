# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# flake8: noqa: E501
import warnings
from dataclasses import dataclass
from typing import Any

from camel.prompts import TextPrompt


@dataclass
class UserInfo:
    user_name: str | None = None
    name: str | None = None
    description: str | None = None
    profile: dict[str, Any] | None = None
    recsys_type: str = "twitter"
    is_controllable: bool = False

    def to_custom_system_message(self, user_info_template: TextPrompt) -> str:
        required_keys = user_info_template.key_words
        info_keys = set(self.profile.keys())
        missing = required_keys - info_keys
        extra = info_keys - required_keys
        if missing:
            raise ValueError(
                f"Missing required keys in UserInfo.profile: {missing}")
        if extra:
            warnings.warn(f"Extra keys not used in UserInfo.profile: {extra}")

        return user_info_template.format(**self.profile)

    def to_system_message(self) -> str:
        if self.recsys_type != "reddit":
            return self.to_twitter_system_message()
        else:
            return self.to_reddit_system_message()

    def to_twitter_system_message(self) -> str:
        name_string = ""
        description_string = ""
        if self.name is not None:
            name_string = f"Your name is {self.name}."
        if self.profile is None:
            description = name_string
        elif "other_info" not in self.profile:
            description = name_string
        elif "user_profile" in self.profile["other_info"]:
            if self.profile["other_info"]["user_profile"] is not None:
                user_profile = self.profile["other_info"]["user_profile"]
                description_string = f"Your have profile: {user_profile}."
                description = f"{name_string}\n{description_string}"

        system_content = f"""
# OBJECTIVE
You're a Twitter user, and I'll present you with some tweets. After you see the tweets, choose some actions from the following functions.

# SELF-DESCRIPTION
Your actions should be consistent with your self-description and personality.
{description}

# RESPONSE METHOD
Please perform actions by tool calling.
        """

        return system_content

    def to_reddit_system_message(self) -> str:
        name_string = ""
        description_string = ""
        if self.name is not None:
            name_string = f"Your name is {self.name}."
        if self.profile is None:
            description = name_string
        elif "other_info" not in self.profile:
            description = name_string
        elif "user_profile" in self.profile["other_info"]:
            if self.profile["other_info"]["user_profile"] is not None:
                user_profile = self.profile["other_info"]["user_profile"]
                description_string = f"Your have profile: {user_profile}."
                description = f"{name_string}\n{description_string}"
                print(self.profile['other_info'])
                description += (
                    f"You are a {self.profile['other_info']['gender']}, "
                    f"{self.profile['other_info']['age']} years old, with an MBTI "
                    f"personality type of {self.profile['other_info']['mbti']} from "
                    f"{self.profile['other_info']['country']}.")

        system_content = f"""
# OBJECTIVE
You're a Reddit user, and I'll present you with some posts. After you see the posts, choose some actions from the following functions.

# SELF-DESCRIPTION
Your actions should be consistent with your self-description and personality.
{description}

# RESPONSE METHOD
Please perform actions by tool calling.
"""
        return system_content

    def to_market_system_message(self) -> str:
        """Build a system message that includes economic decision-making context."""
        other_info = self.profile.get("other_info", {}) if self.profile else {}
        economic = other_info.get("economic", {})

        if not economic:
            return self.to_system_message()

        # Build economic context
        monthly_income = economic.get("monthly_income", 0)
        current_spend = economic.get("current_monthly_spend", 0)
        remaining = max(0, monthly_income - current_spend)
        sensitivity = economic.get("price_sensitivity", 0.5)
        adoption = economic.get("adoption_curve", "early_majority")
        country = other_info.get("country", "")

        # Sensitivity description
        if sensitivity > 0.8:
            price_desc = "extremely price-sensitive — every dollar matters"
        elif sensitivity > 0.6:
            price_desc = "price-conscious — you compare carefully before spending"
        elif sensitivity > 0.4:
            price_desc = "moderately price-aware — willing to pay for quality"
        elif sensitivity > 0.2:
            price_desc = "not very concerned about price — you value quality"
        else:
            price_desc = "price is barely a factor — if it's good, you buy it"

        # Current subscriptions
        subs = economic.get("current_subscriptions", [])
        subs_text = ""
        if subs:
            subs_lines = [f"  - {s.get('name', '?')} (${s.get('monthly_cost', 0)}/mo, satisfaction: {s.get('satisfaction', 5)}/10)" for s in subs]
            subs_text = "Your current subscriptions:\n" + "\n".join(subs_lines)

        # Pain points and needs
        pains = economic.get("pain_points", [])
        needs = economic.get("unmet_needs", [])

        name = self.name or "User"
        age = other_info.get("age", "")
        gender = other_info.get("gender", "")
        profession = other_info.get("profession", "")
        mbti = other_info.get("mbti", "")
        user_profile = other_info.get("user_profile", self.description or "")

        system_content = f"""# IDENTITY
You are {name}, a {age}-year-old {gender} {profession} from {country}.
Personality: {mbti}. {user_profile}

# YOUR FINANCIAL SITUATION
- Monthly disposable income for digital tools/services: ${monthly_income}/mo
- Currently spending: ${current_spend}/mo on subscriptions
- Remaining budget: ${remaining:.0f}/mo
- You are a "{adoption}" on the technology adoption curve
- Price sensitivity: {price_desc}
{subs_text}

# YOUR NEEDS
Pain points: {', '.join(pains) if pains else 'None specific'}
Unmet needs: {', '.join(needs) if needs else 'None specific'}

# HOW YOU MAKE DECISIONS
1. Personal utility — does this solve a real problem for you?
2. Budget fit — can you afford this given your ${monthly_income}/mo income?
3. Social proof — what are people you trust saying about it?
4. Alternatives — how does it compare to what you currently use?
5. Quality — does it meet your standards?

# RULES
- Never spend more than 25% of your monthly income on a single subscription
- If total subscriptions would exceed 20% of income, consider canceling something first
- When trialing, evaluate honestly whether you'd pay full price
- Your actions should be consistent with who you are — {name} from {country}

# YOUR TASK
You are on a social platform where people discuss products and services. Based on what you see, your situation, and the actions available, decide what to do next. Think about whether you genuinely need something before buying it."""

        return system_content
