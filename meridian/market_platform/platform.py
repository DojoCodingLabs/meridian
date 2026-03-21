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

import asyncio
import logging
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Any

from meridian.clock.clock import Clock
from meridian.market_platform.channel import Channel
from meridian.market_platform.database import (create_db,
                                            fetch_rec_table_as_matrix,
                                            fetch_table_from_db)
from meridian.market_platform.platform_utils import PlatformUtils
from meridian.market_platform.recsys import (rec_sys_personalized_twh,
                                          rec_sys_personalized_with_trace,
                                          rec_sys_random, rec_sys_reddit)
from meridian.market_platform.typing import ActionType, RecsysType

# Create log directory if it doesn't exist
log_dir = "./log"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

if "sphinx" not in sys.modules:
    twitter_log = logging.getLogger(name="social.twitter")
    twitter_log.setLevel("DEBUG")
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_handler = logging.FileHandler(f"./log/social.twitter-{now}.log")
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
    twitter_log.addHandler(file_handler)


class Platform:
    r"""Platform."""

    def __init__(
        self,
        db_path: str,
        channel: Any = None,
        sandbox_clock: Clock | None = None,
        start_time: datetime | None = None,
        show_score: bool = False,
        allow_self_rating: bool = True,
        recsys_type: str | RecsysType = "reddit",
        refresh_rec_post_count: int = 1,
        max_rec_post_len: int = 2,
        following_post_count=3,
        use_openai_embedding: bool = False,
    ):
        self.db_path = db_path
        self.recsys_type = recsys_type
        # import pdb; pdb.set_trace()

        # If no clock is specified, default the platform's time
        # magnification factor to 60
        if sandbox_clock is None:
            sandbox_clock = Clock(60)
        if start_time is None:
            start_time = datetime.now()
        self.start_time = start_time
        self.sandbox_clock = sandbox_clock

        self.db, self.db_cursor = create_db(self.db_path)
        self.db.execute("PRAGMA synchronous = OFF")

        self.channel = channel or Channel()

        self.recsys_type = RecsysType(recsys_type)

        # Whether to simulate showing scores like Reddit (likes minus dislikes)
        # instead of showing likes and dislikes separately
        self.show_score = show_score

        # Whether to allow users to like or dislike their own posts and
        # comments
        self.allow_self_rating = allow_self_rating

        # The number of posts returned by the social media internal
        # recommendation system per refresh
        self.refresh_rec_post_count = refresh_rec_post_count
        # The number of posts returned at once from posts made by followed
        # users, ranked by like counts
        self.following_post_count = following_post_count
        # The maximum number of posts per user in the recommendation
        # table (buffer)
        self.max_rec_post_len = max_rec_post_len
        # rec prob between random and personalized
        self.rec_prob = 0.7
        self.use_openai_embedding = use_openai_embedding

        # Parameters for the platform's internal trending rules
        self.trend_num_days = 7
        self.trend_top_k = 1

        # Report threshold setting
        self.report_threshold = 2

        self.pl_utils = PlatformUtils(
            self.db,
            self.db_cursor,
            self.start_time,
            self.sandbox_clock,
            self.show_score,
            self.recsys_type,
            self.report_threshold,
        )

    async def running(self):
        while True:
            message_id, data = await self.channel.receive_from()

            agent_id, message, action = data
            action = ActionType(action)

            if action == ActionType.EXIT:
                # If the database is in-memory, save it to a file before
                # losing
                if self.db_path == ":memory:":
                    dst = sqlite3.connect("mock.db")
                    with dst:
                        self.db.backup(dst)

                self.db_cursor.close()
                self.db.close()
                break

            # Retrieve the corresponding function using getattr
            action_function = getattr(self, action.value, None)
            if action_function:
                # Get the names of the parameters of the function
                func_code = action_function.__code__
                param_names = func_code.co_varnames[:func_code.co_argcount]

                len_param_names = len(param_names)
                if len_param_names > 3:
                    raise ValueError(
                        f"Functions with {len_param_names} parameters are not "
                        f"supported.")
                # Build a dictionary of parameters
                params = {}
                if len_param_names >= 2:
                    params["agent_id"] = agent_id
                if len_param_names == 3:
                    # Assuming the second element in param_names is the name
                    # of the second parameter you want to add
                    second_param_name = param_names[2]
                    params[second_param_name] = message

                # Call the function with the parameters
                result = await action_function(**params)
                await self.channel.send_to((message_id, agent_id, result))
            else:
                raise ValueError(f"Action {action} is not supported")

    def run(self):
        asyncio.run(self.running())

    async def sign_up(self, agent_id, user_message):
        user_name, name, bio = user_message
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_insert_query = (
                "INSERT INTO user (user_id, agent_id, user_name, name, "
                "bio, created_at, num_followings, num_followers) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                user_insert_query,
                (agent_id, agent_id, user_name, name, bio, current_time, 0, 0),
                commit=True,
            )
            user_id = agent_id

            action_info = {"name": name, "user_name": user_name, "bio": bio}
            self.pl_utils._record_trace(user_id, ActionType.SIGNUP.value,
                                        action_info, current_time)
            # twitter_log.info(f"Trace inserted: user_id={user_id}, "
            #                  f"current_time={current_time}, "
            #                  f"action={ActionType.SIGNUP.value}, "
            #                  f"info={action_info}")
            return {"success": True, "user_id": user_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def sign_up_product(self, product_id: int, product_name: str):
        # Note: do not sign up the product with the same product name
        try:
            product_insert_query = (
                "INSERT INTO product (product_id, product_name) VALUES (?, ?)")
            self.pl_utils._execute_db_command(product_insert_query,
                                              (product_id, product_name),
                                              commit=True)
            return {"success": True, "product_id": product_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def purchase_product(self, agent_id, purchase_message):
        product_name, purchase_num = purchase_message
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        # try:
        user_id = agent_id
        # Check if a like record already exists
        product_check_query = (
            "SELECT * FROM 'product' WHERE product_name = ?")
        self.pl_utils._execute_db_command(product_check_query,
                                          (product_name, ))
        check_result = self.db_cursor.fetchone()
        if not check_result:
            # Product not found
            return {"success": False, "error": "No such product."}
        else:
            product_id = check_result[0]

        product_update_query = (
            "UPDATE product SET sales = sales + ? WHERE product_name = ?")
        self.pl_utils._execute_db_command(product_update_query,
                                          (purchase_num, product_name),
                                          commit=True)

        # Record the action in the trace table
        action_info = {
            "product_name": product_name,
            "purchase_num": purchase_num
        }
        self.pl_utils._record_trace(user_id, ActionType.PURCHASE_PRODUCT.value,
                                    action_info, current_time)
        return {"success": True, "product_id": product_id}
        # except Exception as e:
        #     return {"success": False, "error": str(e)}

    async def refresh(self, agent_id: int):
        # Retrieve posts for a specific id from the rec table
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id
            # Retrieve all post_ids for a given user_id from the rec table
            rec_query = "SELECT post_id FROM rec WHERE user_id = ?"
            self.pl_utils._execute_db_command(rec_query, (user_id, ))
            rec_results = self.db_cursor.fetchall()

            post_ids = [row[0] for row in rec_results]
            selected_post_ids = post_ids
            # If the number of post_ids >= self.refresh_rec_post_count,
            # randomly select a specified number of post_ids
            if len(selected_post_ids) >= self.refresh_rec_post_count:
                selected_post_ids = random.sample(selected_post_ids,
                                                  self.refresh_rec_post_count)

            if self.recsys_type != RecsysType.REDDIT:
                # Retrieve posts from following (in network)
                # Modify the SQL query so that the refresh gets posts from
                # people the user follows, sorted by the number of likes on
                # Twitter
                query_following_post = (
                    "SELECT post.post_id, post.user_id, post.content, "
                    "post.created_at, post.num_likes FROM post "
                    "JOIN follow ON post.user_id = follow.followee_id "
                    "WHERE follow.follower_id = ? "
                    "ORDER BY post.num_likes DESC "
                    "LIMIT ?")
                self.pl_utils._execute_db_command(
                    query_following_post,
                    (
                        user_id,
                        self.following_post_count,
                    ),
                )

                following_posts = self.db_cursor.fetchall()
                following_posts_ids = [row[0] for row in following_posts]

                selected_post_ids = following_posts_ids + selected_post_ids
                selected_post_ids = list(set(selected_post_ids))

            placeholders = ", ".join("?" for _ in selected_post_ids)

            post_query = (
                f"SELECT post_id, user_id, original_post_id, content, "
                f"quote_content, created_at, num_likes, num_dislikes, "
                f"num_shares FROM post WHERE post_id IN ({placeholders})")
            self.pl_utils._execute_db_command(post_query, selected_post_ids)
            results = self.db_cursor.fetchall()
            if not results:
                return {"success": False, "message": "No posts found."}
            results_with_comments = self.pl_utils._add_comments_to_posts(
                results)

            action_info = {"posts": results_with_comments}
            # twitter_log.info(action_info)
            self.pl_utils._record_trace(user_id, ActionType.REFRESH.value,
                                        action_info, current_time)

            return {"success": True, "posts": results_with_comments}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_rec_table(self):
        # Recsys(trace/user/post table), refresh rec table
        twitter_log.info("Starting to refresh recommendation system cache...")
        user_table = fetch_table_from_db(self.db_cursor, "user")
        post_table = fetch_table_from_db(self.db_cursor, "post")
        trace_table = fetch_table_from_db(self.db_cursor, "trace")
        rec_matrix = fetch_rec_table_as_matrix(self.db_cursor)

        if self.recsys_type == RecsysType.RANDOM:
            new_rec_matrix = rec_sys_random(post_table, rec_matrix,
                                            self.max_rec_post_len)
        elif self.recsys_type == RecsysType.TWITTER:
            new_rec_matrix = rec_sys_personalized_with_trace(
                user_table, post_table, trace_table, rec_matrix,
                self.max_rec_post_len)
        elif self.recsys_type == RecsysType.TWHIN:
            try:
                latest_post_time = post_table[-1]["created_at"]
                second_latest_post_time = post_table[-2]["created_at"] if len(
                    post_table) > 1 else latest_post_time
                post_query = """
                    SELECT COUNT(*)
                    FROM post
                    WHERE created_at = ? OR created_at = ?
                """
                self.pl_utils._execute_db_command(
                    post_query, (latest_post_time, second_latest_post_time))
                result = self.db_cursor.fetchone()
                latest_post_count = result[0]
                if not latest_post_count:
                    return {
                        "success": False,
                        "message": "Fail to get latest posts count"
                    }
                new_rec_matrix = rec_sys_personalized_twh(
                    user_table,
                    post_table,
                    latest_post_count,
                    trace_table,
                    rec_matrix,
                    self.max_rec_post_len,
                    self.sandbox_clock.time_step,
                    use_openai_embedding=self.use_openai_embedding,
                )
            except Exception as e:
                twitter_log.error(e)
                # If no post in the platform, skip updating the rec table
                return
        elif self.recsys_type == RecsysType.REDDIT:
            new_rec_matrix = rec_sys_reddit(post_table, rec_matrix,
                                            self.max_rec_post_len)
        else:
            raise ValueError("Unsupported recommendation system type, please "
                             "check the `RecsysType`.")

        sql_query = "DELETE FROM rec"
        # Execute the SQL statement using the _execute_db_command function
        self.pl_utils._execute_db_command(sql_query, commit=True)

        # Batch insertion is more time-efficient
        # create a list of values to insert
        insert_values = [(user_id, post_id)
                         for user_id in range(len(new_rec_matrix))
                         for post_id in new_rec_matrix[user_id]]

        # Perform batch insertion into the database
        self.pl_utils._execute_many_db_command(
            "INSERT INTO rec (user_id, post_id) VALUES (?, ?)",
            insert_values,
            commit=True,
        )

    async def create_post(self, agent_id: int, content: str):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            post_insert_query = (
                "INSERT INTO post (user_id, content, created_at, num_likes, "
                "num_dislikes, num_shares) VALUES (?, ?, ?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                post_insert_query, (user_id, content, current_time, 0, 0, 0),
                commit=True)
            post_id = self.db_cursor.lastrowid

            action_info = {"content": content, "post_id": post_id}
            self.pl_utils._record_trace(user_id, ActionType.CREATE_POST.value,
                                        action_info, current_time)

            # twitter_log.info(f"Trace inserted: user_id={user_id}, "
            #                  f"current_time={current_time}, "
            #                  f"action={ActionType.CREATE_POST.value}, "
            #                  f"info={action_info}")
            return {"success": True, "post_id": post_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def repost(self, agent_id: int, post_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # Ensure the content has not been reposted by this user before
            repost_check_query = (
                "SELECT * FROM 'post' WHERE original_post_id = ? AND "
                "user_id = ?")
            self.pl_utils._execute_db_command(repost_check_query,
                                              (post_id, user_id))
            if self.db_cursor.fetchone():
                # for common and quote post, check if the post has been
                # reposted
                return {
                    "success": False,
                    "error": "Repost record already exists."
                }

            post_type_result = self.pl_utils._get_post_type(post_id)
            post_insert_query = ("INSERT INTO post (user_id, original_post_id"
                                 ", created_at) VALUES (?, ?, ?)")
            # Update num_shares for the found post
            update_shares_query = (
                "UPDATE post SET num_shares = num_shares + 1 WHERE post_id = ?"
            )

            if not post_type_result:
                return {"success": False, "error": "Post not found."}
            elif (post_type_result['type'] == 'common'
                  or post_type_result['type'] == 'quote'):
                self.pl_utils._execute_db_command(
                    post_insert_query, (user_id, post_id, current_time),
                    commit=True)
                self.pl_utils._execute_db_command(update_shares_query,
                                                  (post_id, ),
                                                  commit=True)
            elif post_type_result['type'] == 'repost':
                repost_check_query = (
                    "SELECT * FROM 'post' WHERE original_post_id = ? AND "
                    "user_id = ?")
                self.pl_utils._execute_db_command(
                    repost_check_query,
                    (post_type_result['root_post_id'], user_id))

                if self.db_cursor.fetchone():
                    # for repost post, check if the post has been reposted
                    return {
                        "success": False,
                        "error": "Repost record already exists."
                    }

                self.pl_utils._execute_db_command(
                    post_insert_query,
                    (user_id, post_type_result['root_post_id'], current_time),
                    commit=True)
                self.pl_utils._execute_db_command(
                    update_shares_query, (post_type_result['root_post_id'], ),
                    commit=True)

            new_post_id = self.db_cursor.lastrowid

            action_info = {"reposted_id": post_id, "new_post_id": new_post_id}
            self.pl_utils._record_trace(user_id, ActionType.REPOST.value,
                                        action_info, current_time)

            return {"success": True, "post_id": new_post_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def quote_post(self, agent_id: int, quote_message: tuple):
        post_id, quote_content = quote_message
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # Allow quote a post more than once because the quote content may
            # be different

            post_query = "SELECT content FROM post WHERE post_id = ?"

            post_type_result = self.pl_utils._get_post_type(post_id)
            post_insert_query = (
                "INSERT INTO post (user_id, original_post_id, "
                "content, quote_content, created_at) VALUES (?, ?, ?, ?, ?)")
            update_shares_query = (
                "UPDATE post SET num_shares = num_shares + 1 WHERE post_id = ?"
            )

            if not post_type_result:
                return {"success": False, "error": "Post not found."}
            elif post_type_result['type'] == 'common':
                self.pl_utils._execute_db_command(post_query, (post_id, ))
                post_content = self.db_cursor.fetchone()[0]
                self.pl_utils._execute_db_command(
                    post_insert_query, (user_id, post_id, post_content,
                                        quote_content, current_time),
                    commit=True)
                self.pl_utils._execute_db_command(update_shares_query,
                                                  (post_id, ),
                                                  commit=True)
            elif (post_type_result['type'] == 'repost'
                  or post_type_result['type'] == 'quote'):
                self.pl_utils._execute_db_command(
                    post_query, (post_type_result['root_post_id'], ))
                post_content = self.db_cursor.fetchone()[0]
                self.pl_utils._execute_db_command(
                    post_insert_query,
                    (user_id, post_type_result['root_post_id'], post_content,
                     quote_content, current_time),
                    commit=True)
                self.pl_utils._execute_db_command(
                    update_shares_query, (post_type_result['root_post_id'], ),
                    commit=True)

            new_post_id = self.db_cursor.lastrowid

            action_info = {"quoted_id": post_id, "new_post_id": new_post_id}
            self.pl_utils._record_trace(user_id, ActionType.QUOTE_POST.value,
                                        action_info, current_time)

            return {"success": True, "post_id": new_post_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def like_post(self, agent_id: int, post_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            post_type_result = self.pl_utils._get_post_type(post_id)
            if post_type_result['type'] == 'repost':
                post_id = post_type_result['root_post_id']
            user_id = agent_id
            # Check if a like record already exists
            like_check_query = ("SELECT * FROM 'like' WHERE post_id = ? AND "
                                "user_id = ?")
            self.pl_utils._execute_db_command(like_check_query,
                                              (post_id, user_id))
            if self.db_cursor.fetchone():
                # Like record already exists
                return {
                    "success": False,
                    "error": "Like record already exists."
                }

            # Check if the post to be liked is self-posted
            if self.allow_self_rating is False:
                check_result = self.pl_utils._check_self_post_rating(
                    post_id, user_id)
                if check_result:
                    return check_result

            # Update the number of likes in the post table
            post_update_query = (
                "UPDATE post SET num_likes = num_likes + 1 WHERE post_id = ?")
            self.pl_utils._execute_db_command(post_update_query, (post_id, ),
                                              commit=True)

            # Add a record in the like table
            like_insert_query = (
                "INSERT INTO 'like' (post_id, user_id, created_at) "
                "VALUES (?, ?, ?)")
            self.pl_utils._execute_db_command(like_insert_query,
                                              (post_id, user_id, current_time),
                                              commit=True)
            # Get the ID of the newly inserted like record
            like_id = self.db_cursor.lastrowid

            # Record the action in the trace table
            # if post has been reposted, record the root post id into trace
            action_info = {"post_id": post_id, "like_id": like_id}
            self.pl_utils._record_trace(user_id, ActionType.LIKE_POST.value,
                                        action_info, current_time)
            return {"success": True, "like_id": like_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unlike_post(self, agent_id: int, post_id: int):
        try:
            post_type_result = self.pl_utils._get_post_type(post_id)
            if post_type_result['type'] == 'repost':
                post_id = post_type_result['root_post_id']
            user_id = agent_id

            # Check if a like record already exists
            like_check_query = ("SELECT * FROM 'like' WHERE post_id = ? AND "
                                "user_id = ?")
            self.pl_utils._execute_db_command(like_check_query,
                                              (post_id, user_id))
            result = self.db_cursor.fetchone()

            if not result:
                # No like record exists
                return {
                    "success": False,
                    "error": "Like record does not exist."
                }

            # Get the `like_id`
            like_id, _, _, _ = result

            # Update the number of likes in the post table
            post_update_query = (
                "UPDATE post SET num_likes = num_likes - 1 WHERE post_id = ?")
            self.pl_utils._execute_db_command(
                post_update_query,
                (post_id, ),
                commit=True,
            )

            # Delete the record in the like table
            like_delete_query = "DELETE FROM 'like' WHERE like_id = ?"
            self.pl_utils._execute_db_command(
                like_delete_query,
                (like_id, ),
                commit=True,
            )

            # Record the action in the trace table
            action_info = {"post_id": post_id, "like_id": like_id}
            self.pl_utils._record_trace(user_id, ActionType.UNLIKE_POST.value,
                                        action_info)
            return {"success": True, "like_id": like_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def dislike_post(self, agent_id: int, post_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            post_type_result = self.pl_utils._get_post_type(post_id)
            if post_type_result['type'] == 'repost':
                post_id = post_type_result['root_post_id']
            user_id = agent_id
            # Check if a dislike record already exists
            like_check_query = (
                "SELECT * FROM 'dislike' WHERE post_id = ? AND user_id = ?")
            self.pl_utils._execute_db_command(like_check_query,
                                              (post_id, user_id))
            if self.db_cursor.fetchone():
                # Dislike record already exists
                return {
                    "success": False,
                    "error": "Dislike record already exists."
                }

            # Check if the post to be disliked is self-posted
            if self.allow_self_rating is False:
                check_result = self.pl_utils._check_self_post_rating(
                    post_id, user_id)
                if check_result:
                    return check_result

            # Update the number of dislikes in the post table
            post_update_query = (
                "UPDATE post SET num_dislikes = num_dislikes + 1 WHERE "
                "post_id = ?")
            self.pl_utils._execute_db_command(post_update_query, (post_id, ),
                                              commit=True)

            # Add a record in the dislike table
            dislike_insert_query = (
                "INSERT INTO 'dislike' (post_id, user_id, created_at) "
                "VALUES (?, ?, ?)")
            self.pl_utils._execute_db_command(dislike_insert_query,
                                              (post_id, user_id, current_time),
                                              commit=True)
            # Get the ID of the newly inserted dislike record
            dislike_id = self.db_cursor.lastrowid

            # Record the action in the trace table
            action_info = {"post_id": post_id, "dislike_id": dislike_id}
            self.pl_utils._record_trace(user_id, ActionType.DISLIKE_POST.value,
                                        action_info, current_time)
            return {"success": True, "dislike_id": dislike_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def undo_dislike_post(self, agent_id: int, post_id: int):
        try:
            post_type_result = self.pl_utils._get_post_type(post_id)
            if post_type_result['type'] == 'repost':
                post_id = post_type_result['root_post_id']
            user_id = agent_id

            # Check if a dislike record already exists
            like_check_query = (
                "SELECT * FROM 'dislike' WHERE post_id = ? AND user_id = ?")
            self.pl_utils._execute_db_command(like_check_query,
                                              (post_id, user_id))
            result = self.db_cursor.fetchone()

            if not result:
                # No dislike record exists
                return {
                    "success": False,
                    "error": "Dislike record does not exist."
                }

            # Get the `dislike_id`
            dislike_id, _, _, _ = result

            # Update the number of dislikes in the post table
            post_update_query = (
                "UPDATE post SET num_dislikes = num_dislikes - 1 WHERE "
                "post_id = ?")
            self.pl_utils._execute_db_command(
                post_update_query,
                (post_id, ),
                commit=True,
            )

            # Delete the record in the dislike table
            like_delete_query = "DELETE FROM 'dislike' WHERE dislike_id = ?"
            self.pl_utils._execute_db_command(
                like_delete_query,
                (dislike_id, ),
                commit=True,
            )

            # Record the action in the trace table
            action_info = {"post_id": post_id, "dislike_id": dislike_id}
            self.pl_utils._record_trace(user_id,
                                        ActionType.UNDO_DISLIKE_POST.value,
                                        action_info)
            return {"success": True, "dislike_id": dislike_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_posts(self, agent_id: int, query: str):
        try:
            user_id = agent_id
            # Update the SQL query to search by content, post_id, and user_id
            # simultaneously
            sql_query = (
                "SELECT post_id, user_id, original_post_id, content, "
                "quote_content, created_at, num_likes, num_dislikes, "
                "num_shares FROM post WHERE content LIKE ? OR CAST(post_id AS "
                "TEXT) LIKE ? OR CAST(user_id AS TEXT) LIKE ?")
            # Note: CAST is necessary because post_id and user_id are integers,
            # while the search query is a string type
            self.pl_utils._execute_db_command(
                sql_query,
                ("%" + query + "%", "%" + query + "%", "%" + query + "%"),
                commit=True,
            )
            results = self.db_cursor.fetchall()

            # Record the operation in the trace table
            action_info = {"query": query}
            self.pl_utils._record_trace(user_id, ActionType.SEARCH_POSTS.value,
                                        action_info)

            # If no results are found, return a dictionary indicating failure
            if not results:
                return {
                    "success": False,
                    "message": "No posts found matching the query.",
                }
            results_with_comments = self.pl_utils._add_comments_to_posts(
                results)

            return {"success": True, "posts": results_with_comments}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_user(self, agent_id: int, query: str):
        try:
            user_id = agent_id
            sql_query = (
                "SELECT user_id, user_name, name, bio, created_at, "
                "num_followings, num_followers "
                "FROM user "
                "WHERE user_name LIKE ? OR name LIKE ? OR bio LIKE ? OR "
                "CAST(user_id AS TEXT) LIKE ?")
            # Rewrite to use the execute_db_command method
            self.pl_utils._execute_db_command(
                sql_query,
                (
                    "%" + query + "%",
                    "%" + query + "%",
                    "%" + query + "%",
                    "%" + query + "%",
                ),
                commit=True,
            )
            results = self.db_cursor.fetchall()

            # Record the operation in the trace table
            action_info = {"query": query}
            self.pl_utils._record_trace(user_id, ActionType.SEARCH_USER.value,
                                        action_info)

            # If no results are found, return a dict indicating failure
            if not results:
                return {
                    "success": False,
                    "message": "No users found matching the query.",
                }

            # Convert each tuple in results into a dictionary
            users = [{
                "user_id": user_id,
                "user_name": user_name,
                "name": name,
                "bio": bio,
                "created_at": created_at,
                "num_followings": num_followings,
                "num_followers": num_followers,
            } for user_id, user_name, name, bio, created_at, num_followings,
                     num_followers in results]
            return {"success": True, "users": users}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def follow(self, agent_id: int, followee_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id
            # Check if a follow record already exists
            follow_check_query = ("SELECT * FROM follow WHERE follower_id = ? "
                                  "AND followee_id = ?")
            self.pl_utils._execute_db_command(follow_check_query,
                                              (user_id, followee_id))
            if self.db_cursor.fetchone():
                # Follow record already exists
                return {
                    "success": False,
                    "error": "Follow record already exists."
                }

            # Add a record in the follow table
            follow_insert_query = (
                "INSERT INTO follow (follower_id, followee_id, created_at) "
                "VALUES (?, ?, ?)")
            self.pl_utils._execute_db_command(
                follow_insert_query, (user_id, followee_id, current_time),
                commit=True)
            # Get the ID of the newly inserted follow record
            follow_id = self.db_cursor.lastrowid

            # Update the following field in the user table
            user_update_query1 = (
                "UPDATE user SET num_followings = num_followings + 1 "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(user_update_query1, (user_id, ),
                                              commit=True)

            # Update the follower field in the user table
            user_update_query2 = (
                "UPDATE user SET num_followers = num_followers + 1 "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(user_update_query2,
                                              (followee_id, ),
                                              commit=True)

            # Record the operation in the trace table
            action_info = {"follow_id": follow_id}
            self.pl_utils._record_trace(user_id, ActionType.FOLLOW.value,
                                        action_info, current_time)
            # twitter_log.info(f"Trace inserted: user_id={user_id}, "
            #                  f"current_time={current_time}, "
            #                  f"action={ActionType.FOLLOW.value}, "
            #                  f"info={action_info}")
            return {"success": True, "follow_id": follow_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unfollow(self, agent_id: int, followee_id: int):
        try:
            user_id = agent_id
            # Check for the existence of a follow record and get its ID
            follow_check_query = (
                "SELECT follow_id FROM follow WHERE follower_id = ? AND "
                "followee_id = ?")
            self.pl_utils._execute_db_command(follow_check_query,
                                              (user_id, followee_id))
            follow_record = self.db_cursor.fetchone()
            if not follow_record:
                return {
                    "success": False,
                    "error": "Follow record does not exist."
                }
            # Assuming ID is in the first column of the result
            follow_id = follow_record[0]

            # Delete the record in the follow table
            follow_delete_query = "DELETE FROM follow WHERE follow_id = ?"
            self.pl_utils._execute_db_command(follow_delete_query,
                                              (follow_id, ),
                                              commit=True)

            # Update the following field in the user table
            user_update_query1 = (
                "UPDATE user SET num_followings = num_followings - 1 "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(user_update_query1, (user_id, ),
                                              commit=True)

            # Update the follower field in the user table
            user_update_query2 = (
                "UPDATE user SET num_followers = num_followers - 1 "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(user_update_query2,
                                              (followee_id, ),
                                              commit=True)

            # Record the operation in the trace table
            action_info = {"followee_id": followee_id}
            self.pl_utils._record_trace(user_id, ActionType.UNFOLLOW.value,
                                        action_info)
            return {
                "success": True,
                "follow_id": follow_id,
            }  # Return the ID of the deleted follow record
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def mute(self, agent_id: int, mutee_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id
            # Check if a mute record already exists
            mute_check_query = ("SELECT * FROM mute WHERE muter_id = ? AND "
                                "mutee_id = ?")
            self.pl_utils._execute_db_command(mute_check_query,
                                              (user_id, mutee_id))
            if self.db_cursor.fetchone():
                # Mute record already exists
                return {
                    "success": False,
                    "error": "Mute record already exists."
                }
            # Add a record in the mute table
            mute_insert_query = (
                "INSERT INTO mute (muter_id, mutee_id, created_at) "
                "VALUES (?, ?, ?)")
            self.pl_utils._execute_db_command(
                mute_insert_query, (user_id, mutee_id, current_time),
                commit=True)
            # Get the ID of the newly inserted mute record
            mute_id = self.db_cursor.lastrowid

            # Record the operation in the trace table
            action_info = {"mutee_id": mutee_id}
            self.pl_utils._record_trace(user_id, ActionType.MUTE.value,
                                        action_info, current_time)
            return {"success": True, "mute_id": mute_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unmute(self, agent_id: int, mutee_id: int):
        try:
            user_id = agent_id
            # Check for the specified mute record and get mute_id
            mute_check_query = (
                "SELECT mute_id FROM mute WHERE muter_id = ? AND mutee_id = ?")
            self.pl_utils._execute_db_command(mute_check_query,
                                              (user_id, mutee_id))
            mute_record = self.db_cursor.fetchone()
            if not mute_record:
                # If no mute record exists
                return {"success": False, "error": "No mute record exists."}
            mute_id = mute_record[0]

            # Delete the specified mute record from the mute table
            mute_delete_query = "DELETE FROM mute WHERE mute_id = ?"
            self.pl_utils._execute_db_command(mute_delete_query, (mute_id, ),
                                              commit=True)

            # Record the unmute operation in the trace table
            action_info = {"mutee_id": mutee_id}
            self.pl_utils._record_trace(user_id, ActionType.UNMUTE.value,
                                        action_info)
            return {"success": True, "mute_id": mute_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def trend(self, agent_id: int):
        """
        Get the top K trending posts in the last num_days days.
        """
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id
            # Calculate the start time for the search
            if self.recsys_type == RecsysType.REDDIT:
                start_time = current_time - timedelta(days=self.trend_num_days)
            else:
                start_time = int(current_time) - self.trend_num_days * 24 * 60

            # Build the SQL query
            sql_query = """
                SELECT post_id, user_id, original_post_id, content,
                quote_content, created_at, num_likes, num_dislikes,
                num_shares FROM post
                WHERE created_at >= ?
                ORDER BY num_likes DESC
                LIMIT ?
            """
            # Execute the database query
            self.pl_utils._execute_db_command(sql_query,
                                              (start_time, self.trend_top_k),
                                              commit=True)
            results = self.db_cursor.fetchall()

            # If no results were found, return a dictionary indicating failure
            if not results:
                return {
                    "success": False,
                    "message": "No trending posts in the specified period.",
                }
            results_with_comments = self.pl_utils._add_comments_to_posts(
                results)

            action_info = {"posts": results_with_comments}
            self.pl_utils._record_trace(user_id, ActionType.TREND.value,
                                        action_info, current_time)

            return {"success": True, "posts": results_with_comments}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_comment(self, agent_id: int, comment_message: tuple):
        post_id, content = comment_message
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            post_type_result = self.pl_utils._get_post_type(post_id)
            if post_type_result['type'] == 'repost':
                post_id = post_type_result['root_post_id']
            user_id = agent_id

            # Insert the comment record
            comment_insert_query = (
                "INSERT INTO comment (post_id, user_id, content, created_at) "
                "VALUES (?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                comment_insert_query,
                (post_id, user_id, content, current_time),
                commit=True,
            )
            comment_id = self.db_cursor.lastrowid

            # Prepare information for the trace record
            action_info = {"content": content, "comment_id": comment_id}
            self.pl_utils._record_trace(user_id,
                                        ActionType.CREATE_COMMENT.value,
                                        action_info, current_time)

            return {"success": True, "comment_id": comment_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def like_comment(self, agent_id: int, comment_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # Check if a like record already exists
            like_check_query = (
                "SELECT * FROM comment_like WHERE comment_id = ? AND "
                "user_id = ?")
            self.pl_utils._execute_db_command(like_check_query,
                                              (comment_id, user_id))
            if self.db_cursor.fetchone():
                # Like record already exists
                return {
                    "success": False,
                    "error": "Comment like record already exists.",
                }

            # Check if the comment to be liked was posted by oneself
            if self.allow_self_rating is False:
                check_result = self.pl_utils._check_self_comment_rating(
                    comment_id, user_id)
                if check_result:
                    return check_result

            # Update the number of likes in the comment table
            comment_update_query = (
                "UPDATE comment SET num_likes = num_likes + 1 WHERE "
                "comment_id = ?")
            self.pl_utils._execute_db_command(comment_update_query,
                                              (comment_id, ),
                                              commit=True)

            # Add a record in the comment_like table
            like_insert_query = (
                "INSERT INTO comment_like (comment_id, user_id, created_at) "
                "VALUES (?, ?, ?)")
            self.pl_utils._execute_db_command(
                like_insert_query, (comment_id, user_id, current_time),
                commit=True)
            # Get the ID of the newly inserted like record
            comment_like_id = self.db_cursor.lastrowid

            # Record the operation in the trace table
            action_info = {
                "comment_id": comment_id,
                "comment_like_id": comment_like_id
            }
            self.pl_utils._record_trace(user_id, ActionType.LIKE_COMMENT.value,
                                        action_info, current_time)
            return {"success": True, "comment_like_id": comment_like_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unlike_comment(self, agent_id: int, comment_id: int):
        try:
            user_id = agent_id

            # Check if a like record already exists
            like_check_query = (
                "SELECT * FROM comment_like WHERE comment_id = ? AND "
                "user_id = ?")
            self.pl_utils._execute_db_command(like_check_query,
                                              (comment_id, user_id))
            result = self.db_cursor.fetchone()

            if not result:
                # No like record exists
                return {
                    "success": False,
                    "error": "Comment like record does not exist.",
                }
            # Get the `comment_like_id`
            comment_like_id = result[0]

            # Update the number of likes in the comment table
            comment_update_query = (
                "UPDATE comment SET num_likes = num_likes - 1 WHERE "
                "comment_id = ?")
            self.pl_utils._execute_db_command(
                comment_update_query,
                (comment_id, ),
                commit=True,
            )
            # Delete the record in the comment_like table
            like_delete_query = ("DELETE FROM comment_like WHERE "
                                 "comment_like_id = ?")
            self.pl_utils._execute_db_command(
                like_delete_query,
                (comment_like_id, ),
                commit=True,
            )
            # Record the operation in the trace table
            action_info = {
                "comment_id": comment_id,
                "comment_like_id": comment_like_id
            }
            self.pl_utils._record_trace(user_id,
                                        ActionType.UNLIKE_COMMENT.value,
                                        action_info)
            return {"success": True, "comment_like_id": comment_like_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def dislike_comment(self, agent_id: int, comment_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # Check if a dislike record already exists
            dislike_check_query = (
                "SELECT * FROM comment_dislike WHERE comment_id = ? AND "
                "user_id = ?")
            self.pl_utils._execute_db_command(dislike_check_query,
                                              (comment_id, user_id))
            if self.db_cursor.fetchone():
                # Dislike record already exists
                return {
                    "success": False,
                    "error": "Comment dislike record already exists.",
                }

            # Check if the comment to be disliked was posted by oneself
            if self.allow_self_rating is False:
                check_result = self.pl_utils._check_self_comment_rating(
                    comment_id, user_id)
                if check_result:
                    return check_result

            # Update the number of dislikes in the comment table
            comment_update_query = (
                "UPDATE comment SET num_dislikes = num_dislikes + 1 WHERE "
                "comment_id = ?")
            self.pl_utils._execute_db_command(comment_update_query,
                                              (comment_id, ),
                                              commit=True)

            # Add a record in the comment_dislike table
            dislike_insert_query = (
                "INSERT INTO comment_dislike (comment_id, user_id, "
                "created_at) VALUES (?, ?, ?)")
            self.pl_utils._execute_db_command(
                dislike_insert_query, (comment_id, user_id, current_time),
                commit=True)
            # Get the ID of the newly inserted dislike record
            comment_dislike_id = (self.db_cursor.lastrowid)

            # Record the operation in the trace table
            action_info = {
                "comment_id": comment_id,
                "comment_dislike_id": comment_dislike_id,
            }
            self.pl_utils._record_trace(user_id,
                                        ActionType.DISLIKE_COMMENT.value,
                                        action_info, current_time)
            return {"success": True, "comment_dislike_id": comment_dislike_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def undo_dislike_comment(self, agent_id: int, comment_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # Check if a dislike record already exists
            dislike_check_query = (
                "SELECT comment_dislike_id FROM comment_dislike WHERE "
                "comment_id = ? AND user_id = ?")
            self.pl_utils._execute_db_command(dislike_check_query,
                                              (comment_id, user_id))
            dislike_record = self.db_cursor.fetchone()
            if not dislike_record:
                # No dislike record exists
                return {
                    "success": False,
                    "error": "Comment dislike record does not exist.",
                }
            comment_dislike_id = dislike_record[0]

            # Delete the record from the comment_dislike table
            dislike_delete_query = (
                "DELETE FROM comment_dislike WHERE comment_id = ? AND "
                "user_id = ?")
            self.pl_utils._execute_db_command(dislike_delete_query,
                                              (comment_id, user_id),
                                              commit=True)

            # Update the number of dislikes in the comment table
            comment_update_query = (
                "UPDATE comment SET num_dislikes = num_dislikes - 1 WHERE "
                "comment_id = ?")
            self.pl_utils._execute_db_command(comment_update_query,
                                              (comment_id, ),
                                              commit=True)

            # Record the operation in the trace table
            action_info = {
                "comment_id": comment_id,
                "comment_dislike_id": comment_dislike_id,
            }
            self.pl_utils._record_trace(user_id,
                                        ActionType.UNDO_DISLIKE_COMMENT.value,
                                        action_info, current_time)
            return {"success": True, "comment_dislike_id": comment_dislike_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def do_nothing(self, agent_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            action_info = {}
            self.pl_utils._record_trace(user_id, ActionType.DO_NOTHING.value,
                                        action_info, current_time)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def interview(self, agent_id: int, interview_data):
        """Interview an agent with the given prompt and record the response.

        Args:
            agent_id (int): The ID of the agent being interviewed.
            interview_data: Either a string (prompt only) or dict with prompt
                and response.

        Returns:
            dict: A dictionary with success status.
        """
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # Handle both old format (string prompt) and new format
            # (dict with prompt + response)
            if isinstance(interview_data, str):
                # Old format: just the prompt
                prompt = interview_data
                response = None
                interview_id = f"{current_time}_{user_id}"
                action_info = {"prompt": prompt, "interview_id": interview_id}
            else:
                # New format: dict with prompt and response
                prompt = interview_data.get("prompt", "")
                response = interview_data.get("response", "")
                interview_id = f"{current_time}_{user_id}"
                action_info = {
                    "prompt": prompt,
                    "response": response,
                    "interview_id": interview_id
                }

            # Record the interview in the trace table
            self.pl_utils._record_trace(user_id, ActionType.INTERVIEW.value,
                                        action_info, current_time)

            return {"success": True, "interview_id": interview_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def report_post(self, agent_id: int, report_message: tuple):
        post_id, report_reason = report_message
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id
            post_type_result = self.pl_utils._get_post_type(post_id)

            # Check if a report record already exists
            check_report_query = (
                "SELECT * FROM report WHERE user_id = ? AND post_id = ?")
            self.pl_utils._execute_db_command(check_report_query,
                                              (user_id, post_id))
            if self.db_cursor.fetchone():
                return {
                    "success": False,
                    "error": "Report record already exists."
                }

            if not post_type_result:
                return {"success": False, "error": "Post not found."}

            # Update the number of reports in the post table
            update_reports_query = (
                "UPDATE post SET num_reports = num_reports + 1 WHERE "
                "post_id = ?")
            self.pl_utils._execute_db_command(update_reports_query,
                                              (post_id, ),
                                              commit=True)

            # Add a report in the report table
            report_insert_query = (
                "INSERT INTO report (post_id, user_id, report_reason, "
                "created_at) VALUES (?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                report_insert_query,
                (post_id, user_id, report_reason, current_time),
                commit=True)

            # Get the ID of the newly inserted report record
            report_id = self.db_cursor.lastrowid

            # Record the action in the trace table
            action_info = {"post_id": post_id, "report_id": report_id}
            self.pl_utils._record_trace(user_id, ActionType.REPORT_POST.value,
                                        action_info, current_time)

            return {"success": True, "report_id": report_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_to_group(self, agent_id: int, message: tuple):
        group_id, content = message
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id
            # check if user is a member of the group
            check_query = ("SELECT * FROM group_members WHERE group_id = ? "
                           "AND agent_id = ?")
            self.pl_utils._execute_db_command(check_query, (group_id, user_id))
            if not self.db_cursor.fetchone():
                return {
                    "success": False,
                    "error": "User is not a member of this group.",
                }

            # Insert the message into the group_messages table
            insert_query = """
                INSERT INTO group_messages
                (group_id, sender_id, content, sent_at)
                VALUES (?, ?, ?, ?)
            """
            self.pl_utils._execute_db_command(
                insert_query, (group_id, user_id, content, current_time),
                commit=True)
            message_id = self.db_cursor.lastrowid

            # get the group members
            members_query = ("SELECT agent_id FROM group_members WHERE "
                             "group_id = ? AND agent_id != ?")
            self.pl_utils._execute_db_command(members_query,
                                              (group_id, user_id))
            members = [row[0] for row in self.db_cursor.fetchall()]
            action_info = {
                "group_id": group_id,
                "message_id": message_id,
                "content": content,
            }
            self.pl_utils._record_trace(user_id,
                                        ActionType.SEND_TO_GROUP.value,
                                        action_info, current_time)

            return {"success": True, "message_id": message_id, "to": members}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_group(self, agent_id: int, group_name: str):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # insert the group into the groups table
            insert_query = """
                INSERT INTO chat_group (name, created_at) VALUES (?, ?)
            """
            self.pl_utils._execute_db_command(insert_query,
                                              (group_name, current_time),
                                              commit=True)
            group_id = self.db_cursor.lastrowid

            # insert the user as a member of the group
            join_query = """
                INSERT INTO group_members (group_id, agent_id, joined_at)
                VALUES (?, ?, ?)
            """
            self.pl_utils._execute_db_command(
                join_query, (group_id, user_id, current_time), commit=True)

            action_info = {"group_id": group_id, "group_name": group_name}
            self.pl_utils._record_trace(user_id, ActionType.CREATE_GROUP.value,
                                        action_info, current_time)

            return {"success": True, "group_id": group_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def join_group(self, agent_id: int, group_id: int):
        if self.recsys_type == RecsysType.REDDIT:
            current_time = self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            current_time = self.sandbox_clock.get_time_step()
        try:
            user_id = agent_id

            # check if group exists
            check_group_query = """SELECT * FROM chat_group
                WHERE group_id = ?"""
            self.pl_utils._execute_db_command(check_group_query, (group_id, ))
            if not self.db_cursor.fetchone():
                return {"success": False, "error": "Group does not exist."}

            # check if user is already in the group
            check_member_query = (
                "SELECT * FROM group_members WHERE group_id = ? "
                "AND agent_id = ?")
            self.pl_utils._execute_db_command(check_member_query,
                                              (group_id, user_id))
            if self.db_cursor.fetchone():
                return {
                    "success": False,
                    "error": "User is already in the group."
                }

            # join the group
            join_query = """
                INSERT INTO group_members
                (group_id, agent_id, joined_at) VALUES (?, ?, ?)
            """
            self.pl_utils._execute_db_command(
                join_query, (group_id, user_id, current_time), commit=True)

            action_info = {"group_id": group_id}
            self.pl_utils._record_trace(user_id, ActionType.JOIN_GROUP.value,
                                        action_info, current_time)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def leave_group(self, agent_id: int, group_id: int):
        try:
            user_id = agent_id

            # check if user is a member of the group
            check_query = ("SELECT * FROM group_members "
                           "WHERE group_id = ? AND agent_id = ?")
            self.pl_utils._execute_db_command(check_query, (group_id, user_id))
            if not self.db_cursor.fetchone():
                return {
                    "success": False,
                    "error": "User is not a member of this group."
                }

            # delete the member record
            delete_query = ("DELETE FROM group_members "
                            "WHERE group_id = ? AND agent_id = ?")
            self.pl_utils._execute_db_command(delete_query,
                                              (group_id, user_id),
                                              commit=True)

            action_info = {"group_id": group_id}
            self.pl_utils._record_trace(user_id, ActionType.LEAVE_GROUP.value,
                                        action_info)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def listen_from_group(self, agent_id: int):
        try:
            # get all groups Dict[group_id, group_name]
            query = """ SELECT * FROM chat_group """
            self.pl_utils._execute_db_command(query)
            all_groups = {}
            for row in self.db_cursor.fetchall():
                all_groups[row[0]] = row[1]

            # get all groups that the user is a member of
            in_query = """
                SELECT group_id FROM group_members WHERE agent_id = ?
            """
            self.pl_utils._execute_db_command(in_query, (agent_id, ))
            joined_group_ids = [row[0] for row in self.db_cursor.fetchall()]

            # get all messages from those groups, Dict[group_id, [messages]]
            messages = {}
            for group_id in joined_group_ids:
                select_query = """
                    SELECT message_id, content, sender_id,
                    sent_at FROM group_messages WHERE group_id = ?
                """
                self.pl_utils._execute_db_command(select_query, (group_id, ))
                messages[group_id] = [{
                    "message_id": row[0],
                    "content": row[1],
                    "sender_id": row[2],
                    "sent_at": row[3],
                } for row in self.db_cursor.fetchall()]

            return {
                "success": True,
                "all_groups": all_groups,
                "joined_groups": joined_group_ids,
                "messages": messages
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===================== Economic Action Handlers =====================

    def _get_current_time(self):
        """Helper to get the current simulation time."""
        if self.recsys_type == RecsysType.REDDIT:
            return self.sandbox_clock.time_transfer(
                datetime.now(), self.start_time)
        else:
            return self.sandbox_clock.get_time_step()

    def _lookup_product_by_name(self, product_name: str):
        """Helper to find a product by name. Returns the row or None."""
        query = "SELECT * FROM product WHERE product_name = ?"
        self.pl_utils._execute_db_command(query, (product_name,))
        return self.db_cursor.fetchone()

    def _lookup_product_tiers(self, product_id: int):
        """Helper to get all tiers for a product."""
        query = ("SELECT tier_id, product_id, tier_name, monthly_price, "
                 "annual_price, one_time_price, feature_set, max_users, "
                 "is_default FROM product_tier WHERE product_id = ?")
        self.pl_utils._execute_db_command(query, (product_id,))
        rows = self.db_cursor.fetchall()
        return [{
            "tier_id": r[0], "product_id": r[1], "tier_name": r[2],
            "monthly_price": r[3], "annual_price": r[4],
            "one_time_price": r[5], "feature_set": r[6],
            "max_users": r[7], "is_default": r[8],
        } for r in rows]

    def _product_row_to_dict(self, row):
        """Convert a product table row to a dictionary."""
        return {
            "product_id": row[0], "product_name": row[1],
            "description": row[2], "category": row[3],
            "is_target": row[4], "is_competitor": row[5],
            "base_price": row[6], "has_free_tier": row[7],
            "has_trial": row[8], "trial_days": row[9],
            "quality_score": row[10], "brand_strength": row[11],
            "feature_count": row[12], "sales": row[13],
            "active_subscribers": row[14], "total_revenue": row[15],
            "created_at": row[16],
        }

    async def sign_up_product_with_tiers(
        self, product_name: str, description: str, category: str,
        base_price: float, tiers: list, features: list = None,
        is_target: bool = False, is_competitor: bool = False,
        has_free_tier: bool = False, has_trial: bool = False,
        trial_days: int = 0, quality_score: float = 0.5,
        brand_strength: float = 0.5,
    ):
        """Register a product with full pricing tier information.

        Args:
            product_name: Name of the product.
            description: Product description.
            category: Product category.
            base_price: Base price of the product.
            tiers: List of dicts with tier info, each containing:
                tier_name, monthly_price, annual_price, feature_set,
                max_users, is_default.
            features: Optional list of dicts with feature info, each
                containing: feature_key, feature_name, description,
                importance_weight.
            is_target: Whether this is the target product.
            is_competitor: Whether this is a competitor product.
            has_free_tier: Whether the product has a free tier.
            has_trial: Whether the product offers a trial.
            trial_days: Number of trial days.
            quality_score: Quality score (0-1).
            brand_strength: Brand strength (0-1).

        Returns:
            dict: Success status and product_id.
        """
        current_time = self._get_current_time()
        try:
            feature_count = len(features) if features else 0
            product_insert = (
                "INSERT INTO product (product_name, description, category, "
                "is_target, is_competitor, base_price, has_free_tier, "
                "has_trial, trial_days, quality_score, brand_strength, "
                "feature_count, sales, active_subscribers, total_revenue, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "0, 0, 0.0, ?)")
            self.pl_utils._execute_db_command(
                product_insert,
                (product_name, description, category, int(is_target),
                 int(is_competitor), base_price, int(has_free_tier),
                 int(has_trial), trial_days, quality_score, brand_strength,
                 feature_count, current_time),
                commit=True)
            product_id = self.db_cursor.lastrowid

            # Insert tiers
            for tier in tiers:
                tier_insert = (
                    "INSERT INTO product_tier (product_id, tier_name, "
                    "monthly_price, annual_price, one_time_price, "
                    "feature_set, max_users, is_default) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
                self.pl_utils._execute_db_command(
                    tier_insert,
                    (product_id, tier.get("tier_name", "default"),
                     tier.get("monthly_price", 0.0),
                     tier.get("annual_price", 0.0),
                     tier.get("one_time_price"),
                     tier.get("feature_set", ""),
                     tier.get("max_users", 1),
                     int(tier.get("is_default", False))),
                    commit=True)

            # Insert features if provided
            if features:
                for feat in features:
                    feat_insert = (
                        "INSERT INTO product_feature (product_id, "
                        "feature_key, feature_name, description, "
                        "importance_weight) VALUES (?, ?, ?, ?, ?)")
                    self.pl_utils._execute_db_command(
                        feat_insert,
                        (product_id, feat.get("feature_key", ""),
                         feat.get("feature_name", ""),
                         feat.get("description", ""),
                         feat.get("importance_weight", 0.5)),
                        commit=True)

            return {"success": True, "product_id": product_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browse_products(self, agent_id: int):
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            query = (
                "SELECT * FROM product")
            self.pl_utils._execute_db_command(query)
            products = self.db_cursor.fetchall()

            if not products:
                return {"success": False, "message": "No products available."}

            catalog = []
            for row in products:
                prod = self._product_row_to_dict(row)
                prod["tiers"] = self._lookup_product_tiers(prod["product_id"])
                # Get average rating
                rating_query = (
                    "SELECT AVG(rating), COUNT(*) FROM product_review "
                    "WHERE product_id = ?")
                self.pl_utils._execute_db_command(
                    rating_query, (prod["product_id"],))
                rating_row = self.db_cursor.fetchone()
                prod["avg_rating"] = rating_row[0] if rating_row[0] else 0.0
                prod["num_reviews"] = rating_row[1] if rating_row[1] else 0
                catalog.append(prod)

            action_info = {"num_products": len(catalog)}
            self.pl_utils._record_trace(
                user_id, ActionType.BROWSE_PRODUCTS.value,
                action_info, current_time)

            return {"success": True, "products": catalog}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def compare_products(self, agent_id: int, message: tuple):
        product_a_name, product_b_name = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id

            def _get_product_info(pname):
                row = self._lookup_product_by_name(pname)
                if not row:
                    return None
                prod = self._product_row_to_dict(row)
                prod["tiers"] = self._lookup_product_tiers(prod["product_id"])
                # Reviews
                rev_query = (
                    "SELECT AVG(rating), COUNT(*) FROM product_review "
                    "WHERE product_id = ?")
                self.pl_utils._execute_db_command(
                    rev_query, (prod["product_id"],))
                rev_row = self.db_cursor.fetchone()
                prod["avg_rating"] = rev_row[0] if rev_row[0] else 0.0
                prod["num_reviews"] = rev_row[1] if rev_row[1] else 0
                return prod

            info_a = _get_product_info(product_a_name)
            info_b = _get_product_info(product_b_name)

            if not info_a:
                return {
                    "success": False,
                    "error": f"Product '{product_a_name}' not found."}
            if not info_b:
                return {
                    "success": False,
                    "error": f"Product '{product_b_name}' not found."}

            action_info = {
                "product_a": product_a_name, "product_b": product_b_name}
            self.pl_utils._record_trace(
                user_id, ActionType.COMPARE_PRODUCTS.value,
                action_info, current_time)

            return {
                "success": True,
                "product_a": info_a,
                "product_b": info_b,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def view_product_details(self, agent_id: int, product_name: str):
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}

            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]
            prod["tiers"] = self._lookup_product_tiers(product_id)

            # Features
            feat_query = (
                "SELECT feature_id, feature_key, feature_name, description, "
                "importance_weight FROM product_feature WHERE product_id = ?")
            self.pl_utils._execute_db_command(feat_query, (product_id,))
            prod["features"] = [{
                "feature_id": r[0], "feature_key": r[1],
                "feature_name": r[2], "description": r[3],
                "importance_weight": r[4],
            } for r in self.db_cursor.fetchall()]

            # Reviews
            rev_query = (
                "SELECT review_id, user_id, rating, content, "
                "sentiment_score, created_at FROM product_review "
                "WHERE product_id = ? ORDER BY created_at DESC LIMIT 10")
            self.pl_utils._execute_db_command(rev_query, (product_id,))
            prod["reviews"] = [{
                "review_id": r[0], "user_id": r[1], "rating": r[2],
                "content": r[3], "sentiment_score": r[4],
                "created_at": r[5],
            } for r in self.db_cursor.fetchall()]

            # Average rating
            avg_query = (
                "SELECT AVG(rating), COUNT(*) FROM product_review "
                "WHERE product_id = ?")
            self.pl_utils._execute_db_command(avg_query, (product_id,))
            avg_row = self.db_cursor.fetchone()
            prod["avg_rating"] = avg_row[0] if avg_row[0] else 0.0
            prod["num_reviews"] = avg_row[1] if avg_row[1] else 0

            action_info = {"product_name": product_name}
            self.pl_utils._record_trace(
                user_id, ActionType.VIEW_PRODUCT_DETAILS.value,
                action_info, current_time)

            return {"success": True, "product": prod}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def start_trial(self, agent_id: int, product_name: str):
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            if not prod["has_trial"]:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' does not offer a "
                             f"trial."}

            # Check if user already has an active trial
            trial_check = (
                "SELECT * FROM trial WHERE user_id = ? AND product_id = ? "
                "AND converted = 0 AND abandon_reason IS NULL")
            self.pl_utils._execute_db_command(
                trial_check, (user_id, product_id))
            if self.db_cursor.fetchone():
                return {
                    "success": False,
                    "error": "You already have an active trial for this "
                             "product."}

            # Calculate trial end date
            trial_days = prod["trial_days"] if prod["trial_days"] else 14
            if self.recsys_type == RecsysType.REDDIT:
                ends_at = current_time + timedelta(days=trial_days)
            else:
                ends_at = int(current_time) + trial_days * 24 * 60

            # Get default tier
            tier_query = (
                "SELECT tier_id FROM product_tier WHERE product_id = ? "
                "AND is_default = 1")
            self.pl_utils._execute_db_command(tier_query, (product_id,))
            tier_row = self.db_cursor.fetchone()
            tier_id = tier_row[0] if tier_row else None

            # If no default tier, get the first one
            if tier_id is None:
                tier_query2 = (
                    "SELECT tier_id FROM product_tier WHERE product_id = ? "
                    "LIMIT 1")
                self.pl_utils._execute_db_command(tier_query2, (product_id,))
                tier_row2 = self.db_cursor.fetchone()
                tier_id = tier_row2[0] if tier_row2 else None

            # Insert trial record
            trial_insert = (
                "INSERT INTO trial (user_id, product_id, tier_id, "
                "started_at, ends_at) VALUES (?, ?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                trial_insert,
                (user_id, product_id, tier_id, current_time, ends_at),
                commit=True)
            trial_id = self.db_cursor.lastrowid

            # Create subscription with status='trial'
            sub_insert = (
                "INSERT INTO subscription (user_id, product_id, tier_id, "
                "status, started_at, trial_ends_at, "
                "current_period_start, current_period_end) "
                "VALUES (?, ?, ?, 'trial', ?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                sub_insert,
                (user_id, product_id, tier_id, current_time, ends_at,
                 current_time, ends_at),
                commit=True)

            # Create trial_start transaction
            txn_insert = (
                "INSERT INTO 'transaction' (user_id, product_id, tier_id, "
                "type, amount, created_at) VALUES (?, ?, ?, 'trial_start', "
                "0.0, ?)")
            self.pl_utils._execute_db_command(
                txn_insert,
                (user_id, product_id, tier_id, current_time),
                commit=True)

            # Record funnel event
            funnel_insert = (
                "INSERT INTO funnel_event (user_id, product_id, stage, "
                "previous_stage, trigger_type, created_at) "
                "VALUES (?, ?, 'trialing', 'considering', 'start_trial', ?)")
            self.pl_utils._execute_db_command(
                funnel_insert, (user_id, product_id, current_time),
                commit=True)

            action_info = {
                "product_name": product_name, "trial_id": trial_id,
                "ends_at": str(ends_at)}
            self.pl_utils._record_trace(
                user_id, ActionType.START_TRIAL.value,
                action_info, current_time)

            return {
                "success": True, "trial_id": trial_id,
                "ends_at": str(ends_at)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def end_trial(self, agent_id: int, message: tuple):
        product_name, reason = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Find active trial
            trial_query = (
                "SELECT trial_id FROM trial WHERE user_id = ? AND "
                "product_id = ? AND converted = 0 AND "
                "abandon_reason IS NULL")
            self.pl_utils._execute_db_command(
                trial_query, (user_id, product_id))
            trial_row = self.db_cursor.fetchone()
            if not trial_row:
                return {
                    "success": False,
                    "error": "No active trial found for this product."}
            trial_id = trial_row[0]

            # Update trial with abandon reason
            trial_update = (
                "UPDATE trial SET abandon_reason = ? WHERE trial_id = ?")
            self.pl_utils._execute_db_command(
                trial_update, (reason, trial_id), commit=True)

            # Update subscription status
            sub_update = (
                "UPDATE subscription SET status = 'cancelled', "
                "cancelled_at = ?, cancel_reason = ? "
                "WHERE user_id = ? AND product_id = ? AND status = 'trial'")
            self.pl_utils._execute_db_command(
                sub_update,
                (current_time, reason, user_id, product_id),
                commit=True)

            # Record funnel event
            funnel_insert = (
                "INSERT INTO funnel_event (user_id, product_id, stage, "
                "previous_stage, trigger_type, created_at, metadata) "
                "VALUES (?, ?, 'churned', 'trialing', 'end_trial', ?, ?)")
            self.pl_utils._execute_db_command(
                funnel_insert,
                (user_id, product_id, current_time, reason),
                commit=True)

            action_info = {
                "product_name": product_name, "trial_id": trial_id,
                "reason": reason}
            self.pl_utils._record_trace(
                user_id, ActionType.END_TRIAL.value,
                action_info, current_time)

            return {"success": True, "trial_id": trial_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def subscribe(self, agent_id: int, message: tuple):
        product_name, tier_name = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Look up tier
            tier_query = (
                "SELECT tier_id, monthly_price FROM product_tier "
                "WHERE product_id = ? AND tier_name = ?")
            self.pl_utils._execute_db_command(
                tier_query, (product_id, tier_name))
            tier_row = self.db_cursor.fetchone()
            if not tier_row:
                return {
                    "success": False,
                    "error": f"Tier '{tier_name}' not found for "
                             f"'{product_name}'."}
            tier_id = tier_row[0]
            monthly_price = tier_row[1]

            # Check wallet balance
            wallet_query = (
                "SELECT wallet_id, balance, monthly_spending_limit, "
                "current_month_spent FROM wallet WHERE user_id = ?")
            self.pl_utils._execute_db_command(wallet_query, (user_id,))
            wallet_row = self.db_cursor.fetchone()
            if not wallet_row:
                return {
                    "success": False,
                    "error": "No wallet found. Please set up a budget first."}
            wallet_id, balance, monthly_limit, month_spent = wallet_row

            if balance < monthly_price:
                return {
                    "success": False,
                    "error": f"Insufficient balance. Need ${monthly_price}, "
                             f"have ${balance}."}
            if monthly_limit > 0 and (month_spent + monthly_price) > \
                    monthly_limit:
                return {
                    "success": False,
                    "error": f"Would exceed monthly spending limit of "
                             f"${monthly_limit}."}

            # Check for existing active subscription
            sub_check = (
                "SELECT subscription_id, status FROM subscription "
                "WHERE user_id = ? AND product_id = ? "
                "AND status IN ('active', 'trial')")
            self.pl_utils._execute_db_command(
                sub_check, (user_id, product_id))
            existing = self.db_cursor.fetchone()

            if existing and existing[1] == 'active':
                return {
                    "success": False,
                    "error": "You already have an active subscription to "
                             "this product."}

            # If converting from trial, update trial record
            if existing and existing[1] == 'trial':
                trial_update = (
                    "UPDATE trial SET converted = 1, converted_at = ? "
                    "WHERE user_id = ? AND product_id = ? AND converted = 0")
                self.pl_utils._execute_db_command(
                    trial_update, (current_time, user_id, product_id),
                    commit=True)
                # Update existing subscription
                sub_update = (
                    "UPDATE subscription SET status = 'active', "
                    "tier_id = ?, current_period_start = ? "
                    "WHERE subscription_id = ?")
                self.pl_utils._execute_db_command(
                    sub_update,
                    (tier_id, current_time, existing[0]),
                    commit=True)
                subscription_id = existing[0]
            else:
                # Create new subscription
                if self.recsys_type == RecsysType.REDDIT:
                    period_end = current_time + timedelta(days=30)
                else:
                    period_end = int(current_time) + 30 * 24 * 60
                sub_insert = (
                    "INSERT INTO subscription (user_id, product_id, "
                    "tier_id, status, started_at, "
                    "current_period_start, current_period_end) "
                    "VALUES (?, ?, ?, 'active', ?, ?, ?)")
                self.pl_utils._execute_db_command(
                    sub_insert,
                    (user_id, product_id, tier_id, current_time,
                     current_time, period_end),
                    commit=True)
                subscription_id = self.db_cursor.lastrowid

            # Debit wallet
            wallet_update = (
                "UPDATE wallet SET balance = balance - ?, "
                "total_spent = total_spent + ?, "
                "current_month_spent = current_month_spent + ? "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(
                wallet_update,
                (monthly_price, monthly_price, monthly_price, user_id),
                commit=True)

            # Create transaction
            txn_insert = (
                "INSERT INTO 'transaction' (user_id, product_id, tier_id, "
                "type, amount, created_at) "
                "VALUES (?, ?, ?, 'subscription_payment', ?, ?)")
            self.pl_utils._execute_db_command(
                txn_insert,
                (user_id, product_id, tier_id, monthly_price, current_time),
                commit=True)

            # Update product active_subscribers and revenue
            prod_update = (
                "UPDATE product SET active_subscribers = "
                "active_subscribers + 1, total_revenue = total_revenue + ? "
                "WHERE product_id = ?")
            self.pl_utils._execute_db_command(
                prod_update, (monthly_price, product_id), commit=True)

            # Record funnel event
            prev_stage = 'trialing' if (
                existing and existing[1] == 'trial') else 'considering'
            funnel_insert = (
                "INSERT INTO funnel_event (user_id, product_id, stage, "
                "previous_stage, trigger_type, created_at) "
                "VALUES (?, ?, 'subscribed', ?, 'subscribe', ?)")
            self.pl_utils._execute_db_command(
                funnel_insert,
                (user_id, product_id, prev_stage, current_time),
                commit=True)

            action_info = {
                "product_name": product_name, "tier_name": tier_name,
                "subscription_id": subscription_id,
                "amount_charged": monthly_price}
            self.pl_utils._record_trace(
                user_id, ActionType.SUBSCRIBE.value,
                action_info, current_time)

            return {
                "success": True,
                "subscription_id": subscription_id,
                "amount_charged": monthly_price}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def upgrade_tier(self, agent_id: int, message: tuple):
        product_name, new_tier = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Find active subscription
            sub_query = (
                "SELECT subscription_id, tier_id FROM subscription "
                "WHERE user_id = ? AND product_id = ? AND status = 'active'")
            self.pl_utils._execute_db_command(
                sub_query, (user_id, product_id))
            sub_row = self.db_cursor.fetchone()
            if not sub_row:
                return {
                    "success": False,
                    "error": "No active subscription found for this "
                             "product."}
            subscription_id, old_tier_id = sub_row

            # Get old tier price
            old_price_query = (
                "SELECT monthly_price FROM product_tier "
                "WHERE tier_id = ?")
            self.pl_utils._execute_db_command(
                old_price_query, (old_tier_id,))
            old_price_row = self.db_cursor.fetchone()
            old_price = old_price_row[0] if old_price_row else 0.0

            # Look up new tier
            tier_query = (
                "SELECT tier_id, monthly_price FROM product_tier "
                "WHERE product_id = ? AND tier_name = ?")
            self.pl_utils._execute_db_command(
                tier_query, (product_id, new_tier))
            tier_row = self.db_cursor.fetchone()
            if not tier_row:
                return {
                    "success": False,
                    "error": f"Tier '{new_tier}' not found for "
                             f"'{product_name}'."}
            new_tier_id, new_price = tier_row

            # Calculate price difference (upgrade cost)
            price_diff = new_price - old_price
            if price_diff <= 0:
                return {
                    "success": False,
                    "error": "New tier is not more expensive. Use "
                             "downgrade_tier instead."}

            # Check wallet
            wallet_query = (
                "SELECT balance FROM wallet WHERE user_id = ?")
            self.pl_utils._execute_db_command(wallet_query, (user_id,))
            wallet_row = self.db_cursor.fetchone()
            if not wallet_row or wallet_row[0] < price_diff:
                return {
                    "success": False,
                    "error": f"Insufficient balance for upgrade. "
                             f"Need ${price_diff}."}

            # Update subscription tier
            sub_update = (
                "UPDATE subscription SET tier_id = ? "
                "WHERE subscription_id = ?")
            self.pl_utils._execute_db_command(
                sub_update, (new_tier_id, subscription_id), commit=True)

            # Debit wallet for the difference
            wallet_update = (
                "UPDATE wallet SET balance = balance - ?, "
                "total_spent = total_spent + ?, "
                "current_month_spent = current_month_spent + ? "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(
                wallet_update,
                (price_diff, price_diff, price_diff, user_id),
                commit=True)

            # Create upgrade transaction
            txn_insert = (
                "INSERT INTO 'transaction' (user_id, product_id, tier_id, "
                "type, amount, created_at) "
                "VALUES (?, ?, ?, 'upgrade', ?, ?)")
            self.pl_utils._execute_db_command(
                txn_insert,
                (user_id, product_id, new_tier_id, price_diff, current_time),
                commit=True)

            # Update product revenue
            prod_update = (
                "UPDATE product SET total_revenue = total_revenue + ? "
                "WHERE product_id = ?")
            self.pl_utils._execute_db_command(
                prod_update, (price_diff, product_id), commit=True)

            action_info = {
                "product_name": product_name, "new_tier": new_tier,
                "subscription_id": subscription_id,
                "price_diff": price_diff}
            self.pl_utils._record_trace(
                user_id, ActionType.UPGRADE_TIER.value,
                action_info, current_time)

            return {
                "success": True,
                "subscription_id": subscription_id,
                "new_tier": new_tier,
                "amount_charged": price_diff}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def downgrade_tier(self, agent_id: int, message: tuple):
        product_name, new_tier = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Find active subscription
            sub_query = (
                "SELECT subscription_id, tier_id FROM subscription "
                "WHERE user_id = ? AND product_id = ? AND status = 'active'")
            self.pl_utils._execute_db_command(
                sub_query, (user_id, product_id))
            sub_row = self.db_cursor.fetchone()
            if not sub_row:
                return {
                    "success": False,
                    "error": "No active subscription found for this "
                             "product."}
            subscription_id, old_tier_id = sub_row

            # Get old tier price
            old_price_query = (
                "SELECT monthly_price FROM product_tier "
                "WHERE tier_id = ?")
            self.pl_utils._execute_db_command(
                old_price_query, (old_tier_id,))
            old_price_row = self.db_cursor.fetchone()
            old_price = old_price_row[0] if old_price_row else 0.0

            # Look up new tier
            tier_query = (
                "SELECT tier_id, monthly_price FROM product_tier "
                "WHERE product_id = ? AND tier_name = ?")
            self.pl_utils._execute_db_command(
                tier_query, (product_id, new_tier))
            tier_row = self.db_cursor.fetchone()
            if not tier_row:
                return {
                    "success": False,
                    "error": f"Tier '{new_tier}' not found for "
                             f"'{product_name}'."}
            new_tier_id, new_price = tier_row

            # Calculate credit (downgrade savings)
            price_diff = old_price - new_price
            if price_diff <= 0:
                return {
                    "success": False,
                    "error": "New tier is not cheaper. Use upgrade_tier "
                             "instead."}

            # Update subscription tier
            sub_update = (
                "UPDATE subscription SET tier_id = ? "
                "WHERE subscription_id = ?")
            self.pl_utils._execute_db_command(
                sub_update, (new_tier_id, subscription_id), commit=True)

            # Credit wallet for the difference
            wallet_update = (
                "UPDATE wallet SET balance = balance + ?, "
                "current_month_spent = current_month_spent - ? "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(
                wallet_update, (price_diff, price_diff, user_id),
                commit=True)

            # Create downgrade transaction
            txn_insert = (
                "INSERT INTO 'transaction' (user_id, product_id, tier_id, "
                "type, amount, created_at) "
                "VALUES (?, ?, ?, 'downgrade', ?, ?)")
            self.pl_utils._execute_db_command(
                txn_insert,
                (user_id, product_id, new_tier_id, -price_diff, current_time),
                commit=True)

            action_info = {
                "product_name": product_name, "new_tier": new_tier,
                "subscription_id": subscription_id,
                "amount_credited": price_diff}
            self.pl_utils._record_trace(
                user_id, ActionType.DOWNGRADE_TIER.value,
                action_info, current_time)

            return {
                "success": True,
                "subscription_id": subscription_id,
                "new_tier": new_tier,
                "amount_credited": price_diff}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def cancel_subscription(self, agent_id: int, message: tuple):
        product_name, reason = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Find active subscription
            sub_query = (
                "SELECT subscription_id FROM subscription "
                "WHERE user_id = ? AND product_id = ? "
                "AND status IN ('active', 'trial')")
            self.pl_utils._execute_db_command(
                sub_query, (user_id, product_id))
            sub_row = self.db_cursor.fetchone()
            if not sub_row:
                return {
                    "success": False,
                    "error": "No active subscription found for this "
                             "product."}
            subscription_id = sub_row[0]

            # Update subscription status
            sub_update = (
                "UPDATE subscription SET status = 'cancelled', "
                "cancelled_at = ?, cancel_reason = ? "
                "WHERE subscription_id = ?")
            self.pl_utils._execute_db_command(
                sub_update,
                (current_time, reason, subscription_id),
                commit=True)

            # Update product active_subscribers
            prod_update = (
                "UPDATE product SET active_subscribers = "
                "active_subscribers - 1 "
                "WHERE product_id = ? AND active_subscribers > 0")
            self.pl_utils._execute_db_command(
                prod_update, (product_id,), commit=True)

            # Record funnel event
            funnel_insert = (
                "INSERT INTO funnel_event (user_id, product_id, stage, "
                "previous_stage, trigger_type, created_at, metadata) "
                "VALUES (?, ?, 'churned', 'subscribed', "
                "'cancel_subscription', ?, ?)")
            self.pl_utils._execute_db_command(
                funnel_insert,
                (user_id, product_id, current_time, reason),
                commit=True)

            action_info = {
                "product_name": product_name,
                "subscription_id": subscription_id,
                "cancel_reason": reason}
            self.pl_utils._record_trace(
                user_id, ActionType.CANCEL_SUBSCRIPTION.value,
                action_info, current_time)

            return {
                "success": True, "subscription_id": subscription_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def renew_subscription(self, agent_id: int, product_name: str):
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Find active subscription
            sub_query = (
                "SELECT subscription_id, tier_id, months_active, "
                "total_paid FROM subscription "
                "WHERE user_id = ? AND product_id = ? AND status = 'active'")
            self.pl_utils._execute_db_command(
                sub_query, (user_id, product_id))
            sub_row = self.db_cursor.fetchone()
            if not sub_row:
                return {
                    "success": False,
                    "error": "No active subscription found for this "
                             "product."}
            subscription_id, tier_id, months_active, total_paid = sub_row

            # Get tier price
            price_query = (
                "SELECT monthly_price FROM product_tier "
                "WHERE tier_id = ?")
            self.pl_utils._execute_db_command(price_query, (tier_id,))
            price_row = self.db_cursor.fetchone()
            monthly_price = price_row[0] if price_row else 0.0

            # Check wallet
            wallet_query = (
                "SELECT balance, monthly_spending_limit, "
                "current_month_spent FROM wallet WHERE user_id = ?")
            self.pl_utils._execute_db_command(wallet_query, (user_id,))
            wallet_row = self.db_cursor.fetchone()
            if not wallet_row:
                return {
                    "success": False,
                    "error": "No wallet found."}
            balance, monthly_limit, month_spent = wallet_row

            if balance < monthly_price:
                return {
                    "success": False,
                    "error": f"Insufficient balance. Need ${monthly_price}, "
                             f"have ${balance}."}

            # Extend subscription period
            if self.recsys_type == RecsysType.REDDIT:
                new_period_end = current_time + timedelta(days=30)
            else:
                new_period_end = int(current_time) + 30 * 24 * 60

            sub_update = (
                "UPDATE subscription SET current_period_start = ?, "
                "current_period_end = ?, months_active = ?, "
                "total_paid = ? WHERE subscription_id = ?")
            self.pl_utils._execute_db_command(
                sub_update,
                (current_time, new_period_end, months_active + 1,
                 total_paid + monthly_price, subscription_id),
                commit=True)

            # Debit wallet
            wallet_update = (
                "UPDATE wallet SET balance = balance - ?, "
                "total_spent = total_spent + ?, "
                "current_month_spent = current_month_spent + ? "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(
                wallet_update,
                (monthly_price, monthly_price, monthly_price, user_id),
                commit=True)

            # Create transaction
            txn_insert = (
                "INSERT INTO 'transaction' (user_id, product_id, tier_id, "
                "type, amount, created_at) "
                "VALUES (?, ?, ?, 'subscription_payment', ?, ?)")
            self.pl_utils._execute_db_command(
                txn_insert,
                (user_id, product_id, tier_id, monthly_price, current_time),
                commit=True)

            # Update product revenue
            prod_update = (
                "UPDATE product SET total_revenue = total_revenue + ? "
                "WHERE product_id = ?")
            self.pl_utils._execute_db_command(
                prod_update, (monthly_price, product_id), commit=True)

            action_info = {
                "product_name": product_name,
                "subscription_id": subscription_id,
                "amount_charged": monthly_price,
                "renewed_until": str(new_period_end)}
            self.pl_utils._record_trace(
                user_id, ActionType.RENEW_SUBSCRIPTION.value,
                action_info, current_time)

            return {
                "success": True,
                "subscription_id": subscription_id,
                "amount_charged": monthly_price,
                "renewed_until": str(new_period_end)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def write_review(self, agent_id: int, message: tuple):
        product_name, rating, review_text = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Validate rating
            if not (1 <= rating <= 5):
                return {
                    "success": False,
                    "error": "Rating must be between 1 and 5."}

            # Insert review
            review_insert = (
                "INSERT INTO product_review (user_id, product_id, rating, "
                "content, created_at) VALUES (?, ?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                review_insert,
                (user_id, product_id, rating, review_text, current_time),
                commit=True)
            review_id = self.db_cursor.lastrowid

            # Also create a post about the review
            review_post = (
                f"Review of {product_name} ({rating}/5 stars): "
                f"{review_text}")
            post_insert = (
                "INSERT INTO post (user_id, content, created_at, "
                "num_likes, num_dislikes, num_shares) "
                "VALUES (?, ?, ?, 0, 0, 0)")
            self.pl_utils._execute_db_command(
                post_insert, (user_id, review_post, current_time),
                commit=True)
            post_id = self.db_cursor.lastrowid

            action_info = {
                "product_name": product_name, "rating": rating,
                "review_id": review_id, "post_id": post_id}
            self.pl_utils._record_trace(
                user_id, ActionType.WRITE_REVIEW.value,
                action_info, current_time)

            return {
                "success": True,
                "review_id": review_id, "post_id": post_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def refer_friend(self, agent_id: int, message: tuple):
        product_name, recommendation_text = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Insert referral record (referred_user_id is NULL since it's
            # a broadcast recommendation)
            referral_insert = (
                "INSERT INTO referral (referrer_user_id, product_id, "
                "status, created_at) VALUES (?, ?, 'pending', ?)")
            self.pl_utils._execute_db_command(
                referral_insert,
                (user_id, product_id, current_time),
                commit=True)
            referral_id = self.db_cursor.lastrowid

            # Create a recommendation post
            rec_post = (
                f"I recommend {product_name}! {recommendation_text}")
            post_insert = (
                "INSERT INTO post (user_id, content, created_at, "
                "num_likes, num_dislikes, num_shares) "
                "VALUES (?, ?, ?, 0, 0, 0)")
            self.pl_utils._execute_db_command(
                post_insert, (user_id, rec_post, current_time),
                commit=True)
            post_id = self.db_cursor.lastrowid

            # Record funnel event as advocate
            funnel_insert = (
                "INSERT INTO funnel_event (user_id, product_id, stage, "
                "previous_stage, trigger_type, created_at) "
                "VALUES (?, ?, 'advocate', 'subscribed', 'refer_friend', ?)")
            self.pl_utils._execute_db_command(
                funnel_insert, (user_id, product_id, current_time),
                commit=True)

            action_info = {
                "product_name": product_name, "referral_id": referral_id,
                "post_id": post_id}
            self.pl_utils._record_trace(
                user_id, ActionType.REFER_FRIEND.value,
                action_info, current_time)

            return {
                "success": True,
                "referral_id": referral_id, "post_id": post_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def request_refund(self, agent_id: int, message: tuple):
        product_name, reason = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Find the most recent subscription payment transaction
            txn_query = (
                "SELECT transaction_id, amount, tier_id FROM 'transaction' "
                "WHERE user_id = ? AND product_id = ? "
                "AND type = 'subscription_payment' "
                "ORDER BY created_at DESC LIMIT 1")
            self.pl_utils._execute_db_command(
                txn_query, (user_id, product_id))
            txn_row = self.db_cursor.fetchone()
            if not txn_row:
                return {
                    "success": False,
                    "error": "No payment found to refund."}
            _, refund_amount, tier_id = txn_row

            # Create refund transaction (negative amount)
            refund_insert = (
                "INSERT INTO 'transaction' (user_id, product_id, tier_id, "
                "type, amount, created_at) "
                "VALUES (?, ?, ?, 'refund', ?, ?)")
            self.pl_utils._execute_db_command(
                refund_insert,
                (user_id, product_id, tier_id, -refund_amount, current_time),
                commit=True)
            refund_txn_id = self.db_cursor.lastrowid

            # Credit wallet
            wallet_update = (
                "UPDATE wallet SET balance = balance + ?, "
                "total_spent = total_spent - ?, "
                "current_month_spent = current_month_spent - ? "
                "WHERE user_id = ?")
            self.pl_utils._execute_db_command(
                wallet_update,
                (refund_amount, refund_amount, refund_amount, user_id),
                commit=True)

            # Update product revenue
            prod_update = (
                "UPDATE product SET total_revenue = total_revenue - ? "
                "WHERE product_id = ?")
            self.pl_utils._execute_db_command(
                prod_update, (refund_amount, product_id), commit=True)

            action_info = {
                "product_name": product_name, "reason": reason,
                "refund_amount": refund_amount,
                "transaction_id": refund_txn_id}
            self.pl_utils._record_trace(
                user_id, ActionType.REQUEST_REFUND.value,
                action_info, current_time)

            return {
                "success": True,
                "refund_amount": refund_amount,
                "transaction_id": refund_txn_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def set_budget(self, agent_id: int, new_monthly_limit: float):
        current_time = self._get_current_time()
        try:
            user_id = agent_id

            # Check if wallet exists
            wallet_query = (
                "SELECT wallet_id FROM wallet WHERE user_id = ?")
            self.pl_utils._execute_db_command(wallet_query, (user_id,))
            wallet_row = self.db_cursor.fetchone()

            if wallet_row:
                # Update existing wallet
                wallet_update = (
                    "UPDATE wallet SET monthly_spending_limit = ? "
                    "WHERE user_id = ?")
                self.pl_utils._execute_db_command(
                    wallet_update, (new_monthly_limit, user_id),
                    commit=True)
            else:
                # Create new wallet with default balance
                wallet_insert = (
                    "INSERT INTO wallet (user_id, balance, "
                    "monthly_spending_limit, current_month_spent, "
                    "last_reset_at) VALUES (?, ?, ?, 0.0, ?)")
                self.pl_utils._execute_db_command(
                    wallet_insert,
                    (user_id, new_monthly_limit, new_monthly_limit,
                     current_time),
                    commit=True)

            action_info = {"monthly_spending_limit": new_monthly_limit}
            self.pl_utils._record_trace(
                user_id, ActionType.SET_BUDGET.value,
                action_info, current_time)

            return {
                "success": True,
                "monthly_spending_limit": new_monthly_limit}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def evaluate_alternatives(self, agent_id: int,
                                    current_product: str):
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(current_product)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{current_product}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Query competitor table
            comp_query = (
                "SELECT competitor_product_id, overlap_score, "
                "price_difference FROM competitor "
                "WHERE target_product_id = ?")
            self.pl_utils._execute_db_command(comp_query, (product_id,))
            competitors = self.db_cursor.fetchall()

            alternatives = []
            for comp_row in competitors:
                comp_product_id, overlap_score, price_diff = comp_row
                # Get competitor product details
                comp_prod_query = "SELECT * FROM product WHERE product_id = ?"
                self.pl_utils._execute_db_command(
                    comp_prod_query, (comp_product_id,))
                comp_prod_row = self.db_cursor.fetchone()
                if comp_prod_row:
                    alt = self._product_row_to_dict(comp_prod_row)
                    alt["tiers"] = self._lookup_product_tiers(comp_product_id)
                    alt["overlap_score"] = overlap_score
                    alt["price_difference"] = price_diff
                    # Average rating
                    avg_query = (
                        "SELECT AVG(rating), COUNT(*) FROM product_review "
                        "WHERE product_id = ?")
                    self.pl_utils._execute_db_command(
                        avg_query, (comp_product_id,))
                    avg_row = self.db_cursor.fetchone()
                    alt["avg_rating"] = avg_row[0] if avg_row[0] else 0.0
                    alt["num_reviews"] = avg_row[1] if avg_row[1] else 0
                    alternatives.append(alt)

            action_info = {
                "current_product": current_product,
                "num_alternatives": len(alternatives)}
            self.pl_utils._record_trace(
                user_id, ActionType.EVALUATE_ALTERNATIVES.value,
                action_info, current_time)

            return {
                "success": True,
                "current_product": current_product,
                "alternatives": alternatives}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def react_to_price(self, agent_id: int, message: tuple):
        product_name, tier_name, reaction = message
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Look up tier
            tier_query = (
                "SELECT tier_id, monthly_price FROM product_tier "
                "WHERE product_id = ? AND tier_name = ?")
            self.pl_utils._execute_db_command(
                tier_query, (product_id, tier_name))
            tier_row = self.db_cursor.fetchone()
            if not tier_row:
                return {
                    "success": False,
                    "error": f"Tier '{tier_name}' not found for "
                             f"'{product_name}'."}
            tier_id, price_shown = tier_row

            # Validate reaction
            valid_reactions = {'accepted', 'rejected', 'compared', 'deferred'}
            if reaction not in valid_reactions:
                return {
                    "success": False,
                    "error": f"Invalid reaction. Must be one of: "
                             f"{valid_reactions}"}

            # Insert price reaction
            reaction_insert = (
                "INSERT INTO price_reaction (user_id, product_id, tier_id, "
                "price_shown, reaction, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)")
            self.pl_utils._execute_db_command(
                reaction_insert,
                (user_id, product_id, tier_id, price_shown, reaction,
                 current_time),
                commit=True)
            reaction_id = self.db_cursor.lastrowid

            # Record appropriate funnel event based on reaction
            if reaction == 'accepted':
                stage = 'considering'
            elif reaction == 'rejected':
                stage = 'aware'
            elif reaction == 'compared':
                stage = 'considering'
            else:  # deferred
                stage = 'interested'

            funnel_insert = (
                "INSERT INTO funnel_event (user_id, product_id, stage, "
                "previous_stage, trigger_type, created_at, metadata) "
                "VALUES (?, ?, ?, 'aware', 'react_to_price', ?, ?)")
            self.pl_utils._execute_db_command(
                funnel_insert,
                (user_id, product_id, stage, current_time, reaction),
                commit=True)

            action_info = {
                "product_name": product_name, "tier_name": tier_name,
                "reaction": reaction, "price_shown": price_shown,
                "reaction_id": reaction_id}
            self.pl_utils._record_trace(
                user_id, ActionType.REACT_TO_PRICE.value,
                action_info, current_time)

            return {"success": True, "reaction_id": reaction_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_subscription_status(self, agent_id: int):
        current_time = self._get_current_time()
        try:
            user_id = agent_id

            # Get all subscriptions for this user
            sub_query = (
                "SELECT s.subscription_id, s.product_id, s.tier_id, "
                "s.status, s.started_at, s.trial_ends_at, "
                "s.current_period_start, s.current_period_end, "
                "s.months_active, s.total_paid, "
                "p.product_name, t.tier_name, t.monthly_price "
                "FROM subscription s "
                "JOIN product p ON s.product_id = p.product_id "
                "LEFT JOIN product_tier t ON s.tier_id = t.tier_id "
                "WHERE s.user_id = ?")
            self.pl_utils._execute_db_command(sub_query, (user_id,))
            sub_rows = self.db_cursor.fetchall()

            subscriptions = [{
                "subscription_id": r[0], "product_id": r[1],
                "tier_id": r[2], "status": r[3], "started_at": r[4],
                "trial_ends_at": r[5], "current_period_start": r[6],
                "current_period_end": r[7], "months_active": r[8],
                "total_paid": r[9], "product_name": r[10],
                "tier_name": r[11], "monthly_price": r[12],
            } for r in sub_rows]

            # Get wallet info
            wallet_query = (
                "SELECT balance, total_spent, monthly_spending_limit, "
                "current_month_spent FROM wallet WHERE user_id = ?")
            self.pl_utils._execute_db_command(wallet_query, (user_id,))
            wallet_row = self.db_cursor.fetchone()
            wallet = None
            if wallet_row:
                wallet = {
                    "balance": wallet_row[0],
                    "total_spent": wallet_row[1],
                    "monthly_spending_limit": wallet_row[2],
                    "current_month_spent": wallet_row[3],
                }

            # Get active trials
            trial_query = (
                "SELECT t.trial_id, t.product_id, t.started_at, "
                "t.ends_at, p.product_name "
                "FROM trial t "
                "JOIN product p ON t.product_id = p.product_id "
                "WHERE t.user_id = ? AND t.converted = 0 "
                "AND t.abandon_reason IS NULL")
            self.pl_utils._execute_db_command(trial_query, (user_id,))
            trial_rows = self.db_cursor.fetchall()
            trials = [{
                "trial_id": r[0], "product_id": r[1],
                "started_at": r[2], "ends_at": r[3],
                "product_name": r[4],
            } for r in trial_rows]

            action_info = {
                "num_subscriptions": len(subscriptions),
                "num_trials": len(trials)}
            self.pl_utils._record_trace(
                user_id, ActionType.CHECK_SUBSCRIPTION_STATUS.value,
                action_info, current_time)

            return {
                "success": True,
                "subscriptions": subscriptions,
                "trials": trials,
                "wallet": wallet}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browse_reviews(self, agent_id: int, product_name: str):
        current_time = self._get_current_time()
        try:
            user_id = agent_id
            row = self._lookup_product_by_name(product_name)
            if not row:
                return {
                    "success": False,
                    "error": f"Product '{product_name}' not found."}
            prod = self._product_row_to_dict(row)
            product_id = prod["product_id"]

            # Get reviews
            rev_query = (
                "SELECT r.review_id, r.user_id, r.rating, r.content, "
                "r.sentiment_score, r.created_at, u.user_name "
                "FROM product_review r "
                "LEFT JOIN user u ON r.user_id = u.user_id "
                "WHERE r.product_id = ? "
                "ORDER BY r.created_at DESC")
            self.pl_utils._execute_db_command(rev_query, (product_id,))
            rev_rows = self.db_cursor.fetchall()

            reviews = [{
                "review_id": r[0], "user_id": r[1], "rating": r[2],
                "content": r[3], "sentiment_score": r[4],
                "created_at": r[5], "user_name": r[6],
            } for r in rev_rows]

            # Summary stats
            avg_query = (
                "SELECT AVG(rating), COUNT(*) FROM product_review "
                "WHERE product_id = ?")
            self.pl_utils._execute_db_command(avg_query, (product_id,))
            avg_row = self.db_cursor.fetchone()
            avg_rating = avg_row[0] if avg_row[0] else 0.0
            num_reviews = avg_row[1] if avg_row[1] else 0

            action_info = {
                "product_name": product_name,
                "num_reviews": num_reviews}
            self.pl_utils._record_trace(
                user_id, ActionType.BROWSE_REVIEWS.value,
                action_info, current_time)

            return {
                "success": True,
                "product_name": product_name,
                "avg_rating": avg_rating,
                "num_reviews": num_reviews,
                "reviews": reviews}
        except Exception as e:
            return {"success": False, "error": str(e)}
