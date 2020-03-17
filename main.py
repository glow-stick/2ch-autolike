#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import time
import requests
import threading
import random
import js_regex
import json
import sys
import base64
import wasmer
import io
from PIL import Image

class Comparator:
    def __init__(self, bytecode, images):
        buffer_ptr = 102400 # 100K
        buffer_size = 409600 # 400K
        self.instance = wasmer.Instance(bytecode)
        self.memory = self.instance.memory.uint8_view()
        self.instance.exports.set_ptrs(buffer_ptr, buffer_ptr + buffer_size)
        self.buffer_ptr = self.instance.exports.get_buffer_ptr()
        self.db_ptr = self.instance.exports.get_db_ptr()
        self.memory_ptr = self.instance.exports.get_memory_ptr()
        for image in images:
            db_write_ptr = self.instance.exports.get_db_write_ptr()
            self.memory[db_write_ptr:db_write_ptr+len(image)] = image
            self.instance.exports.on_write_to_db(len(image))

    def compare(self, image, width, height):
        self.memory[self.buffer_ptr:self.buffer_ptr+len(image)] = image
        rate = self.instance.exports.find_buffer_in_db(width, height)
        return rate != -1 and rate < 10

class Proxies:
    def __init__(self, proxies):
        self.proxies = proxies
        random.shuffle(self.proxies)
        self.current_proxy = 0

    def next_proxy(self):
        proxy = self.proxies[self.current_proxy]
        self.current_proxy = (self.current_proxy + 1) % len(self.proxies)
        return {"http": "http://" + proxy, "https": "https://" + proxy}

