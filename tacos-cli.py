#!/usr/bin/env python3

import json
import sys
import traceback

import click
from dotenv import load_dotenv
import requests

from helpers import(
    construct_object,
    MSCR_API,
    MSCR_JSON_DATA,
    DTR_API,
    Verbosity, 
    log, 
    log_decorator, 
    time_decorator,
    add_mscr_options,
    add_log_and_verbose_options,
    delete_keys_from_dict
    )

load_dotenv()

def fetch_type_info(type_api_resp, type_api_url=None, verbose=False):
    """Recursively fetches Type info from DTR."""

    if not type_api_url:
        type_api_url = "https://typeapi.lab.pidconsortium.net/v1/types/"

    data = type_api_resp

    # Note: This is using type_api, which wraps the Cordra responses under "content" key.
    if data.get("content", None).get("Schema", None) is not None:
        # Check if it is an array
        if data["content"]["Schema"].get("Type", None) == "Array":
            link=data["content"]["Schema"]["subCond"]
            if verbose:
                log.info("Fetching " + "\"{}\": \"{}\"".format(data["name"],type_api_url+link))
            content_response = requests.get(type_api_url+link)
            data["content"]["Schema"]["Identifier"] = link # Add Identifier -key to arrays. Everything else already has it
            data["content"]["Schema"]["subCond"]=fetch_type_info(content_response.json())
        if data["content"]["Schema"].get("Properties", None) is not None:
            for item in data["content"]["Schema"]["Properties"]:
                if item.get("Type", None) is not None:
                    link=item.get("Type")
                    if verbose:
                        log.info("Fetching " + "\"{}\": \"{}\"".format(item.get("Name"),type_api_url+item.get("Type")))
                    content_response = requests.get(type_api_url+link)
                    item['Type']=fetch_type_info(content_response.json())
    return data

@click.group()
def tacos():
    pass

@tacos.group()
def dtr():
    pass

@tacos.group()
def mscr():
    pass

