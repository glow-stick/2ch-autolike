#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import re
from enum import IntEnum

class LikeAction(IntEnum):
    NONE = 0
    LIKE = 1
    DISLIKE = 2

class Checker:
    def __init__(self, re_like, re_dislike, cmp_dislike):
        self.re_like = [re.compile(regex) for regex in re_like]
        self.re_dislike = [re.compile(regex) for regex in re_dislike]
        self.cmp_dislike = cmp_dislike
        self.replacements = {
            "а": ["a"],
            "б": ["6"],
            "в": ["v", "b"],
            "г": ["g"],
            "д": ["d"],
            "е": ["e"],
            "ж": ["j"],
            "з": ["z", "3"],
            "и": ["i", "u"],
            "к": ["k"],
            "л": ["l"],
            "м": ["m"],
            "н": ["n"],
            "о": ["o", "0"],
            "п": ["p"],
            "р": ["r", "p"],
            "с": ["c", "s"],
            "т": ["t"],
            "у": ["y"],
            "ф": ["f"],
            "х": ["x", "h", "}{"],
            "ч": ["4"]
        }

    def _check_regex(self, text):
        text = text.lower()
        for replacement in self.replacements:
            for r in self.replacements[replacement]:
                text = text.replace(r, replacement)
        for regex in self.re_dislike:
            if regex and regex.search(text) != None:
                return LikeAction.DISLIKE
        for regex in self.re_like:
            if regex.search(text) != None:
                return LikeAction.LIKE
        return LikeAction.NONE

    def _check_image(self, image):
        ret = self.cmp_dislike.compare(image.pixels, image.width, image.height)
        return LikeAction.DISLIKE if ret else LikeAction.NONE

    def check(self, post):
        action = self._check_regex(post.text)
        if action != LikeAction.NONE:
            return action
        for path in post.images:
            action = self._check_image(post.images[path])
            if action != LikeAction.NONE:
                print(post.num + " matches!")
                return action
        return LikeAction.NONE
