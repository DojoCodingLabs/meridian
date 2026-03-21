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
from typing import Any

from camel.toolkits import FunctionTool

from meridian.market_platform.channel import Channel
from meridian.market_platform.typing import ActionType


class SocialAction:

    def __init__(self, agent_id: int, channel: Channel):
        self.agent_id = agent_id
        self.channel = channel

    def get_openai_function_list(self) -> list[FunctionTool]:
        return [
            FunctionTool(func) for func in [
                self.create_post,
                self.like_post,
                self.repost,
                self.quote_post,
                self.unlike_post,
                self.dislike_post,
                self.undo_dislike_post,
                self.search_posts,
                self.search_user,
                self.trend,
                self.refresh,
                self.do_nothing,
                self.create_comment,
                self.like_comment,
                self.dislike_comment,
                self.unlike_comment,
                self.undo_dislike_comment,
                self.follow,
                self.unfollow,
                self.mute,
                self.unmute,
                self.purchase_product,
                self.interview,
                self.report_post,
                self.join_group,
                self.leave_group,
                self.send_to_group,
                self.create_group,
                self.listen_from_group,
                self.browse_products,
                self.compare_products,
                self.view_product_details,
                self.start_trial,
                self.end_trial,
                self.subscribe,
                self.upgrade_tier,
                self.downgrade_tier,
                self.cancel_subscription,
                self.renew_subscription,
                self.write_review,
                self.refer_friend,
                self.request_refund,
                self.set_budget,
                self.evaluate_alternatives,
                self.react_to_price,
                self.check_subscription_status,
                self.browse_reviews,
            ]
        ]

    async def perform_action(self, message: Any, type: str):
        message_id = await self.channel.write_to_receive_queue(
            (self.agent_id, message, type))
        response = await self.channel.read_from_send_queue(message_id)
        return response[2]

    async def sign_up(self, user_name: str, name: str, bio: str):
        r"""Signs up a new user with the provided username, name, and bio.

        This method prepares a user message comprising the user's details and
        invokes an asynchronous action to perform the sign-up process. On
        successful execution, it returns a dictionary indicating success along
        with the newly created user ID.

        Args:
            user_name (str): The username for the new user.
            name (str): The full name of the new user.
            bio (str): A brief biography of the new user.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the sign-up was
                successful, and 'user_id' key maps to the integer ID of the
                newly created user on success.

            Example of a successful return:
            {'success': True, 'user_id': 2}
        """

        # print(f"Agent {self.agent_id} is signing up with "
        #       f"user_name: {user_name}, name: {name}, bio: {bio}")
        user_message = (user_name, name, bio)
        return await self.perform_action(user_message, ActionType.SIGNUP.value)

    async def refresh(self):
        r"""Refresh to get recommended posts.

        This method invokes an asynchronous action to refresh and fetch
        recommended posts. On successful execution, it returns a dictionary
        indicating success along with a list of posts. Each post in the list
        contains details such as post ID, user ID, content, creation date,
        and the number of likes.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the refresh is
                successful. The 'posts' key maps to a list of dictionaries,
                each representing a post with its details.

            Example of a successful return:
            {
                "success": True,
                "posts": [
                    {
                        "post_id": 1,
                        "user_id": 23,
                        "content": "This is an example post content.",
                        "created_at": "2024-05-14T12:00:00Z",
                        "num_likes": 5
                    },
                    {
                        "post_id": 2,
                        "user_id": 42,
                        "content": "Another example post content.",
                        "created_at": "2024-05-14T12:05:00Z",
                        "num_likes": 15
                    }
                ]
            }
        """
        return await self.perform_action(None, ActionType.REFRESH.value)

    async def do_nothing(self):
        """Perform no action.
        Returns:
            dict: A dictionary with 'success' indicating if the removal was
                successful.
            Example of a successful return:
                {"success": True}
        """
        return await self.perform_action(None, ActionType.DO_NOTHING.value)

    async def create_post(self, content: str):
        r"""Create a new post with the given content.

        This method invokes an asynchronous action to create a new post based
        on the provided content. Upon successful execution, it returns a
        dictionary indicating success and the ID of the newly created post.

        Args:
            content (str): The content of the post to be created.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the post creation was
                successful. The 'post_id' key maps to the integer ID of the
                newly created post.

            Example of a successful return:
            {'success': True, 'post_id': 50}
        """
        return await self.perform_action(content, ActionType.CREATE_POST.value)

    async def repost(self, post_id: int):
        r"""Repost a specified post.

        This method invokes an asynchronous action to Repost a specified
        post. It is identified by the given post ID. Upon successful
        execution, it returns a dictionary indicating success and the ID of
        the newly created repost.

        Args:
            post_id (int): The ID of the post to be reposted.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the Repost creation was
                successful. The 'post_id' key maps to the integer ID of the
                newly created repost.

            Example of a successful return:
            {"success": True, "post_id": 123}

        Note:
            Attempting to repost a post that the user has already reposted
            will result in a failure.
        """
        return await self.perform_action(post_id, ActionType.REPOST.value)

    async def quote_post(self, post_id: int, quote_content: str):
        r"""Quote a specified post with a given quote content.

        This method invokes an asynchronous action to quote a specified post
        with a given quote content. Upon successful execution, it returns a
        dictionary indicating success and the ID of the newly created quote.

        Args:
            post_id (int): The ID of the post to be quoted.
            quote_content (str): The content of the quote to be created.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the quote creation was
                successful. The 'post_id' key maps to the integer ID of the
                newly created quote.

            Example of a successful return:
            {"success": True, "post_id": 123}

        Note:
            Attempting to quote a post that the user has already quoted will
            result in a failure.
        """
        quote_message = (post_id, quote_content)
        return await self.perform_action(quote_message, ActionType.QUOTE_POST)

    async def like_post(self, post_id: int):
        r"""Create a new like for a specified post.

        This method invokes an asynchronous action to create a new like for a
        post. It is identified by the given post ID. Upon successful
        execution, it returns a dictionary indicating success and the ID of
        the newly created like.

        Args:
            post_id (int): The ID of the post to be liked.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the like creation was
                successful. The 'like_id' key maps to the integer ID of the
                newly created like.

            Example of a successful return:
            {"success": True, "like_id": 123}

        Note:
            Attempting to like a post that the user has already liked will
            result in a failure.
        """
        return await self.perform_action(post_id, ActionType.LIKE_POST.value)

    async def unlike_post(self, post_id: int):
        """Remove a like for a post.

        This method removes a like from the database, identified by the
        post's ID. It returns a dictionary indicating the success of the
        operation and the ID of the removed like.

        Args:
            post_id (int): The ID of the post to be unliked.

        Returns:
            dict: A dictionary with 'success' indicating if the removal was
                successful, and 'like_id' the ID of the removed like.

            Example of a successful return:
            {"success": True, "like_id": 123}

        Note:
            Attempting to remove a like for a post that the user has not
            previously liked will result in a failure.
        """
        return await self.perform_action(post_id, ActionType.UNLIKE_POST.value)

    async def dislike_post(self, post_id: int):
        r"""Create a new dislike for a specified post.

        This method invokes an asynchronous action to create a new dislike for
        a post. It is identified by the given post ID. Upon successful
        execution, it returns a dictionary indicating success and the ID of
        the newly created dislike.

        Args:
            post_id (int): The ID of the post to be disliked.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the dislike creation was
                successful. The 'dislike_id' key maps to the integer ID of the
                newly created like.

            Example of a successful return:
            {"success": True, "dislike_id": 123}

        Note:
            Attempting to dislike a post that the user has already liked will
            result in a failure.
        """
        return await self.perform_action(post_id,
                                         ActionType.DISLIKE_POST.value)

    async def undo_dislike_post(self, post_id: int):
        """Remove a dislike for a post.

        This method removes a dislike from the database, identified by the
        post's ID. It returns a dictionary indicating the success of the
        operation and the ID of the removed dislike.

        Args:
            post_id (int): The ID of the post to be unliked.

        Returns:
            dict: A dictionary with 'success' indicating if the removal was
                successful, and 'dislike_id' the ID of the removed like.

            Example of a successful return:
            {"success": True, "dislike_id": 123}

        Note:
            Attempting to remove a dislike for a post that the user has not
            previously liked will result in a failure.
        """
        return await self.perform_action(post_id,
                                         ActionType.UNDO_DISLIKE_POST.value)

    async def search_posts(self, query: str):
        r"""Search posts based on a given query.

        This method performs a search operation in the database for posts
        that match the given query string. The search considers the
        post's content, post ID, and user ID. It returns a dictionary
        indicating the operation's success and, if successful, a list of
        posts that match the query.

        Args:
            query (str): The search query string. The search is performed
                against the post's content, post ID, and user ID.

        Returns:
            dict: A dictionary with a 'success' key indicating the operation's
                success. On success, it includes a 'posts' key with a list of
                dictionaries, each representing a post. On failure, it
                includes an 'error' message or a 'message' indicating no
                posts were found.

            Example of a successful return:
            {
                "success": True,
                "posts": [
                    {
                        "post_id": 1,
                        "user_id": 42,
                        "content": "Hello, world!",
                        "created_at": "2024-05-14T12:00:00Z",
                        "num_likes": 150
                    },
                    ...
                ]
            }
        """
        return await self.perform_action(query, ActionType.SEARCH_POSTS.value)

    async def search_user(self, query: str):
        r"""Search users based on a given query.

        This asynchronous method performs a search operation in the database
        for users that match the given query string. The search considers the
        user's username, name, bio, and user ID. It returns a dictionary
        indicating the operation's success and, if successful, a list of users
        that match the query.

        Args:
            query (str): The search query string. The search is performed
                against the user's username, name, bio, and user ID.

        Returns:
            dict: A dictionary with a 'success' key indicating the operation's
                success. On success, it includes a 'users' key with a list of
                dictionaries, each representing a user. On failure, it includes
                an 'error' message or a 'message' indicating no users were
                found.

            Example of a successful return:
            {
                "success": True,
                "users": [
                    {
                        "user_id": 1,
                        "user_name": "exampleUser",
                        "name": "John Doe",
                        "bio": "This is an example bio",
                        "created_at": "2024-05-14T12:00:00Z",
                        "num_followings": 100,
                        "num_followers": 150
                    },
                    ...
                ]
            }
        """
        return await self.perform_action(query, ActionType.SEARCH_USER.value)

    async def follow(self, followee_id: int):
        r"""Follow a user.

        This method allows agent to follow another user (followee).
        It checks if the agent initiating the follow request has a
        corresponding user ID and if the follow relationship already exists.

        Args:
            followee_id (int): The user ID of the user to be followed.

        Returns:
            dict: A dictionary with a 'success' key indicating the operation's
                success. On success, it includes a 'follow_id' key with the ID
                of the newly created follow record. On failure, it includes an
                'error' message.

            Example of a successful return:
            {"success": True, "follow_id": 123}
        """
        return await self.perform_action(followee_id, ActionType.FOLLOW.value)

    async def unfollow(self, followee_id: int):
        r"""Unfollow a user.

        This method allows agent to unfollow another user (followee). It
        checks if the agent initiating the unfollow request has a
        corresponding user ID and if the follow relationship exists. If so,
        it removes the follow record from the database, updates the followers
        and followings count for both users, and logs the action.

        Args:
            followee_id (int): The user ID of the user to be unfollowed.

        Returns:
            dict: A dictionary with a 'success' key indicating the operation's
                success. On success, it includes a 'follow_id' key with the ID
                of the removed follow record. On failure, it includes an
                'error' message.

            Example of a successful return:
            {"success": True, "follow_id": 123}
        """
        return await self.perform_action(followee_id,
                                         ActionType.UNFOLLOW.value)

    async def mute(self, mutee_id: int):
        r"""Mute a user.

        Allows agent to mute another user. Checks for an existing mute
        record before adding a new one to the database.

        Args:
            mutee_id (int): ID of the user to be muted.

        Returns:
            dict: On success, returns a dictionary with 'success': True and
                mute_id' of the new record. On failure, returns 'success':
                False and an 'error' message.

            Example of a successful return:
            {"success": True, "mutee_id": 123}
        """
        return await self.perform_action(mutee_id, ActionType.MUTE.value)

    async def unmute(self, mutee_id: int):
        r"""Unmute a user.

        Allows agent to remove a mute on another user. Checks for an
        existing mute record before removing it from the database.

        Args:
            mutee_id (int): ID of the user to be unmuted.

        Returns:
            dict: On success, returns a dictionary with 'success': True and
                'mutee_id' of the unmuted record. On failure, returns
                'success': False and an 'error' message.

            Example of a successful return:
            {"success": True, "mutee_id": 123}
        """
        return await self.perform_action(mutee_id, ActionType.UNMUTE.value)

    async def trend(self):
        r"""Fetch the trending posts within a predefined time period.

        Retrieves the top K posts with the most likes in the last specified
        number of days.

        Returns:
            dict: On success, returns a dictionary with 'success': True and a
                list of 'posts', each post being a dictionary containing
                'post_id', 'user_id', 'content', 'created_at', and
                'num_likes'. On failure, returns 'success': False and an
                'error' message or a message indicating no trending posts
                were found.

            Example of a successful return:
            {
                "success": True,
                "posts": [
                    {
                        "post_id": 123,
                        "user_id": 456,
                        "content": "Example post content",
                        "created_at": "2024-05-14T12:00:00",
                        "num_likes": 789
                    },
                    ...
                ]
            }
        """
        return await self.perform_action(None, ActionType.TREND.value)

    async def create_comment(self, post_id: int, content: str):
        r"""Create a new comment for a specified post given content.

        This method creates a new comment based on the provided content and
        associates it with the given post ID. Upon successful execution, it
        returns a dictionary indicating success and the ID of the newly created
        comment.

        Args:
            post_id (int): The ID of the post to which the comment is to be
                added.
            content (str): The content of the comment to be created.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the comment creation was
                successful. The 'comment_id' key maps to the integer ID of the
                newly created comment.

            Example of a successful return:
                {'success': True, 'comment_id': 123}
        """
        comment_message = (post_id, content)
        return await self.perform_action(comment_message,
                                         ActionType.CREATE_COMMENT.value)

    async def like_comment(self, comment_id: int):
        r"""Create a new like for a specified comment.

        This method invokes an action to create a new like for a comment,
        identified by the given comment ID. Upon successful execution, it
        returns a dictionary indicating success and the ID of the newly
        created like.

        Args:
            comment_id (int): The ID of the comment to be liked.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the like creation was
                successful. The 'like_id' key maps to the integer ID of the
                newly created like.

            Example of a successful return:
            {"success": True, "comment_like_id": 456}

        Note:
            Attempting to like a comment that the user has already liked will
            result in a failure.
        """
        return await self.perform_action(comment_id,
                                         ActionType.LIKE_COMMENT.value)

    async def unlike_comment(self, comment_id: int):
        """Remove a like for a comment based on the comment's ID.

        This method removes a like from the database, identified by the
        comment's ID. It returns a dictionary indicating the success of the
        operation and the ID of the removed like.

        Args:
            comment_id (int): The ID of the comment to be unliked.

        Returns:
            dict: A dictionary with 'success' indicating if the removal was
                successful, and 'like_id' the ID of the removed like.

            Example of a successful return:
            {"success": True, "like_id": 456}

        Note:
            Attempting to remove a like for a comment that the user has not
            previously liked will result in a failure.
        """
        return await self.perform_action(comment_id,
                                         ActionType.UNLIKE_COMMENT.value)

    async def dislike_comment(self, comment_id: int):
        r"""Create a new dislike for a specified comment.

        This method invokes an action to create a new dislike for a
        comment, identified by the given comment ID. Upon successful execution,
        it returns a dictionary indicating success and the ID of the newly
        created dislike.

        Args:
            comment_id (int): The ID of the comment to be disliked.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the dislike creation was
                successful. The 'dislike_id' key maps to the integer ID of the
                newly created dislike.

            Example of a successful return:
            {"success": True, "comment_dislike_id": 456}

        Note:
            Attempting to dislike a comment that the user has already liked
            will result in a failure.
        """
        return await self.perform_action(comment_id,
                                         ActionType.DISLIKE_COMMENT.value)

    async def undo_dislike_comment(self, comment_id: int):
        """Remove a dislike for a comment.

        This method removes a dislike from the database, identified by the
        comment's ID. It returns a dictionary indicating the success of the
        operation and the ID of the removed dislike.

        Args:
            comment_id (int): The ID of the comment to have the dislike
                removed.

        Returns:
            dict: A dictionary with 'success' indicating if the removal was
                successful, and 'dislike_id' the ID of the removed dislike.

            Example of a successful return:
            {"success": True, "dislike_id": 456}

        Note:
            Attempting to remove a dislike for a comment that the user has not
            previously disliked will result in a failure.
        """
        return await self.perform_action(comment_id,
                                         ActionType.UNDO_DISLIKE_COMMENT.value)

    async def purchase_product(self, product_name: str, purchase_num: int):
        r"""Purchase a product.

        Args:
            product_name (str): The name of the product to be purchased.
            purchase_num (int): The number of products to be purchased.

        Returns:
            dict: A dictionary with 'success' indicating if the purchase was
                successful.
        """
        purchase_message = (product_name, purchase_num)
        return await self.perform_action(purchase_message,
                                         ActionType.PURCHASE_PRODUCT.value)

    async def interview(self, prompt: str):
        r"""Interview an agent with the given prompt.

        This method invokes an asynchronous action to interview an agent with a
        specific prompt question. Upon successful execution,
        it returns a dictionary containing a success status
        and an interview_id for tracking.

        Args:
            prompt (str): The interview question or prompt to ask the agent.

        Returns:
            dict: A dictionary containing success status and an interview_id.

            Example of a successful return:
            {
                "success": True,
                "interview_id": "1621234567_0"  # Timestamp_UserID format
            }
        """
        return await self.perform_action(prompt, ActionType.INTERVIEW.value)

    async def report_post(self, post_id: int, report_reason: str):
        r"""Report a specified post with a given reason.

        This method invokes an asynchronous action to report a specified post
        with a given reason. Upon successful execution, it returns a
        dictionary indicating success and the ID of the newly created report.

        Args:
            post_id (int): The ID of the post to be reported.
            report_reason (str): The reason for reporting the post.

        Returns:
            dict: A dictionary with two key-value pairs. The 'success' key
                maps to a boolean indicating whether the report creation was
                successful. The 'report_id' key maps to the integer ID of the
                newly created report.

            Example of a successful return:
            {"success": True, "report_id": 123}

        Note:
            Attempting to report a post that the user has already reported will
            result in a failure.
        """
        report_message = (post_id, report_reason)
        return await self.perform_action(report_message,
                                         ActionType.REPORT_POST.value)

    async def create_group(self, group_name: str):
        r"""Creates a new group on the platform.

        Args:
            group_name (str): The name of the group to be created.

        Returns:
            dict: Platform response indicating success or failure,
            e.g.{"success": True, "group_id": 1}
        """
        return await self.perform_action(group_name,
                                         ActionType.CREATE_GROUP.value)

    async def join_group(self, group_id: int):
        r"""Joins a group with the specified ID.

        Args:
            group_id (int): The ID of the group to join.

        Returns:
            dict: Platform response indicating success or failure,
            e.g. {"success": True}
        """
        return await self.perform_action(group_id, ActionType.JOIN_GROUP.value)

    async def leave_group(self, group_id: int):
        r"""Leaves a group with the specified ID.

        Args:
            group_id (int): The ID of the group to leave.

        Returns:
            dict: Platform response indicating success or failure, e.g.
            {"success": True}
        """
        return await self.perform_action(group_id,
                                         ActionType.LEAVE_GROUP.value)

    async def send_to_group(self, group_id: int, message: str):
        r"""Sends a message to a specific group.

        Args:
            group_id (int): The ID of the target group.
            message (str): The content of the message to send.

        Returns:
            dict: Platform response indicating success or failure, e.g.
             {"success": True, "message_id": 123}
        """
        return await self.perform_action((group_id, message),
                                         ActionType.SEND_TO_GROUP.value)

    async def listen_from_group(self):
        r"""Listen messages from groups"""
        return await self.perform_action(self.agent_id,
                                         ActionType.LISTEN_FROM_GROUP.value)

    # ===================== Economic Actions =====================

    async def browse_products(self) -> dict:
        r"""Browse available products and their pricing tiers. Returns a
        catalog of products with prices, features, and ratings.

        Use this to discover what products are available before making
        purchase decisions.

        Returns:
            dict: A dictionary with 'success' indicating if the browse was
                successful, and 'products' containing a list of available
                products with their tiers and pricing.

            Example of a successful return:
            {
                "success": True,
                "products": [
                    {
                        "product_id": 1,
                        "product_name": "StreamVault",
                        "category": "streaming",
                        "tiers": [...]
                    }
                ]
            }
        """
        message = None
        return await self.perform_action(
            message, ActionType.BROWSE_PRODUCTS.value)

    async def compare_products(self, product_a: str, product_b: str) -> dict:
        r"""Compare two products side by side. Returns features, pricing,
        reviews, and social proof for each.

        Args:
            product_a (str): Name of the first product to compare.
            product_b (str): Name of the second product to compare.

        Returns:
            dict: A dictionary with 'success' and comparison data for both
                products including tiers, reviews, and subscriber counts.

            Example of a successful return:
            {
                "success": True,
                "product_a": {...},
                "product_b": {...}
            }
        """
        message = (product_a, product_b)
        return await self.perform_action(
            message, ActionType.COMPARE_PRODUCTS.value)

    async def view_product_details(self, product_name: str) -> dict:
        r"""View detailed information about a specific product including all
        tiers, features, and reviews.

        Args:
            product_name (str): Name of the product to view.

        Returns:
            dict: A dictionary with 'success' and detailed product info
                including tiers, features, and reviews.

            Example of a successful return:
            {
                "success": True,
                "product": {
                    "product_name": "StreamVault",
                    "tiers": [...],
                    "features": [...],
                    "reviews": [...]
                }
            }
        """
        message = product_name
        return await self.perform_action(
            message, ActionType.VIEW_PRODUCT_DETAILS.value)

    async def start_trial(self, product_name: str) -> dict:
        r"""Start a free trial for a product. Only works if the product
        offers a trial period.

        Args:
            product_name (str): Name of the product to trial.

        Returns:
            dict: A dictionary with 'success' and trial details including
                trial_id and trial end date.

            Example of a successful return:
            {"success": True, "trial_id": 1, "ends_at": "2024-06-14"}
        """
        message = product_name
        return await self.perform_action(
            message, ActionType.START_TRIAL.value)

    async def end_trial(self, product_name: str, reason: str) -> dict:
        r"""End a trial early without converting to paid.

        Args:
            product_name (str): Product to stop trialing.
            reason (str): Why you're ending the trial early.

        Returns:
            dict: A dictionary with 'success' indicating if the trial was
                ended successfully.

            Example of a successful return:
            {"success": True, "trial_id": 1}
        """
        message = (product_name, reason)
        return await self.perform_action(
            message, ActionType.END_TRIAL.value)

    async def subscribe(self, product_name: str, tier_name: str) -> dict:
        r"""Subscribe to a paid product tier. This will charge your monthly
        budget. Only subscribe if you've evaluated the product and believe
        it provides genuine value.

        Args:
            product_name (str): Name of the product to subscribe to.
            tier_name (str): Name of the pricing tier (e.g., 'pro', 'vip',
                'starter').

        Returns:
            dict: A dictionary with 'success' and subscription details
                including subscription_id and amount charged.

            Example of a successful return:
            {"success": True, "subscription_id": 1, "amount_charged": 9.99}
        """
        message = (product_name, tier_name)
        return await self.perform_action(
            message, ActionType.SUBSCRIBE.value)

    async def upgrade_tier(self, product_name: str, new_tier: str) -> dict:
        r"""Upgrade your subscription to a higher tier.

        Args:
            product_name (str): Product to upgrade.
            new_tier (str): Name of the new higher tier.

        Returns:
            dict: A dictionary with 'success' and updated subscription
                details.

            Example of a successful return:
            {"success": True, "subscription_id": 1, "new_tier": "pro"}
        """
        message = (product_name, new_tier)
        return await self.perform_action(
            message, ActionType.UPGRADE_TIER.value)

    async def downgrade_tier(self, product_name: str, new_tier: str) -> dict:
        r"""Downgrade your subscription to a lower tier to save money.

        Args:
            product_name (str): Product to downgrade.
            new_tier (str): Name of the new lower tier.

        Returns:
            dict: A dictionary with 'success' and updated subscription
                details.

            Example of a successful return:
            {"success": True, "subscription_id": 1, "new_tier": "basic"}
        """
        message = (product_name, new_tier)
        return await self.perform_action(
            message, ActionType.DOWNGRADE_TIER.value)

    async def cancel_subscription(self, product_name: str,
                                  reason: str) -> dict:
        r"""Cancel your paid subscription to a product.

        Args:
            product_name (str): Product to cancel.
            reason (str): Why you're canceling (e.g., 'too expensive',
                'not using it', 'found better alternative').

        Returns:
            dict: A dictionary with 'success' indicating if the
                cancellation was successful.

            Example of a successful return:
            {"success": True, "subscription_id": 1}
        """
        message = (product_name, reason)
        return await self.perform_action(
            message, ActionType.CANCEL_SUBSCRIPTION.value)

    async def renew_subscription(self, product_name: str) -> dict:
        r"""Explicitly renew your subscription for another period.

        Args:
            product_name (str): Product to renew.

        Returns:
            dict: A dictionary with 'success' and renewal details.

            Example of a successful return:
            {"success": True, "subscription_id": 1, "renewed_until": "..."}
        """
        message = product_name
        return await self.perform_action(
            message, ActionType.RENEW_SUBSCRIPTION.value)

    async def write_review(self, product_name: str, rating: int,
                           review_text: str) -> dict:
        r"""Write a review for a product you've used. Be honest about your
        experience.

        Args:
            product_name (str): Product to review.
            rating (int): Star rating from 1 to 5.
            review_text (str): Your honest review of the product.

        Returns:
            dict: A dictionary with 'success' and the review_id.

            Example of a successful return:
            {"success": True, "review_id": 1}
        """
        message = (product_name, rating, review_text)
        return await self.perform_action(
            message, ActionType.WRITE_REVIEW.value)

    async def refer_friend(self, product_name: str,
                           recommendation_text: str) -> dict:
        r"""Recommend a product to your network by creating a
        recommendation post.

        Args:
            product_name (str): Product you're recommending.
            recommendation_text (str): Your recommendation message.

        Returns:
            dict: A dictionary with 'success', 'referral_id', and 'post_id'
                of the recommendation post created.

            Example of a successful return:
            {"success": True, "referral_id": 1, "post_id": 50}
        """
        message = (product_name, recommendation_text)
        return await self.perform_action(
            message, ActionType.REFER_FRIEND.value)

    async def request_refund(self, product_name: str, reason: str) -> dict:
        r"""Request a refund for a product you're unsatisfied with.

        Args:
            product_name (str): Product to request refund for.
            reason (str): Why you want a refund.

        Returns:
            dict: A dictionary with 'success' and refund details.

            Example of a successful return:
            {"success": True, "refund_amount": 9.99, "transaction_id": 5}
        """
        message = (product_name, reason)
        return await self.perform_action(
            message, ActionType.REQUEST_REFUND.value)

    async def set_budget(self, new_monthly_limit: float) -> dict:
        r"""Adjust your monthly spending budget for digital products and
        subscriptions.

        Args:
            new_monthly_limit (float): New monthly spending limit in dollars.

        Returns:
            dict: A dictionary with 'success' and updated budget info.

            Example of a successful return:
            {"success": True, "monthly_spending_limit": 50.0}
        """
        message = new_monthly_limit
        return await self.perform_action(
            message, ActionType.SET_BUDGET.value)

    async def evaluate_alternatives(self, current_product: str) -> dict:
        r"""Evaluate alternative products to what you currently use. Returns
        competitor comparisons.

        Args:
            current_product (str): The product you want to find alternatives
                for.

        Returns:
            dict: A dictionary with 'success' and a list of alternative
                products with comparison details.

            Example of a successful return:
            {
                "success": True,
                "current_product": "StreamVault",
                "alternatives": [...]
            }
        """
        message = current_product
        return await self.perform_action(
            message, ActionType.EVALUATE_ALTERNATIVES.value)

    async def react_to_price(self, product_name: str, tier_name: str,
                             reaction: str) -> dict:
        r"""Record your reaction to a product's pricing.

        Args:
            product_name (str): Product whose price you're reacting to.
            tier_name (str): Specific tier you're evaluating.
            reaction (str): Your reaction: 'accepted', 'rejected',
                'compared', or 'deferred'.

        Returns:
            dict: A dictionary with 'success' and the reaction_id.

            Example of a successful return:
            {"success": True, "reaction_id": 1}
        """
        message = (product_name, tier_name, reaction)
        return await self.perform_action(
            message, ActionType.REACT_TO_PRICE.value)

    async def check_subscription_status(self) -> dict:
        r"""Check the status of all your current subscriptions, trials, and
        spending.

        Returns:
            dict: A dictionary with 'success' and subscription/wallet
                details.

            Example of a successful return:
            {
                "success": True,
                "subscriptions": [...],
                "wallet": {"balance": 100.0, "current_month_spent": 25.0}
            }
        """
        message = None
        return await self.perform_action(
            message, ActionType.CHECK_SUBSCRIPTION_STATUS.value)

    async def browse_reviews(self, product_name: str) -> dict:
        r"""Read reviews written by other users about a product.

        Args:
            product_name (str): Product to read reviews for.

        Returns:
            dict: A dictionary with 'success' and a list of reviews.

            Example of a successful return:
            {
                "success": True,
                "reviews": [
                    {
                        "review_id": 1,
                        "user_id": 5,
                        "rating": 4,
                        "content": "Great product!",
                        "created_at": "2024-05-14"
                    }
                ]
            }
        """
        message = product_name
        return await self.perform_action(
            message, ActionType.BROWSE_REVIEWS.value)