@dtr.command("fetch-schema")
@click.option('-v', '--verbose', count=True)
@click.option(
    "--output-file",
    help="Output file [default: STDOUT]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@click.option(
    "--dtr-url",
    type=click.STRING,
    envvar="DTR_URL",
    default="https://typeapi.lab.pidconsortium.net",
    help="Base URL for DTR",
)
@click.option(
    '--resolve-subtypes',
    count=True,
    help="If specified, resolves Types for all elements of the Schema."
)
@click.argument(
    'dtr-schema-pid', 
    type=click.STRING,
    # help="PID of Schema in DTR. Maybe 21.T11969/f67c4f7359d2a211fb80 ?",
    envvar="DTR_SCHEMA"
)
@log_decorator
@time_decorator
@add_log_and_verbose_options
def fetch_schema(
    log_level,
    verbose,
    dtr_url,
    resolve_subtypes,
    output_file,
    dtr_schema_pid
):
    """Fetch a Schema from DTR in JSON-Schema format and output it."""
    log.info("This is fetch-schema")
    verbosity = Verbosity(verbose)

    dtr_session = requests.Session()

    try:
        # Fetch DTR schema
        if verbosity >= Verbosity.SINGLE:
            log.info("Fetch DTR Schema from {}".format(dtr_url+DTR_API["types"]+dtr_schema_pid))

        r = dtr_session.get(dtr_url+DTR_API["types"]+dtr_schema_pid)
        if r.status_code != requests.codes.ok:
            msg = "Error. Maybe given DTR Schema PID does not exist at {}?".format(dtr_url)
            log.error(msg)
            r.raise_for_status()

        dtr_data = r.json()

        if resolve_subtypes:
            # Try to resolve types.
            if verbosity >= Verbosity.SINGLE:
                log.info("Trying to resolve Types in fetched DTR Schema")

            if verbosity == Verbosity.DEBUG:
                log.debug(dtr_data)

            log.info("This will take a bit of time...keep waiting...")
            dtr_data = fetch_type_info(dtr_data, dtr_url+DTR_API["types"], verbose=True)
            
            if verbosity >= Verbosity.SINGLE:
                log.info("Types resolved")

            if verbosity == Verbosity.DEBUG:
                log.debug(dtr_data)

        with click.open_file(output_file, "w") as f:
            json.dump(dtr_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        log.error(e)
        log.error(traceback.format_exc())


@dtr.command("fetch-json-schema")
@click.option(
    "--dtr-url",
    type=click.STRING,
    envvar="DTR_URL",
    default="https://typeapi.lab.pidconsortium.net",
    help="Base URL for DTR",
)
@click.option(
    "--output-file",
    help="Output file [default: STDOUT]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@click.argument(
    'dtr-schema-pid', 
    type=click.STRING,
    # help="PID of Schema in DTR. Maybe 21.T11969/f67c4f7359d2a211fb80 ?",
    envvar="DTR_SCHEMA"
)
@log_decorator
@time_decorator
@add_log_and_verbose_options
def fetch_json_schema(
    log_level,
    verbose,
    dtr_url,
    output_file,
    dtr_schema_pid
):
    """Fetch a Schema from DTR and output it."""
    verbosity = Verbosity(verbose)
    dtr_session = requests.Session()

    try:
        # Fetch DTR schema
        if verbosity >= Verbosity.SINGLE:
            log.info("Fetch DTR Schema from {}".format(dtr_url+DTR_API["types"]+dtr_schema_pid))

        r = dtr_session.get(dtr_url+DTR_API["schema"]+dtr_schema_pid)
        
        if r.status_code != requests.codes.ok:
            msg = "JSON-Schema with DTR Schema PID \
                  could not be fetched from {}".format(dtr_url+DTR_API["schema"]+dtr_schema_pid)
            log.error(msg)
            r.raise_for_status()

        # Remove "unique" -keywords from JSON-Schema
        if verbosity >= Verbosity.SINGLE:
            log.info("Remove 'unique' -keywords from fetched JSON-Schema")

        if verbosity == Verbosity.DEBUG:
            log.debug(r.json())

        # dtr_schema_data = replace_keys(r.json(), {"unique":"uniqueItems"})
        dtr_schema_data = delete_keys_from_dict(r.json(), ["unique"])
            
        if verbosity >= Verbosity.SINGLE:
            log.info("Patched")

        if verbosity == Verbosity.DEBUG:
            log.debug(dtr_schema_data)

        with click.open_file(output_file, "w") as f:
            json.dump(dtr_schema_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        log.error(e)
        log.error(traceback.format_exc())


@mscr.command("register-schema")
@click.option(
    "--input-file",
    help="Input file [default: STDIN]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@click.option(
    "--output-file",
    help="Output file [default: STDOUT]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@click.option(
    '--dry-run', 
    count=True,
    help="If specified, no changes are made to MSCR"
)
@log_decorator
@time_decorator
@add_mscr_options
@add_log_and_verbose_options
def register_schema(
    input_file,
    output_file,
    mscr_token,
    mscr_url,
    log_level,
    verbose,
    dry_run
):
    """Register metadata schema into MSCR."""
    verbosity = Verbosity(verbose)
    mscr_session = requests.Session()
    if mscr_token:
        mscr_session.headers.update({"Authorization": "Bearer {}".format(mscr_token)})

    try:
        if verbosity >= Verbosity.SINGLE:
            log.info("Register the JSON-Schema to MSCR {}".format(mscr_url+MSCR_API["schemaFull"]))
        
        if input_file == "-" and sys.stdin.isatty():
            log.critical("Input from stdin which is a tty - aborting")
            return 128
        
        with click.open_file(input_file, "r") as f:
            dtr_json_schema = json.load(f)

        # Send as a form but form data is b'string' created with json.dumps()
        mscr_req_data = {
            # "metadata": (None, json.dumps(MSCR_JSON_DATA, indent=2).encode('utf-8')),
            "metadata": (None, json.dumps(MSCR_JSON_DATA, indent=2).encode('utf-8')),
            "file": (
                "my_schema.json", 
                json.dumps(dtr_json_schema, indent=2).encode('utf-8'), 
                "application/json"
                )
        }

        # myhearders={'Content-Type': 'multipart/form-data'}
        # req = requests.Request('PUT', mscr_url+MSCR_API["schemaFull"], data=mscr_data, headers=myhearders)
        req = requests.Request('PUT', mscr_url+MSCR_API["schemaFull"], files=mscr_req_data)
        prepped_req = mscr_session.prepare_request(req)

        if verbosity == Verbosity.DEBUG:
            reqhearders = '\n'.join(['{}: {}'.format(*hv) for hv in prepped_req.headers.items()])
            log.info(reqhearders)
            log.info(prepped_req.body)

        # HH: Commented out as payload content is not valid for MSCR API
        if not dry_run:
            log.info("This will take a LOT of time...keep waiting...")
            r = mscr_session.send(prepped_req, timeout=200)
            if r.status_code != requests.codes.ok:
                msg = "Could not register JSON-Schema to MSCR"
                log.error(msg)
                log.error(r.status_code)
                log.error(r.text)
                r.raise_for_status()

            if verbosity >= Verbosity.SINGLE:
                log.info("Registered to MSCR")

        if verbosity >= Verbosity.SINGLE:
            log.info("Dry-run to MSCR")

    except Exception as e:
        log.error(e)
        log.error(traceback.format_exc())
 


@mscr.command("add-types")
@click.option(
    "--input-file",
    help="Input file [default: STDIN]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@click.option(
    "--output-file",
    help="Output file [default: STDOUT]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@click.option(
    '--dry-run', 
    count=True,
    help="If specified, no changes are made to MSCR"
)
@click.option(
    '--dtr-schema-pid', 
    type=click.STRING,
    help="PID of Schema in DTR. Maybe 21.T11969/f67c4f7359d2a211fb80 ?",
    envvar="DTR_SCHEMA"
)
@log_decorator
@time_decorator
@add_mscr_options
@add_log_and_verbose_options
def add_types(
    input_file,
    output_file,
    mscr_token,
    mscr_url,
    log_level,
    verbose,
    dry_run,
    dtr_schema_pid
):
    # Read DTR Schema file
    # - Create DTRType for each Type entry in JSON.
    #   "if it has a 'pid' keyword, it is a DTRType object"
    # - Pass in previous DTRType as parent to new DTRTypes
    # - self.child reference is the new DTRType
    # - This smells like recursion
    # - Gather DTRTypes into DTRSchema.elements
    # Generate dtr_types_dict
    # - keys are paths using notation from MSCR. This way we can do string matching.
    # - values are PIDs of DTR Type definitions
    # - Start with elements with no self.child and work way up
    #   - Probably most fool-proof way to construct the paths.
    #     self.elements[0] + '/' + self.elements[1] + '/' + self.elements[2]
    #     grandparent + '/' + parent + '/' + child
    # Read MSCR Schema in internal format
    # - parse using pymantic. subject.value contains the MSCR-Object-ID
    #   for s in graph.subjects():
    #   ...:     print(type(s))
    #   ...:     print(s.value)
    # - Split MSCR-Object-ID with MSCR-Schema-ID.
    #   Only schema element path is left, which you add to mscr_elements -list
    # - Match each element path in mscr_elements with dtr_types_dict
    #   for e in mscr_elements:
    #       # Get rid of root/Root/ prefix.
    #       e_without_prefix = remove_prefix(e, prefix)
    #       dtr_type = dtr_types_dict[e_without_prefix]
    #       # PATCH dtr_type to https://mscr-test.rahtiapp.fi/datamodel-api/v2/dtr/schema/
    
    verbosity = Verbosity(verbose)
    mscr_session = requests.Session()
    if mscr_token:
        mscr_session.headers.update({"Authorization": "Bearer {}".format(mscr_token)})

    try:
        if input_file == "-" and sys.stdin.isatty():
            log.critical("Input from stdin which is a tty - aborting")
            return 128
        
        with click.open_file(input_file, "r") as f:
            resolved_dtr_schema = json.load(f)

        ## TODO: Add checking of resolved_dtr_schema.
        ##       Is it a JSON Document in the first place.

        dtr_schema = construct_object(resolved_dtr_schema, first_run=True)

        for e in dtr_schema.elements:
            log.info(e.name)
            log.info(e.id)
            log.info(e.type)
            log.info("P:" + e.parent.name)
            if e.child is not None: 
                log.info("C:" + e.child.name)
            if e.elements is not None:
                for new_e in e.elements:
                    log.info("--" + new_e.name)
                    log.info("--" + new_e.id)
                    log.info("--" + new_e.type)
                    log.info("--P:" + new_e.parent.name)
                    if new_e.child is not None:
                        log.info("--C:" + new_e.child.name)
                    if new_e.elements is not None:
                        for new_new_e in new_e.elements:
                            log.info("----" + new_new_e.name)
                            log.info("----" + new_new_e.id)
                            log.info("----" + new_new_e.type)
                            log.info("----P:" + new_new_e.parent.name)
                            if new_new_e.child is not None:
                                log.info("----C:" + new_new_e.child.name)

    except Exception as e:
        log.error(e)
        log.error(traceback.format_exc())
 

@dtr.command("fetch-type")
@click.option(
    "--output-file",
    help="Output file [default: STDOUT]",
    type=click.Path(readable=True, file_okay=True, dir_okay=False),
    default="-",
)
@log_decorator
@time_decorator
@add_log_and_verbose_options
def fetch_dtr_type(
    log_level,
    output_file
):
    """Fetch DTR Type information and output it."""
    log.info("This is fetch-dtr-type")
    log.warning("Not implemented")


if __name__ == "__main__":
    tacos()
