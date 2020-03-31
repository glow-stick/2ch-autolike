#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import threading
import requests
import time

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
        self.new_reqs = []
        self.rem_reqs = []
        self.reqs = []
        self.threads = []
        self.on_empty_cb = None
        self.barrier = threading.Barrier(workers, action=self._process_requests)
        self.lock = threading.RLock()
        for i in range(workers):
            self.threads += [threading.Thread(target=lambda i=i, total=workers: self._worker(i, total))]

    def _process_requests(self):
        self.lock.acquire()
        self.reqs = [req for req in self.reqs if not req.id in self.rem_reqs]
        self.reqs += self.new_reqs
        self.rem_reqs = []
        self.new_reqs = []
        self.lock.release()

    def _worker(self, index, total):
        while True:
            try:
                self.barrier.wait()
            except Exception as e:
                print("barrier exception")
                print(e)
                pass

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

            #print(str(index) + ": (" + str(req.id) + ") " + req.url)

            try:
                if req.callback_continue and not req.callback_continue(req.id):
                    self.lock.acquire()
                    self.rem_reqs += [req.id]
                    #print(str(index) + ": continue")
                    self.lock.release()
                    continue
            except Exception as e:
                print("exception in network:")
                print(e)

            try:
                res = None
                if req.method == "GET":
                    res = requests.get(req.url, proxies=proxy, headers={"User-Agent": agent}, timeout=2)
                self.lock.acquire()
                removed = req.id in self.rem_reqs
                if not removed:
                    self.rem_reqs += [req.id]
                self.lock.release()
                if removed or (not removed and not req.callback_once):
                    req.callback(res)
            except Exception as e:
                #print(req.url)
                #print(e)
                pass
            time.sleep(0.1)

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
        self.new_reqs += [req]
        self.lock.release()
        return req.id

    def get_request(self, url, callback, callback_continue, callback_once, proxy):
        return self._request(Request("GET", url, None, callback, callback_continue, callback_once, proxy))