class Autoliker:
    def __init__(self, board, comparator, posts_liked, proxies, regexps_like, regexps_dislike):
        self.board = board

        self.comparator = comparator

        self.regexps_like = regexps_like
        self.regexps_dislike = regexps_dislike

        self.proxies = proxies
        self.mutex_proxies = threading.Lock()

        self.net_req_id = 0
        self.mutex_net_req_id = threading.Lock()

        self.net_done_reqs = []
        self.mutex_net_done_reqs = threading.Lock()

        self.likes_count = 5
        self.posts_liked = dict(posts_liked)
        self.mutex_posts = threading.Lock()

        self.threads_loaded = 0
        self.mutex_threads_loaded = threading.Lock()

        self.post_images = {}
        self.mutex_post_images = threading.Lock()

        threads_count = 100

        self.net_requests = []
        self.net_requests_remove = []
        self.mutex_net_requests = threading.Lock()

        self.net_barrier = threading.Barrier(threads_count, action=self._remove_requests)

        self.workers_net = []
        for i in range(threads_count):
            self.workers_net += [threading.Thread(target=lambda i=i, count=threads_count: self._worker_net(i, count))]

        self.worker_posts = threading.Thread(target=self._worker_posts)

    def start(self):
        for thread in self.workers_net:
            thread.start()
        self.worker_posts.start()

    def join(self):
        self.worker_posts.join()
        for thread in self.workers_net:
            thread.join()

    def _remove_requests(self):
        self.mutex_net_requests.acquire()
        self.net_requests_remove = list(set(self.net_requests_remove))
        self.net_requests_remove.sort(reverse=True)
        for i in self.net_requests_remove:
            self.net_requests.pop(i)
        self.net_requests_remove = []
        self.mutex_net_requests.release()

    def _worker_net(self, thread_index, threads_count):
        while True:
            req_id = -1
            req = None
            callback_once = False
            callback_res = None
            callback_continue = None
            current_req = None
            current_req_index = -1

            try:
                self.net_barrier.wait()
            except:
                pass

            self.mutex_net_requests.acquire()
            if self.net_requests:
                current_req_index = int(thread_index * len(self.net_requests) / (1.0 * threads_count))
                current_req = self.net_requests[current_req_index]
            else:
                print("getting threads")
                self._do_proxy_request({"method": "GET", "url": "https://2ch.hk/" + self.board + "/catalog.json"}, True, self._on_threads_received, None, False)
            self.mutex_net_requests.release()

            if current_req:
                req_id = current_req[0]
                req = current_req[1]
                callback_once = current_req[2]
                callback_res = current_req[3]
                callback_continue = current_req[4]
            else:
                continue
            
            if callback_continue and not callback_continue(req_id):
                self.mutex_net_requests.acquire()
                self.net_requests_remove += [current_req_index]
                self.mutex_net_requests.release()
                continue

            self.mutex_net_done_reqs.acquire()
            if req_id in self.net_done_reqs:
                self.mutex_net_done_reqs.release()
                continue
            self.mutex_net_done_reqs.release()

            proxy = None
            if not "noproxy" in req or not req["noproxy"]:
                self.mutex_proxies.acquire()
                proxy = self.proxies.next_proxy()
                self.mutex_proxies.release()

            method = req["method"]
            try:
                res = None
                if method == "GET":
                    res = requests.get(req["url"], proxies=proxy, timeout=(0.5, 0.5))

                self.mutex_net_done_reqs.acquire()
                if req_id in self.net_done_reqs:
                    self.mutex_net_done_reqs.release()
                    if not callback_once:
                        callback_res(req_id, res)
                    continue
                self.net_done_reqs += [req_id]
                self.mutex_net_requests.acquire()
                self.net_requests_remove += [current_req_index]
                self.mutex_net_requests.release()
                self.mutex_net_done_reqs.release()

                try:
                    callback_res(req_id, res)
                except Exception as e:
                    print("ERR")
                    print(e)
            except Exception as e:
                continue

    def _do_proxy_request(self, req, callback_once, callback_res, callback_continue, need_lock):
        req_id = -1

        self.mutex_net_req_id.acquire()
        self.net_req_id += 1
        req_id = self.net_req_id
        self.mutex_net_req_id.release()

        if need_lock:
            self.mutex_net_requests.acquire()
        self.net_requests += [(req_id, req, callback_once, callback_res, callback_continue)]
        if need_lock:
            self.mutex_net_requests.release()

    def _post_check_regex(self, post_id, text):
        replacements = {
            "а": "a",
            "б": "6",
            "в": "vb",
            "г": "g",
            "д": "d",
            "е": "e",
            "ж": "j",
            "з": "z3",
            "и": "iu",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o0",
            "п": "p",
            "р": "rp",
            "с": "cs",
            "т": "t",
            "у": "y",
            "ф": "f",
            "х": "xh",
            "ч": "4"
        }
        post_text = ""
        for c in text:
            ready = False
            c = c.lower()
            for replacement in replacements:
                if ready:
                    break
                for r in replacements[replacement]:
                    if c == r:
                        ready = True
                        post_text += replacement
                        break
            if not ready:
                post_text += c

        for regex in self.regexps_dislike:
            if regex.search(post_text) != None:
                self.posts_liked[post_id] = [False, False, 0, self.likes_count]
                return True
        for regex in self.regexps_like:
            if regex.search(post_text) != None:
                self.posts_liked[post_id] = [True, False, 0, self.likes_count]
                return True
        return False

    def _post_check_image(self, post_id, image):
        ret = self.comparator.compare(image["pixels"], image["width"], image["height"])
        if ret:
            print(post_id + " matches!")
            self.posts_liked[post_id] = [False, False, 0, self.likes_count]
        return ret

    def _on_post_ready(self, post_id, text, images):
        if post_id in self.posts_liked:
            return
        self.mutex_posts.acquire()
        for image in images:
            if self._post_check_image(post_id, images[image]):
                self.mutex_posts.release()
                return
        self._post_check_regex(post_id, text)
        self.mutex_posts.release()

    def _on_post_data_loaded(self, post_id, text, path, data):
        self.mutex_post_images.acquire()
        post_images = self.post_images[post_id]
        post_images["files"][path] = data
        if len(post_images["files"]) >= post_images["cnt"]:
            self._on_post_ready(post_id, text, post_images["files"])
        self.mutex_post_images.release()

    def _on_post_image_received(self, req_id, res, post_id, post_text, path):
        image = Image.open(io.BytesIO(res.content))
        pixels = [item for sublist in image.convert("RGBA").getdata() for item in sublist]
        self._on_post_data_loaded(post_id, post_text, path, {"pixels": pixels, "width": image.width, "height": image.height})

    def _post_load_files(self, post_id, post_text, files):
        count = len(files)
        self.mutex_post_images.acquire()
        if not post_id in self.post_images:
            self.post_images[post_id] = {"cnt": len(files), "files": {}}
        post_images = self.post_images[post_id]
        for f in files:
            path = f["thumbnail"]
            if path in post_images:
                self._on_post_data_loaded(post_id, post_text, path, post_images[path])
            else:
                callback = lambda req_id, res, post_id=post_id, post_text=post_text, path=path: self._on_post_image_received(req_id, res, post_id, post_text, path)
                self._do_proxy_request({"method": "GET", "url": "https://2ch.hk" + path, "noproxy": True}, True, callback, None, True)
        self.mutex_post_images.release()

    def _on_posts_received(self, count, req_id, res):
        thread = res.json()
        thread_num = thread["current_thread"]
        posts = thread["threads"][0]["posts"]

        for post in posts:
            post_id = str(post["num"])
            post_text = post["comment"]
            if post["files"]:
                self._post_load_files(post_id, post_text, post["files"])
            else:
                self._on_post_ready(post_id, post_text, {})

        self.mutex_posts.acquire()
        f = open("posts_" + self.board + ".dat", "w")
        f.write(json.dumps(self.posts_liked))
        f.close()
        self.mutex_posts.release()

        self.mutex_threads_loaded.acquire()
        self.threads_loaded += 1
        print("Thread " + thread_num + " loaded. " + str(len(posts)) + " posts (" + str(self.threads_loaded) + " / " + str(count) + ")")
        if self.threads_loaded >= count:
            self.threads_loaded = 0
        self.mutex_threads_loaded.release()

    def _on_threads_received(self, req_id, res):
        threads = [thread["num"] for thread in sorted(res.json()["threads"], key=lambda thread: thread["lasthit"])][-10:]
        print(str(len(threads)) + " threads loaded")
        for thread in threads:
            self._do_proxy_request({"method": "GET", "url": "https://2ch.hk/" + self.board + "/res/" + thread + ".json"}, True, lambda req_id, res: self._on_posts_received(len(threads), req_id, res), None, True)

    def _on_post_can_continue(self, post_id, req_id):
        self.mutex_posts.acquire()

        post = self.posts_liked[post_id]
        res = post[2] < post[3]
        post[1] = res

        self.mutex_posts.release()

        return res

    def _on_post_like(self, post_id, req_id, res):
        self.mutex_posts.acquire()
        post = self.posts_liked[post_id]
        post[1] = post[2] >= post[3]
        if not res.json()["Error"]:
            post[2] += 1
            print(str(req_id) + " " + ("Liking" if post[0] else "Disliking") + " post " + post_id + " successful (" + str(post[2]) + " / " + str(post[3]) + ")")
        else:
            print(str(req_id) + " " + ("Liking" if post[0] else "Disliking") + " post " + post_id + " failed")
        self.mutex_posts.release()

    def _worker_posts(self):
        while True:
            self.mutex_posts.acquire()
            for post_id in self.posts_liked:
                post = self.posts_liked[post_id]
                method = "like" if post[0] else "dislike"
                if not post[1] and post[2] < post[3]:
                    post[1] = True
                    callback_res = lambda req_id, res, post_id=post_id: self._on_post_like(post_id, req_id, res)
                    callback_continue = lambda req_id, post_id=post_id: self._on_post_can_continue(post_id, req_id)
                    self._do_proxy_request({"method": "GET", "url": "https://2ch.hk/api/" + method + "?board=" + self.board + "&num=" + post_id}, False, callback_res, callback_continue, True)
            self.mutex_posts.release()

def main():
    if len(sys.argv) < 2:
        print("Usage: " + sys.argv[0] + " <board>")
        return

    board = sys.argv[1]

    posts_liked = {}
    try:
        posts_liked = json.loads(open("posts_" + board + ".dat").read())
        for post_id in posts_liked:
            posts_liked[post_id][1] = False
    except:
        pass

    images = [base64.b64decode(image.split("\n")[0]) for image in open("images").readlines()]
    print(str(len(images)) + " images loaded")

    comparator = Comparator(open("comparator.wasm", "rb").read(), images)

    regexps_like = [js_regex.compile(regex.split("\n")[0]) for regex in open("regexps_like").readlines()]
    regexps_dislike = [js_regex.compile(regex.split("\n")[0]) for regex in open("regexps_dislike").readlines()]
    proxies = Proxies([proxy.split("\n")[0] for proxy in open("proxies").readlines()])
    autoliker = Autoliker(board, comparator, posts_liked, proxies, regexps_like, regexps_dislike)
    autoliker.start()
    autoliker.join()

main()
