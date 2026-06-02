# -*- coding: utf-8 -*-

from typing import Any

from magic.object.base import ObjectAcquirer


class ObjectGenerator(ObjectAcquirer):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
