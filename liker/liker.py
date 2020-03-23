#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import time
import threading
import io
import json
from PIL import Image
from thumbnail import Thumbnail
from checker import LikeAction

class Post:
    def __init__(self, num, text, target_likes, images):
        self.num = num
        self.text = text
        self.action = LikeAction.NONE
        self.target_likes = target_likes
        self.likes = 0
        self.images = {}
        for path in images:
            self.images[path] = None

class Liker:
    def __init__(self, board, checker, posts, network):
        self.board = board
        self.checker = checker
        self.network = network
        self.network.set_on_empty_callback(lambda: self.network.get_request("%s/%s/catalog.json" % (self.api, self.board), self._on_threads, None, True, True))
        self.api = "https://2ch.hk"
        self.likes_count = 5
        self.lasthit = -1
        self.posts = {}
        self.req2post = {}
        self.lock = threading.Lock()
        for post_id in posts:
            post = posts[post_id]
            self.posts[post_id] = Post(post_id, None, post["target_likes"], [])
            self.posts[post_id].likes = post["likes"]
            self.posts[post_id].action = LikeAction(post["action"])
            self._process_post(self.posts[post_id])

    def _on_threads(self, res):
        threads = [thread for thread in sorted(res.json()["threads"], key=lambda thread: thread["lasthit"], reverse=True)[:20] if thread["lasthit"] > self.lasthit]
        if not threads:
            return
        self.lasthit = threads[0]["lasthit"]
        for thread in threads:
            self.network.get_request("%s/%s/res/%s.json" % (self.api, self.board, thread["num"]), self._on_posts, None, True, True)

    def _on_posts(self, res):
        for post in res.json()["threads"][0]["posts"]:
            post_id = str(post["num"])
            self.lock.acquire()
            if post_id in self.posts:
                self.lock.release()
                continue
            post = Post(post_id, post["comment"], self.likes_count, [f["thumbnail"] for f in post["files"]])
            self.posts[post.num] = post
            self.lock.release()
            if post.images:
                for path in post.images:
                    self._on_thumbnail(post.num, path, None)
            else:
                self._on_post_ready(post)

    def _on_thumbnail(self, post_id, path, res):
        pixels = None
        width = -1
        height = -1
        try:
            image = Image.open(io.BytesIO(res.content))
            pixels = [item for sublist in image.convert("RGBA").getdata() for item in sublist]
            width = image.width
            height = image.height
        except:
            self.network.get_request("%s%s" % (self.api, path), lambda res, post_id=post_id, path=path: self._on_thumbnail(post_id, path, res), None, True, True)
            return

        self.lock.acquire()
        post = self.posts[post_id]
        post.images[path] = Thumbnail(pixels, width, height)
        post_ready = True
        for key in post.images:
            if not post.images[key]:
                post_ready = False
                break
        self.lock.release()
        if post_ready:
            self._on_post_ready(post)

    def _on_post_ready(self, post):
        post.action = self.checker.check(post)
        self._process_post(post)

    def _process_post(self, post):
        if post.likes >= post.target_likes:
            return
        if post.action == LikeAction.LIKE:
            r_id = self.network.get_request("%s/api/like?board=%s&num=%s" % (self.api, self.board, post.num), lambda res, post=post: self._on_post_like(post, True, res), self._post_continue, False, True)
            self.req2post[r_id] = post
        if post.action == LikeAction.DISLIKE:
            r_id = self.network.get_request("%s/api/dislike?board=%s&num=%s" % (self.api, self.board, post.num), lambda res, post=post: self._on_post_like(post, False, res), self._post_continue, False, True)
            self.req2post[r_id] = post

    def _post_continue(self, req_id):
        try:
            post = self.req2post[req_id]
            return post.likes < post.target_likes
        except Exception as e:
            return True

    def _on_post_like(self, post, like, res):
        if res.json()["Error"] != None:
            print("Post >>%s %sliking failed" % (post.num, "" if like else "dis"))
            self._process_post(post)
            return

        self.lock.acquire()
        post.likes += 1

        print("Post >>%s %sliked (%d / %d)" % (post.num, "" if like else "dis", post.likes, self.likes_count))

        self._process_post(post)

        data = {}
        for post_id in self.posts:
            post = self.posts[post_id]
            data[post.num] = {"action": int(post.action), "likes": post.likes, "target_likes": post.target_likes}
        f = open("data/posts_%s.json" % self.board, "w")
        f.write(json.dumps(data))
        f.close()

        self.lock.release()
