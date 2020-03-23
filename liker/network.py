#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import threading
import requests

agent = "Mozilla/5.0 (X11; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"

class Request:
    def __init__(self, method, url, data, callback, callback_continue, callback_once, proxy):
        self.id = -1
        self.method = method
        self.url = url
        self.data = {}
        self.callback = callback
        self.callback_continue = callback_continue
        self.callback_once = callback_once
        self.proxy = proxy

class Network:
    def __init__(self, proxies, workers):
        self.proxies = proxies
        self.req_id = 0
        self.reqs = []
        self.threads = []
        self.on_empty_cb = None
        self.barrier = threading.Barrier(workers)
        self.lock = threading.RLock()
        for i in range(workers):
            self.threads += [threading.Thread(target=lambda i=i, total=workers: self._worker(i, total))]

    def _worker(self, index, total):
        while True:
            req = None
            proxy = None
            self.lock.acquire()
            if self.reqs:
                req = self.reqs[int(index * len(self.reqs) / (1.0 * total))]
                if req.proxy:
                    proxy = self.proxies.next_proxy()
            else:
                if self.on_empty_cb:
                    self.on_empty_cb()
            self.lock.release()

            if not req:
                continue

            try:
                self.barrier.wait()
                if req.callback_continue and not req.callback_continue(req.id):
                    self.lock.acquire()
                    for i, r in enumerate(self.reqs):
                        if r.id == req.id:
                            self.reqs.pop(i)
                            break
                    self.lock.release()
                    continue
            except Exception as e:
                print("exception in network:")
                print(e)

            try:
                res = None
                if req.method == "GET":
                    res = requests.get(req.url, proxies=proxy, headers={"User-Agent": agent}, timeout=(2, 2))
                self.lock.acquire()
                removed = False
                for i, r in enumerate(self.reqs):
                    if r.id == req.id:
                        removed = True
                        self.reqs.pop(i)
                        break
                self.lock.release()
                if removed or (not removed and not req.callback_once):
                    req.callback(res)
            except Exception as e:
                pass

    def start(self):
        for thread in self.threads:
            thread.start()
        print("Network started with %d threads" % len(self.threads))

    def join(self):
        for thread in self.threads:
            thread.join()

    def set_on_empty_callback(self, cb):
        self.on_empty_cb = cb

    def _request(self, req):
        self.lock.acquire()
        req.id = self.req_id
        self.req_id += 1
        ret = self.req_id
        self.reqs += [req]
        self.lock.release()
        return ret

    def get_request(self, url, callback, callback_continue, callback_once, proxy):
        return self._request(Request("GET", url, None, callback, callback_continue, callback_once, proxy))
