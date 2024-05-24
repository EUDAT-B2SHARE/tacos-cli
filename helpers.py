#!/usr/bin/env python3

import cProfile
from enum import IntEnum
import functools
import logging
import math
import pstats
import time

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
}

DTR_API = {
    "types": "/v1/types/",
    "schema": "/v1/types/schema/",
}

MSCR_API = {
    "crosswalk": "/datamodel-api/v2/crosswalk/",
    "schema": "/datamodel-api/v2/schema/",
    "schemaFull": "/datamodel-api/v2/schemaFull",
    "dtr-type": "/datamodel-api/v2/dtr/schema/",
    "schema": "/v1/types/schema/"
}

## This is what MSCR UI sends to backend
## NOTE THE USE OF "status" instead of "state" from the example in MSCR docs
MSCR_JSON_DATA = {
    "namespace": "http://test.com",
    "description": {},
    "label": {
        "en": "test"
    },
    "languages": [
        "en"
    ],
    "organizations": [],
    "status": "DRAFT",
    "format": "JSONSCHEMA",
    "state": "DRAFT",
    "versionLabel": "1"
}

## This is what MSCR docs example specifies
# MSCR_JSON_DATA = {
#     "state": "DRAFT",
#     "visibility": "PRIVATE",
#     "namespace": "http://example.com/test1",
#     "versionLabel": "just testing",
#     "label": {
#         "en": "First test"
#     },
#     "description": {
#         "en": ""
#     },
#     "languages": [
#         "en"
#     ],
#     "organizations": [],
#     "format": "JSONSCHEMA"
# }


class Verbosity(IntEnum):
    """Verbosity level as described by Nagios Plugin guidelines."""
    # Single line, minimal output. Summary
    NONE = 0
    # Single line, additional information (eg list processes that fail)
    SINGLE = 1
    # Multi line, configuration debug output (eg ps command used)
    MULTI = 2
    # Lots of detail for plugin problem diagnosis
    DEBUG = 3

class DTRType:

    def __init__(self, id, name, type, parent=None, child=None, elements=None):
        self.id = id
        self.name = name
        self.type = type
        self.resolved = None
        self.parent = parent
        self.child = child
        if elements is None:
            elements = []
        self.elements = elements

class DTRSchema:

    def __init__(self, id, name, elements=None):
        self.id = id
        self.name = name
        self.resolved = None
        if elements is None:
            elements = []
        self.elements = elements

class MSCRSchemaElement:
    
    def __init__(self, id, name):
        self.id = id
        self.name = name

class MSCRSchema:

    def __init__(self, id, elements):
        self.id = id
        if elements is None:
            elements = {}
        self.elements = elements

# class Schema:

#     def __init__(self, id, name):
#         self.id = id
#         self.at_dtr = 
#         self.at_mscr = 
#         self.json_schema = name


def add_mscr_options(func):
    """Add MSCR related options to click commands."""
    @click.option(
        "--mscr-token",
        type=click.STRING,
        envvar="MSCR_TOKEN",
        # required=True,
        help="Token for MSCR API",
    )
    @click.option(
        "--mscr-url",
        type=click.STRING,
        envvar="MSCR_URL",
        default="https://mscr-test.rahtiapp.fi",
        help="Base URL for MSCR",
    )

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper

def add_log_and_verbose_options(func):
    """Add log and verbose options to click commands."""
    @click.option(
        "--log-level",
        default="WARNING",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        show_default=True,
        help="Set logging level.",
        envvar="LOG_LEVEL"
    )
    @click.option('-v', '--verbose', count=True)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper

def time_decorator(f):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        t1 = time.perf_counter()
        try:
            r = ctx.invoke(f, *args, **kwargs)
            return r
        except Exception as e:
            raise e
        finally:
            t2 = time.perf_counter()
            mins = math.floor(t2-t1) // 60
            hours = mins // 60
            secs = (t2-t1) - 60 * mins - 3600 * hours
            log.info(f"Execution in {hours:02d}:{mins:02d}:{secs:0.4f}")
        
    return functools.update_wrapper(new_func, f)


def profile_decorator(f):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        if ctx.params["profiling"]:
            with cProfile.Profile() as profile:
                r = ctx.invoke(f, *args, **kwargs)
                with open(ctx.params["profiling_file"], "w") as sfs:
                    pstats.Stats(profile, stream=sfs).strip_dirs().sort_stats(
                        ctx.params["profiling_sort_key"]
                    ).print_stats()
                return r
        else:
            r = ctx.invoke(f, *args, **kwargs)
            return r

    return functools.update_wrapper(new_func, f)


def log_decorator(f):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        log.setLevel(log_levels[ctx.params["log_level"]])
        log.info("Starting")
        r =  ctx.invoke(f,  *args, **kwargs)
        log.info("Finishing")
        return r

    return functools.update_wrapper(new_func, f)


