# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from enum import Enum


class ActionType(Enum):
    EXIT = "exit"
    REFRESH = "refresh"
    SEARCH_USER = "search_user"
    SEARCH_POSTS = "search_posts"
    CREATE_POST = "create_post"
    LIKE_POST = "like_post"
    UNLIKE_POST = "unlike_post"
    DISLIKE_POST = "dislike_post"
    UNDO_DISLIKE_POST = "undo_dislike_post"
    REPORT_POST = "report_post"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"
    MUTE = "mute"
    UNMUTE = "unmute"
    TREND = "trend"
    SIGNUP = "sign_up"
    REPOST = "repost"
    QUOTE_POST = "quote_post"
    UPDATE_REC_TABLE = "update_rec_table"
    CREATE_COMMENT = "create_comment"
    LIKE_COMMENT = "like_comment"
    UNLIKE_COMMENT = "unlike_comment"
    DISLIKE_COMMENT = "dislike_comment"
    UNDO_DISLIKE_COMMENT = "undo_dislike_comment"
    DO_NOTHING = "do_nothing"
    PURCHASE_PRODUCT = "purchase_product"
    INTERVIEW = "interview"
    JOIN_GROUP = "join_group"
    LEAVE_GROUP = "leave_group"
    SEND_TO_GROUP = "send_to_group"
    CREATE_GROUP = "create_group"
    LISTEN_FROM_GROUP = "listen_from_group"

    # Economic actions
    BROWSE_PRODUCTS = "browse_products"
    COMPARE_PRODUCTS = "compare_products"
    VIEW_PRODUCT_DETAILS = "view_product_details"
    START_TRIAL = "start_trial"
    END_TRIAL = "end_trial"
    SUBSCRIBE = "subscribe"
    UPGRADE_TIER = "upgrade_tier"
    DOWNGRADE_TIER = "downgrade_tier"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    RENEW_SUBSCRIPTION = "renew_subscription"
    WRITE_REVIEW = "write_review"
    REFER_FRIEND = "refer_friend"
    REQUEST_REFUND = "request_refund"
    SET_BUDGET = "set_budget"
    EVALUATE_ALTERNATIVES = "evaluate_alternatives"
    REACT_TO_PRICE = "react_to_price"
    CHECK_SUBSCRIPTION_STATUS = "check_subscription_status"
    BROWSE_REVIEWS = "browse_reviews"

    @classmethod
    def get_default_twitter_actions(cls):
        return [
            cls.CREATE_POST,
            cls.LIKE_POST,
            cls.REPOST,
            cls.FOLLOW,
            cls.DO_NOTHING,
            cls.QUOTE_POST,
        ]

    @classmethod
    def get_default_reddit_actions(cls):
        return [
            cls.LIKE_POST,
            cls.DISLIKE_POST,
            cls.CREATE_POST,
            cls.CREATE_COMMENT,
            cls.LIKE_COMMENT,
            cls.DISLIKE_COMMENT,
            cls.SEARCH_POSTS,
            cls.SEARCH_USER,
            cls.TREND,
            cls.REFRESH,
            cls.DO_NOTHING,
            cls.FOLLOW,
            cls.MUTE,
        ]

    @classmethod
    def get_marketplace_actions(cls):
        """Social + economic actions for product prediction."""
        return [
            cls.REFRESH, cls.CREATE_POST, cls.LIKE_POST, cls.DISLIKE_POST,
            cls.CREATE_COMMENT, cls.FOLLOW, cls.SEARCH_POSTS,
            cls.BROWSE_PRODUCTS, cls.COMPARE_PRODUCTS, cls.VIEW_PRODUCT_DETAILS,
            cls.START_TRIAL, cls.SUBSCRIBE, cls.CANCEL_SUBSCRIPTION,
            cls.WRITE_REVIEW, cls.REFER_FRIEND, cls.EVALUATE_ALTERNATIVES,
            cls.BROWSE_REVIEWS, cls.DO_NOTHING,
        ]


class RecsysType(Enum):
    TWITTER = "twitter"
    TWHIN = "twhin-bert"
    REDDIT = "reddit"
    RANDOM = "random"


class DefaultPlatformType(Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
