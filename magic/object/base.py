# -*- coding: utf-8 -*-

from typing import Any, Callable, Optional

from magic.blender import brender
from magic.generation import Rotation3D
from magic.utils.dtypes import PathLike, SDict
from magic.utils.file import exists
from magic.utils.misc import format_error, tsprint


class ObjectAcquirer(object):
    def __init__(self, *, detect_rot: Optional[Callable[[str, PathLike], Rotation3D]] = None, **kwargs: Any) -> None:
        self.__correct_rot = detect_rot  # returned Rotation3D should be in Blender format

    def __call__(self, query: str, output_obj: PathLike, **kwargs: Any) -> tuple[bool, SDict[Any]]:
        acquisition = self._acquire(query, output_obj, **kwargs)
        if isinstance(acquisition, bool):
            is_acquired, extra = acquisition, {}
        elif isinstance(acquisition, (tuple, list)):
            if len(acquisition) == 2:
                is_acquired, extra = acquisition
                if not isinstance(is_acquired, bool):
                    raise TypeError(f"self._acquire() should return a bool as the first element, got {acquisition}")
                if not isinstance(extra, dict):
                    raise TypeError(f"self._acquire() should return a dict as the second element, got {acquisition}")
            else:
                raise ValueError(f"a tuple or list from self._acquire() should have a length of 2, got {acquisition}")
        else:
            raise TypeError(f"self._acquire() should return a bool, tuple or list, got {acquisition}")
        if not is_acquired:
            return is_acquired, extra
        # self.__rotate(query, output_obj)
        if not self.__normalize(output_obj):
            return False, extra
        return exists(output_obj), extra

    def _acquire(self, query: str, output_obj: PathLike, **kwargs: Any) -> bool | tuple[bool, SDict[Any]]:
        raise NotImplementedError("This method should be implemented by subclasses")

    def __rotate(self, query: str, obj_path: PathLike) -> bool:
        if self.__correct_rot is None:
            return exists(obj_path)
        rot = self.__correct_rot(query, obj_path)
        rotate_codes = [
            "clear()",
            f'obj = import_obj(r"{obj_path}")',
            f"transform(obj, position=(0, 0, 0), rotation=({rot.x}, {rot.y}, {rot.z}))",
            f'if not export_obj(r"{obj_path}", obj=obj): raise RuntimeError()',
        ]
        try:
            brender(*rotate_codes, verbose=False)
        except RuntimeError as e:
            tsprint(f"[{self.__class__.__name__}] Error correcting rotation for {obj_path}: {format_error(e)[0]}")
            return False
        return exists(obj_path)

    def __normalize(self, obj_path: PathLike) -> bool:
        normalize_codes = [
            "clear()",
            f'obj = import_obj(r"{obj_path}")',
            "builder = Builder()",
            "builder.normalize(obj)",
            f'if not export_obj(r"{obj_path}", obj=obj): raise RuntimeError()',
        ]
        try:
            brender(*normalize_codes, verbose=False)
        except RuntimeError as e:
            tsprint(f"[{self.__class__.__name__}] Error normalizing object {obj_path}: {format_error(e)[0]}")
            return False
        return exists(obj_path)
