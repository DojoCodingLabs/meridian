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
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from string import Template

from meridian.market_agent.agent_action import SocialAction
from meridian.market_platform.database import get_db_path


class Environment(ABC):

    @abstractmethod
    def to_text_prompt(self) -> str:
        r"""Convert the environment to text prompt."""
        raise NotImplementedError


class SocialEnvironment(Environment):
    followers_env_template = Template("I have $num_followers followers.")
    follows_env_template = Template("I have $num_follows follows.")

    posts_env_template = Template(
        "After refreshing, you see some posts $posts")

    groups_env_template = Template(
        "And there are many group chat channels $all_groups\n"
        "And You are already in some groups $joined_groups\n"
        "You receive some messages from them $messages\n"
        "You can join the groups you are interested, "
        "leave the groups you already in, send messages to the group "
        "you already in.\n"
        "You must make sure you can only send messages to the group you "
        "are already in")
    env_template = Template(
        "$groups_env\n"
        "$posts_env\npick one you want to perform action that best "
        "reflects your current inclination based on your profile and "
        "posts content. Do not limit your action in just `like` to like posts")

    def __init__(self, action: SocialAction):
        self.action = action

    async def get_posts_env(self) -> str:
        posts = await self.action.refresh()
        # TODO: Replace posts json format string to other formats
        if posts["success"]:
            posts_env = json.dumps(posts["posts"], indent=4)
            posts_env = self.posts_env_template.substitute(posts=posts_env)
        else:
            posts_env = "After refreshing, there are no existing posts."
        return posts_env

    async def get_followers_env(self) -> str:
        # TODO: Implement followers env
        agent_id = self.action.agent_id
        db_path = get_db_path()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT num_followers FROM user WHERE agent_id = ?",
                           (agent_id, ))
            result = cursor.fetchone()
            num_followers = result[0] if result else 0
            conn.close()
        except Exception:
            num_followers = 0
        return self.followers_env_template.substitute(
            {"num_followers": num_followers})

    async def get_follows_env(self) -> str:
        # TODO: Implement follows env
        agent_id = self.action.agent_id
        try:
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT num_followings FROM user WHERE agent_id = ?",
                (agent_id, ))
            result = cursor.fetchone()
            num_followings = result[0] if result else 0
            conn.close()
        except Exception:
            num_followings = 0
        return self.follows_env_template.substitute(
            {"num_follows": num_followings})

    async def get_group_env(self) -> str:
        groups = await self.action.listen_from_group()
        if groups["success"]:
            all_groups = json.dumps(groups["all_groups"])
            joined_groups = json.dumps(groups["joined_groups"])
            messages = json.dumps(groups["messages"])
            groups_env = self.groups_env_template.substitute(
                all_groups=all_groups,
                joined_groups=joined_groups,
                messages=messages,
            )
        else:
            groups_env = "No groups."
        return groups_env

    async def get_economic_env(self, agent_id: int = None) -> str:
        """Get economic context for an agent's environment observation.

        Returns text describing the agent's wallet, subscriptions, and
        available products.
        """
        sections = []

        if agent_id is not None:
            # Try to get wallet info
            try:
                wallet_result = await self.action.perform_action(
                    None, "check_subscription_status")
                if (wallet_result and isinstance(wallet_result, dict)
                        and wallet_result.get("success")):
                    wallet = wallet_result.get("wallet", {})
                    subs = wallet_result.get("subscriptions", [])

                    if wallet:
                        sections.append(
                            f"Your wallet: "
                            f"${wallet.get('balance', 0):.2f} balance, "
                            f"${wallet.get('current_month_spent', 0):.2f} "
                            f"spent this month "
                            f"(limit: "
                            f"${wallet.get('monthly_spending_limit', 0):.2f})"
                        )

                    if subs:
                        sub_lines = []
                        for sub in subs:
                            sub_lines.append(
                                f"  - {sub.get('product_name', '?')} "
                                f"({sub.get('status', '?')}): "
                                f"satisfaction "
                                f"{sub.get('satisfaction_score', 5)}/10, "
                                f"{sub.get('months_active', 0)} months"
                            )
                        sections.append(
                            "Your subscriptions:\n" + "\n".join(sub_lines))
            except Exception:
                pass

            # Try to get product catalog
            try:
                products_result = await self.action.perform_action(
                    None, "browse_products")
                if (products_result and isinstance(products_result, dict)
                        and products_result.get("success")):
                    products = products_result.get("products", [])
                    if products:
                        prod_lines = []
                        for p in products:
                            tiers = p.get("tiers", [])
                            tier_text = ", ".join(
                                f"{t.get('tier_name', '?')}: "
                                f"${t.get('monthly_price', 0)}/mo"
                                for t in tiers
                            ) if tiers else f"${p.get('base_price', 0)}/mo"
                            prod_lines.append(
                                f"  - {p.get('product_name', '?')}: "
                                f"{tier_text}")
                        sections.append(
                            "Available products:\n" + "\n".join(prod_lines))
            except Exception:
                pass

        if sections:
            return "\n\n## ECONOMIC CONTEXT\n" + "\n\n".join(sections)
        return ""

    async def to_text_prompt(
        self,
        include_posts: bool = True,
        include_followers: bool = True,
        include_follows: bool = True,
        include_economic: bool = True,
    ) -> str:
        followers_env = (await self.get_followers_env()
                         if include_follows else "No followers.")
        follows_env = (await self.get_follows_env()
                       if include_followers else "No follows.")
        posts_env = await self.get_posts_env() if include_posts else ""

        base_prompt = self.env_template.substitute(
            followers_env=followers_env,
            follows_env=follows_env,
            posts_env=posts_env,
            groups_env=await self.get_group_env(),
        )

        if include_economic:
            economic_env = await self.get_economic_env(
                agent_id=self.action.agent_id)
            base_prompt += economic_env

        return base_prompt