# From https://stackoverflow.com/a/38491565
def replace_keys(old_dict, key_dict):
    """
    Replaces old_dict keys that match key_dict keys, with values of key_dict.
    """
    new_dict = { }
    for key in old_dict.keys():
        new_key = key_dict.get(key, key)
        if isinstance(old_dict[key], dict):
            new_dict[new_key] = replace_keys(old_dict[key], key_dict)
        else:
            new_dict[new_key] = old_dict[key]
    return new_dict
    

# From https://stackoverflow.com/a/3405772
def delete_keys_from_dict(dict_del, lst_keys):
    """Deletes all keys from dictionary that match keys-list."""
    for k in lst_keys:
        try:
            del dict_del[k]
        except KeyError:
            pass
    for v in dict_del.values():
        if isinstance(v, dict):
            delete_keys_from_dict(v, lst_keys)
    return dict_del


def construct_object(data, recursion_depth=0, first_run=False, parent=None):
    """
    Creates object than contains DTR Schema and DTR Types for 
    all DTR Schema elements.
    """
    parent_param = parent
    recursion_depth_param = recursion_depth

    print(recursion_depth_param)

    new_recursion_depth = recursion_depth_param + 1

    if first_run:
        dtr_schema = DTRSchema(data.get("pid"), data.get("name"))
        # Start recurse
        if data.get("content", None).get("Schema", None) is not None:
            for e in data["content"]["Schema"]["Properties"]:
                # print(e)
                o = construct_object(
                    e, 
                    recursion_depth = new_recursion_depth, 
                    parent=dtr_schema
                    )
                dtr_schema.elements.append(o)
        return dtr_schema
    
    # Check if current element is an array
    if data.get("Type", None) is not None:
        print("AT Type.fundamentalType")
        if data.get("Type", None).get("fundamentalType", None) == "Array":
            pid = data["Type"]["pid"]
            name = data["Type"]["name"]
            print("AT Type.fundamentalType.Array")
            # Check if child is an Array
            if data["Type"]["content"]["Schema"].get("Type", None) == "Array":
                # Take subCond and recurse
                print("AT Type.fundamentalType.Array.Array")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name, 
                    type="Array",
                    parent = parent_param,
                    )
                dtr_object.child = construct_object(
                    data["Type"]["content"]["Schema"]["subCond"], 
                    recursion_depth = new_recursion_depth,
                    parent=dtr_object
                    )

            # Check if child is an Object  
            elif data["Type"]["content"]["Schema"].get("Type", None) == "Object":
                pid = data["Type"]["pid"]
                name = data["Type"]["name"]
                print("AT Type.fundamentalType.Array.Object")
                print("Name {}".format(name))
                # Child is an object. For loop and add to elements.
                dtr_object = DTRType(pid, name, type="Object", parent=parent_param)
                for e in data["Type"]["content"]["Schema"]["Properties"]:
                    o = construct_object(
                        e, 
                        recursion_depth = new_recursion_depth, 
                        parent=dtr_object
                        )
                    dtr_object.elements.append(o)

            # Not an Array not an Object, could it still be InfoType
            # elif data["Type"].get("type", None) == "InfoType":
            #     # Maybe this an object, within object
            #     # or an Array, within Object
            #     # or an Array, within Array
            #     dtr_object = DTRType(
            #         pid, 
            #         name, 
            #         type, 
            #         child=construct_object(data["Type"]["content"]["Schema"]))

            else:
                # Not an Array or Object or InfoType. Parse ["content"]["Schema"]
                # No need to recurse anymore
                pid = data["Type"]["pid"]
                name = data["Type"]["name"]
                print("AT Type.fundamentalType.Array.Other")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name,
                    type = "BasicInfoType",
                    parent = parent_param
                    )
    
        elif data.get("Type", None).get("fundamentalType", None) == "Object": 
            # This is an Object
            pid = data["Type"]["pid"]
            name = data["Type"]["name"]
            print("AT Type.fundamentalType.Object")
            # Check if child is an Array
            if data["Type"]["content"]["Schema"].get("Type", None) == "Array":
                print("AT Type.fundamentalType.Object.Array")
                print("Name {}".format(name))
                # Take subCond and recurse
                dtr_object = DTRType(pid, name, type="Array", parent=parent_param)
                dtr_object.child = construct_object(
                    data["Type"]["content"]["Schema"]["subCond"], 
                    recursion_depth = new_recursion_depth,
                    parent=dtr_object
                    )
                
            # Check if child is an Object   
            elif data["Type"]["content"]["Schema"].get("Type", None) == "Object":
                print("AT Type.fundamentalType.Object.Object")
                print("Name {}".format(name))
                # Child is an object. For loop and add to elements.
                dtr_object = DTRType(pid, name, type="Object", parent=parent_param)
                for e in data["Type"]["content"]["Schema"]["Properties"]:
                    o = construct_object(
                        e, 
                        recursion_depth = new_recursion_depth, 
                        parent=dtr_object
                        )
                    dtr_object.elements.append(o)

            # # Not an Array not an Object, could it still be InfoType
            # elif data["Type"].get("type", None) == "InfoType":
            #     # Maybe this an object, within object
            #     # or an Array, within Object
            #     # or an Array, within Array
            #     dtr_object = DTRType(
            #         pid, 
            #         name, 
            #         type="InfoType", 
            #         child=construct_object(data["Type"]["content"]["Schema"]))

            else:
                # Child is not an Array or Object (or InfoType?).
                # No need to recurse anymore
                # type = data["Type"]["type"]
                print("AT Type.fundamentalType.Object.Other")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name,
                    type = "BasicInfoType",
                    parent = parent_param
                    )
                
        else:
            # Not an Array or Object. # No need to recurse anymore
            pid = data["Type"]["pid"]
            name = data["Name"]
            type = data["Type"]["type"]
            print("AT_END_OF_Type.fundamentalType")
            print("Name {}".format(name))
            # print(data)
            dtr_object = DTRType(
                pid, 
                name, 
                type = "BasicInfoType",
                parent = parent_param
                )
    # "Type" does not exist on top-level. Check for fundamentalType
    elif data.get("fundamentalType", None) is not None:
        print("AT fundamentalType")
        if data.get("fundamentalType", None) == "Array": 
            # This is an Object
            pid = data["pid"]
            name = data["name"]
            print("AT fundamentalType.Array")
            # Check if child is an Array
            if data["content"]["Schema"].get("Type", None) == "Array":
                # Take subCond and recurse
                print("AT fundamentalType.Array.Array")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name, 
                    type="Array",
                    parent = parent_param)
                dtr_object.child = construct_object(
                    data["content"]["Schema"]["subCond"], 
                    recursion_depth = new_recursion_depth,
                    parent=dtr_object
                    )
                
            # Check if child is an Object   
            elif data["content"]["Schema"].get("Type", None) == "Object":
                # Child is an object. For loop and add to elements.
                print("AT fundamentalType.Array.Object")
                print("Name {}".format(name))
                dtr_object = DTRType(pid, name, type="Object", parent=parent_param)
                for e in data["content"]["Schema"]["Properties"]:
                    # print(e)
                    o = construct_object(e, recursion_depth = new_recursion_depth, parent=dtr_object)
                    dtr_object.elements.append(o)

            else:
                # Child is not an Array or Object (or InfoType?).
                # No need to recurse anymore
                # type = data["Type"]["type"]
                print("AT fundamentalType.Array.Other")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name,
                    type = "BasicInfoType",
                    parent = parent_param
                    )
                
        elif data.get("fundamentalType", None) == "Object": 
            # This is an Object
            pid = data["pid"]
            name = data["name"]
            print("AT fundamentalType.Object")
            # Check if child is an Array
            if data["content"]["Schema"].get("Type", None) == "Array":
                # Take subCond and recurse
                print("AT fundamentalType.Object.Array")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name, 
                    type="Array",
                    parent = parent_param)
                dtr_object.child = construct_object(
                    data["content"]["Schema"]["subCond"], 
                    recursion_depth = new_recursion_depth,
                    parent=dtr_object
                    )
                
            # Check if child is an Object   
            elif data["content"]["Schema"].get("Type", None) == "Object":
                # Child is an object. For loop and add to elements.
                print("AT fundamentalType.Object.Object")
                print("Name {}".format(name))
                dtr_object = DTRType(pid, name, type="Object", parent=parent_param)
                for e in data["content"]["Schema"]["Properties"]:
                    # print(e)
                    o = construct_object(e, recursion_depth = new_recursion_depth, parent=dtr_object)
                    dtr_object.elements.append(o)

            # # Not an Array not an Object, could it still be InfoType
            # elif data["Type"].get("type", None) == "InfoType":
            #     # Maybe this an object, within object
            #     # or an Array, within Object
            #     # or an Array, within Array
            #     dtr_object = DTRType(
            #         pid, 
            #         name, 
            #         type="InfoType", 
            #         child=construct_object(data["Type"]["content"]["Schema"]))

            else:
                # Child is not an Array or Object (or InfoType?).
                # No need to recurse anymore
                # type = data["Type"]["type"]
                print("AT fundamentalType.Object.Other")
                print("Name {}".format(name))
                dtr_object = DTRType(
                    pid, 
                    name,
                    type = "BasicInfoType",
                    parent = parent_param
                    )
        else:
            # Not an Array or Object. # No need to recurse anymore
            pid = data["pid"]
            name = data["name"]
            type = data["type"]
            print("AT_END_OF_fundamentalType")
            print("Name {}".format(name))
            # print(data)
            dtr_object = DTRType(
                pid, 
                name, 
                type = "BasicInfoType",
                parent = parent_param
                )
    else:
        # Not an Array or Object. # No need to recurse anymore
        print("AT_END")
        # print(data)
        pid = data["Type"]["pid"]
        name = data["Type"]["name"]
        type = data["Type"]["type"]
        dtr_object = DTRType(
            pid, 
            name, 
            type = "BasicInfoType",
            parent = parent_param
            )

    return dtr_object