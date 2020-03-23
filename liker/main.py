#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import sys
import base64
import json

from proxies import Proxies
from network import Network
from comparator import Comparator
from checker import Checker
from liker import Liker

def main():
    if len(sys.argv) < 2:
        print("Usage: " + sys.argv[0] + " <board>")
        return

    board = sys.argv[1]

    posts = {}
    try:
        posts = json.loads(open("data/posts_%s.json" % board).read())
    except Exception as e:
        pass

    regexps_like = [regex.split("\n")[0] for regex in open("data/regexps_like").readlines()]
    regexps_dislike = [regex.split("\n")[0] for regex in open("data/regexps_dislike").readlines()]
    comparator_dislike = Comparator(open("data/comparator.wasm", "rb").read(), [base64.b64decode(image.split("\n")[0]) for image in open("data/images").readlines()])
    checker = Checker(regexps_like, regexps_dislike, comparator_dislike)

    proxies = Proxies([proxy.split("\n")[0] for proxy in open("data/proxies").readlines()])
    network = Network(proxies, 10)

    liker = Liker(board, checker, posts, network)

    network.start()
    network.join()

main()
