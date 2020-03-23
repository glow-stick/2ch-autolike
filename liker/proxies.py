#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import random

class Proxies:
    def __init__(self, proxies):
        self.proxies = proxies
        random.shuffle(self.proxies)
        self.current_proxy = 0

    def next_proxy(self):
        proxy = self.proxies[self.current_proxy]
        self.current_proxy = (self.current_proxy + 1) % len(self.proxies)
        if not "://" in proxy:
            proxy = "https://" + proxy
        return {"http": proxy, "https": proxy}

