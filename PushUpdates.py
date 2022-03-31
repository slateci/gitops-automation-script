"""
Python script used by Git Actions automation to apply changes to SLATE instances
described by a Git repository.

Originally written by Mitchell Steinman
"""
import os
import sys
import time
import logging
from typing import Optional

import requests

PathToChangedFiles = sys.argv[1]
slateToken = sys.argv[2]

if 'DEBUG' in os.environ and os.environ['DEBUG'] == 'TRUE':
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.DEBUG)


def get_instance_id(cluster: str, app: str, retries: int = None) -> Optional[str]:
    """
    Try to get instance id fo0r a service started at a given slate site

    :param app: application name to query
    :param cluster: slate cluster to query
    :param retries: number of times to retry, defaults to one retry
    :return: instance id or None if id is not available
    """
    logging.debug(f"arguments for query: {cluster}, {app}, {retries}")
    if retries is None:
        current_retries = 1
    else:
        current_retries = retries
    while current_retries > 0:
        uri = "https://api.slateci.io:443/v1alpha3/instances"
        response = requests.post(uri,
                                 params={"token": slateToken, "cluster": cluster},
                                 json={"apiVersion": "v1alpha3", "cluster": cluster})
        logging.debug(response, response.text)
        if response.status_code == 200:
            slate_response = response.json()
            for item in slate_response['items']:
                if item['metadata']['application'] != app:
                    continue
                instance_id = item["metadata"]["id"]
                if instance_id == "":
                    continue
                return instance_id
        logging.error("Didn't get instance id from SLATE response")
        logging.error("Sleeping for 30s before querying SLATE for instance id")
        time.sleep(30)
    return None


def add_instance() -> None:
    """
    Add an instance to slate api server

    :return: None
    """
    try:
        instanceDetails = open(f"{containerName}/instance.yaml", "r").readlines()
    except Exception as e:
        logging.exception("Failed to open instance file for reading: {containerName}/instance.yaml")
        sys.exit(1)

    instanceConfig = {}
    for line in instanceDetails:
        if line.strip() == "":
            continue
        if ":" not in line:
            logging.warning(f"Skipping malformed line {line}")
            continue
        # Parse key value pairs from the instance file into a dict
        instanceConfig.update(
            {line.split(":")[0].strip(): line.split(":")[1].strip()}
        )

    if "instance" in instanceConfig.keys():
        logging.warning("Detected newly added but existing instance...no changes to make")
        sys.exit(1)
    else:
        clusterName = instanceConfig["cluster"]
        groupName = instanceConfig["group"]
        appName = instanceConfig["app"]
        appVersion = ""
        if instanceConfig.get("appVersion"):
            appVersion = instanceConfig["appVersion"]

        valuesString = open(containerName + "/" + "values.yaml", "r").read()
        # Using port 443 goes to the nginx proxy in front of the api server
        # using this in gh actions often results in a timeout,
        # we only need to use the proxy to talk to the api server from
        # facilities like TACC
        # uri = "https://api.slateci.io:443/v1alpha3/apps/" + appName
        uri = "https://api.slateci.io:18080/v1alpha3/apps/" + appName
        logging.debug(f"Contacting {uri}")
        response = requests.post(
            uri,
            params={"token": slateToken},
            json={
                "apiVersion": "v1alpha3",
                "group": groupName,
                "cluster": clusterName,
                "configuration": valuesString,
            },
        )
        logging.debug(f"Got {response}, with output {response.text}")
        if response.status_code == 200:
            response_json = response.json()
            if "metadata" not in response_json or "id" not in response_json["metadata"]:
                logging.warning("Did not get an instance id in response")
                logging.warning("Didn't get instance id from SLATE response")
                logging.warning("Sleeping for 30s before querying SLATE for instance id")
                instance_id = get_instance_id(clusterName, appName, retries=3)
                if instance_id is None:
                    sys.exit(1)
            instance_id = response_json["metadata"]["id"]
            print("parsed id")
            if instance_id == "":
                # try to get the instance from slate after waiting
                logging.warning("Got a blank instance id in response")
                logging.warning("Sleeping for 30s before querying SLATE for instance id")
                time.sleep(30)
                instance_id = get_instance_id(clusterName, appName, retries=3)
                if instance_id is None:
                    sys.exit(1)
            # Open instance.yaml for writing and writeback instance ID
            try:
                instance_file = open(f"{containerName}/instance.yaml", "a")
                instance_file.write(f"\ninstance: {instance_id}")
                instance_file.close()
                logging.info("Wrote instance.yaml")
                # Git add commit push
                sys.stdout.write("::set-output name=push::true\n")
            except IOError:
                logging.exception(f"Failed to update instance file with ID: {containerName}/instance.yaml")
        else:
            logging.error("Encountered error while adding instance")
            logging.error(f"Got a {response.status_code} from the server")
            sys.exit(1)


