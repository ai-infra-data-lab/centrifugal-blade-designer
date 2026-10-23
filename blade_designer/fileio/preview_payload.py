"""Bounded, non-executable internal preview transfer; not a project format."""
import base64
from dataclasses import fields, is_dataclass
from enum import Enum
import json
import math

import numpy as np

MAX_BYTES = 96 * 1024 * 1024
MAX_NODES = 100000


def _registry():
    from ..models import geometry, geometry_3d, meridional, flow_area, validation
    from ..models.parameters import SurfaceMapping
    from ..geometry import preview_computation, impeller_trim
    result = {"SurfaceMapping": SurfaceMapping}
    for module in (geometry, geometry_3d, meridional, flow_area, validation,
                   preview_computation, impeller_trim):
        for name, cls in vars(module).items():
            if (isinstance(cls, type) and cls.__module__ == module.__name__
                    and (is_dataclass(cls) or issubclass(cls, Enum))):
                result[module.__name__ + "." + name] = cls
    return result


def _dtype(value):
    if not isinstance(value, str):raise ValueError("Invalid preview dtype.")
    dtype = np.dtype(value)
    if dtype.fields or dtype.subdtype or dtype.kind not in "biuf" or dtype.itemsize > 8:
        raise ValueError("Unsupported preview dtype.")
    return dtype


def dumps(value):
    registry = _registry()
    names = {cls: name for name, cls in registry.items()}
    nodes = []; memo = {}

    def encode(obj, depth=0):
        if depth > 128:raise ValueError("Preview nesting limit exceeded.")
        if obj is None or type(obj) in (bool, int, str):return obj
        if type(obj) is float:
            return obj if math.isfinite(obj) else {"float": str(obj)}
        if isinstance(obj, np.generic):
            _dtype(obj.dtype.str)
            return {"scalar": obj.dtype.str, "value": encode(obj.item(),depth+1)}
        if id(obj) in memo:return {"ref": memo[id(obj)][0]}
        if len(nodes) >= MAX_NODES:raise ValueError("Preview node limit exceeded.")
        # Retain temporary numpy scalar arrays too; their ids must not be reused.
        index = len(nodes); memo[id(obj)] = (index,obj); nodes.append(None)
        if isinstance(obj, np.ndarray):
            _dtype(obj.dtype.str)
            if obj.nbytes > MAX_BYTES:raise ValueError("Preview array limit exceeded.")
            node = {"type": "array", "dtype": obj.dtype.str, "shape": list(obj.shape),
                    "data": base64.b64encode(obj.tobytes()).decode("ascii")}
        elif type(obj) in (list, tuple):
            node = {"type": type(obj).__name__, "items": [encode(v,depth+1) for v in obj]}
        elif type(obj) is dict:
            node = {"type": "dict", "items": [[encode(k,depth+1),encode(v,depth+1)] for k,v in obj.items()]}
        elif type(obj) in names and isinstance(obj, Enum):
            node = {"type": "enum", "class": names[type(obj)], "value": obj.value}
        elif type(obj) in names and is_dataclass(obj):
            node = {"type": "dataclass", "class": names[type(obj)],
                    "fields": {f.name: encode(getattr(obj,f.name),depth+1) for f in fields(obj)}}
        else:raise ValueError("Unsupported preview value: " + type(obj).__name__)
        nodes[index] = node
        return {"ref": index}

    root = encode(value)
    data = json.dumps({"version": 1, "root": root, "nodes": nodes},
                      allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_BYTES:raise ValueError("Preview payload limit exceeded.")
    return data


def loads(data):
    if len(data) > MAX_BYTES:raise ValueError("Preview payload limit exceeded.")
    registry = _registry()
    doc = json.loads(data)
    if (not isinstance(doc,dict) or set(doc)!={"version","root","nodes"}
            or type(doc["version"]) is not int or doc["version"]!=1):
        raise ValueError("Invalid preview payload.")
    nodes = doc["nodes"]
    if not isinstance(nodes,list) or len(nodes)>MAX_NODES:raise ValueError("Invalid preview nodes.")
    cache = {}; active = set(); total_bytes = 0

    def decode(value, depth=0):
        nonlocal total_bytes
        if depth > 128:raise ValueError("Preview nesting limit exceeded.")
        if value is None or type(value) in (bool,int,str):return value
        if type(value) is float and math.isfinite(value):return value
        if not isinstance(value,dict):raise ValueError("Invalid preview value.")
        if set(value)=={"float"}:
            if value["float"] not in ("nan","inf","-inf"):raise ValueError("Invalid special float.")
            return float(value["float"])
        if set(value)=={"scalar","value"}:
            dtype=_dtype(value["scalar"]);number=decode(value["value"],depth+1)
            if type(number) not in (bool,int,float):raise ValueError("Invalid preview scalar.")
            return dtype.type(number)
        if set(value)!={"ref"} or type(value["ref"]) is not int:raise ValueError("Invalid preview reference.")
        index=value["ref"]
        if not 0<=index<len(nodes) or index in active:raise ValueError("Invalid or cyclic preview reference.")
        if index in cache:return cache[index]
        active.add(index); node=nodes[index]
        if not isinstance(node,dict):raise ValueError("Invalid preview node.")
        kind=node.get("type")
        if kind=="array" and set(node)=={"type","dtype","shape","data"}:
            dtype=_dtype(node["dtype"]);shape=node["shape"]
            if not isinstance(shape,list) or len(shape)>4 or any(type(s) is not int or s<0 for s in shape):
                raise ValueError("Invalid preview shape.")
            size=math.prod(shape)*dtype.itemsize;total_bytes+=size
            if total_bytes>MAX_BYTES or not isinstance(node["data"],str) or len(node["data"])!=4*((size+2)//3):
                raise ValueError("Invalid preview array size.")
            raw=base64.b64decode(node["data"],validate=True)
            if len(raw)!=size:raise ValueError("Truncated preview array.")
            result=np.frombuffer(raw,dtype=dtype).reshape(shape).copy()
        elif kind in ("list","tuple","dict") and set(node)=={"type","items"} and isinstance(node["items"],list):
            if kind=="dict":
                pairs=node["items"]
                if any(not isinstance(p,list) or len(p)!=2 for p in pairs):raise ValueError("Invalid preview mapping.")
                result={decode(k,depth+1):decode(v,depth+1) for k,v in pairs}
                if len(result)!=len(pairs):raise ValueError("Duplicate preview mapping key.")
            else:
                result=[decode(v,depth+1) for v in node["items"]]
                if kind=="tuple":result=tuple(result)
        elif kind in ("dataclass","enum") and isinstance(node.get("class"),str) and node["class"] in registry:
            cls=registry[node["class"]]
            if kind=="enum" and set(node)=={"type","class","value"} and issubclass(cls,Enum):
                result=cls(node["value"])
            elif kind=="dataclass" and set(node)=={"type","class","fields"} and is_dataclass(cls):
                values=node["fields"]
                if not isinstance(values,dict) or set(values)!={f.name for f in fields(cls)}:
                    raise ValueError("Invalid preview dataclass fields.")
                result=cls(**{k:decode(v,depth+1) for k,v in values.items()})
            else:raise ValueError("Invalid preview class node.")
        else:raise ValueError("Unsupported preview node.")
        active.remove(index);cache[index]=result
        return result

    return decode(doc["root"])
