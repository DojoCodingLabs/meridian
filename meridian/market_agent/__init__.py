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
# Lazy imports — heavy OASIS modules (camel, torch) loaded only when needed.
# Lightweight modules (economic_behavior, segment) import without dependencies.


def __getattr__(name):
    _lazy = {
        "SocialAgent": ".agent",
        "AgentGraph": ".agent_graph",
        "generate_agents_100w": ".agents_generator",
        "generate_reddit_agent_graph": ".agents_generator",
        "generate_twitter_agent_graph": ".agents_generator",
    }
    if name in _lazy:
        import importlib
        module = importlib.import_module(_lazy[name], package=__name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SocialAgent", "AgentGraph", "generate_agents_100w",
    "generate_reddit_agent_graph", "generate_twitter_agent_graph",
]