try:
    ChangedFiles = open(PathToChangedFiles, "r").read().split("\n")
except Exception as e:
    logging.exception(f"Failed to open temp file  {PathToChangedFiles}: {e}")
    sys.exit(1)


for Entry in ChangedFiles:
    logging.info(Entry)
    # Parse entry containing file name and change status
    if Entry == "":
        logging.warning(f"Skipping file {Entry}")
        continue
    # Status: M = Modified, A = Added, D = Removed
    FileStatus = Entry.split()[0]
    FileName = Entry.split()[1]
    # The "container" is any arbitrary path before the slate details
    # 'values.yaml' and 'instance.yaml'
    containerName = FileName.split("/values.yaml")[0]
    # Skip irrelevant files
    if containerName.__contains__("."):
        logging.warning(f"Skipping file {Entry}")
        continue
    if not FileName.__contains__("values.yaml"):
        if FileName.__contains__("instance.yaml"):
            logging.error("Not implemented: Version update")
        else:
            logging.warning(f"Skipping file {Entry}")
            continue

    # Update an instance
    if FileStatus == "M":
        try:
            instanceDetails = open(f"{containerName}/instance.yaml", "r").readlines()
        except Exception:
            logging.exception(f"Failed to open instance file for reading: {containerName}/instance.yaml")
            continue
        instanceConfig = {}
        for line in instanceDetails:
            if line.strip() == "":
                continue
            if not line.__contains__(":"):
                print(
                    "Skipping malformed line", line
                )
                continue
            instanceConfig.update(
                {line.split(": ")[0].strip(): line.split(": ")[1].strip()}
            )
        if not instanceConfig.get("instance"):
            logging.error(f"Failed to find instance ID for {containerName} in {containerName}/instance.yaml")
            logging.warning("Trying to add instance instead...")
            add_instance()
            continue
        appVersion = ""
        if instanceConfig.get("appVersion"):
            appVersion = instanceConfig["appVersion"]
        if "instance" not in instanceConfig or instanceConfig["instance"] == "":
            logging.error(f"Can't find instance in config, skipping: {instanceConfig}")
            logging.warning("Trying to add instance instead...")
            add_instance()
            continue
        instanceID = instanceConfig["instance"]
        valuesString = open(containerName + "/" + "values.yaml", "r").read()
        # Using port 443 goes to the nginx proxy in front of the api server
        # using this in gh actions often results in a timeout,
        # we only need to use the proxy to talk to the api server from
        # facilities like TACC
        # uri = "https://api.slateci.io:443/v1alpha3/instances/" + instanceID + "/update"
        uri = f"https://api.slateci.io:18080/v1alpha3/instances/{instanceID}/update"
        logging.debug(f"Contacting {uri}")
        response = requests.put(
            uri,
            params={"token": slateToken},
            json={"apiVersion": "v1alpha3", "configuration": valuesString},
        )
        logging.debug(f"Got {response} from the server: {response.text}")
        if response.status_code == 200:
            logging.info(f"Successfully updated instance {instanceID}")
            sys.stdout.write("::set-output name=push::true\n")
        else:
            logging.error("Encountered error while adding instance")
            logging.error(f"Got a {response.status_code} from the server")
            logging.error("Processing next entry")
            continue
    # Create a new instance
    elif FileStatus == "A":
        add_instance()
    # Remove an instance
    elif FileStatus == "D":
        logging.warning("Deletion is not implemented. Your instance is still running in SLATE despite file deletion.")
    else:
        logging.error("Error: Invalid file status passed by actions")
        sys.exit(1)
