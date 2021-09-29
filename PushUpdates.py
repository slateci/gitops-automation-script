"""
Python script used by Git Actions automation to apply changes to SLATE instances
described by a Git repository.

Originally written by Mitchell Steinman
"""
import sys
import time
from typing import Optional

import requests

PathToChangedFiles = sys.argv[1]
slateToken = sys.argv[2]


def get_instance_id(cluster: str, app: str, retries: int = None) -> Optional[str]:
    """
    Try to get instance id fo0r a service started at a given slate site

    :param cluster: slate cluster to query
    :param retries: number of times to retry, defaults to one retry
    :return: instance id or None if id is not available
    """
    print(cluster, app, retries)
    if retries is None:
        current_retries = 1
    else:
        current_retries = retries
    while current_retries > 0:
        instance_id = ""
        uri = "https://api.slateci.io:443/v1alpha3/instances"
        response = requests.post(uri,
                                 params={"token": slateToken, "cluster": cluster},
                                 json={"apiVersion": "v1alpha3", "cluster": cluster})
        print(response, response.text)
        if response.status_code == 200:
            slate_response = response.json()
            for item in slate_response['items']:
                if item['metadata']['application'] != app:
                    continue
                instance_id = item["metadata"]["id"]
                if instance_id == "":
                    continue
                return instance_id
        sys.stdout.write("Didn't get instance id from SLATE response\n")
        sys.stdout.write("Sleeping for 30s before querying SLATE for instance id\n")
        time.sleep(30)
    return None

try:
    ChangedFiles = open(PathToChangedFiles, "r").read().split("\n")
except Exception as e:
    sys.stderr.write(f"Failed to open temp file  {PathToChangedFiles}: {e}\n")
    sys.exit(1)


for Entry in ChangedFiles:
    print(Entry, "\n")
    # Parse entry containing file name and change status
    if Entry == "":
        print("Skipping file", Entry, "\n")
        continue
    # Status: M = Modified, A = Added, D = Removed
    FileStatus = Entry.split()[0]
    FileName = Entry.split()[1]
    # The "container" is any arbitrary path before the slate details
    # 'values.yaml' and 'instance.yaml'
    containerName = FileName.split("/values.yaml")[0]
    # Skip irrelevant files
    if containerName.__contains__("."):
        print("Skipping file", Entry, "\n")
        continue
    if not FileName.__contains__("values.yaml"):
        if FileName.__contains__("instance.yaml"):
            print("Not implemented: Version update")
        else:
            print("Skipping file", Entry, "\n")
            continue

    # Update an instance
    if FileStatus == "M":
        try:
            instanceDetails = open(
                containerName + "/" + "instance.yaml", "r"
            ).readlines()
        except Exception as e:
            sys.stderr.write("Failed to open instance file for reading:"
                             f"{containerName}/instance.yaml: {e}\n")
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
            print(
                f"Failed to find instance ID for {containerName} in {containerName}/instance.yaml"
            )
            sys.exit(1)
        appVersion = ""
        if instanceConfig.get("appVersion"):
            appVersion = instanceConfig["appVersion"]
        if "instance" not in instanceConfig or instanceConfig["instance"] =="":
            sys.stderr.write(f"Can't find instance in config, skipping: {instanceConfig}\n")
            continue
        instanceID = instanceConfig["instance"]
        valuesString = open(containerName + "/" + "values.yaml", "r").read()
        # uri = "https://api.slateci.io:443/v1alpha3/instances/" + instanceID + "/update"
        uri = "https://api.slateci.io:18080/v1alpha3/instances/" + instanceID + "/update"
        print(uri)
        response = requests.put(
            uri,
            params={"token": slateToken},
            json={"apiVersion": "v1alpha3", "configuration": valuesString},
        )
        print(response, response.text)
        if response.status_code == 200:
            sys.stdout.write(f"Successfully updated instance {instanceID}\n")
            sys.stdout.write("::set-output name=push::true\n")
        else:
            sys.stderr.write("Encountered error while adding instance\n")
            sys.stderr.write(f"Got a {response.status_code} from the server\n")
            sys.exit(1)
    # Create a new instance
    elif FileStatus == "A":
        try:
            instanceDetails = open(
                containerName + "/" + "instance.yaml", "r"
            ).readlines()
        except Exception as e:
            sys.stderr.write("Failed to open instance file for reading: "
                             f"{containerName}/instance.yaml: {e}\n")
            continue

        instanceConfig = {}
        for line in instanceDetails:
            if line.strip() == "":
                continue
            if ":" not in line:
                print(
                    "Skipping malformed line", line
                )
                continue
            # Parse key value pairs from the instance file into a dict
            instanceConfig.update(
                {line.split(":")[0].strip(): line.split(":")[1].strip()}
            )
        
        if "instance" in instanceConfig.keys():
            print("Detected newly added but existing instance...no changes to make")
            continue
        else:
            clusterName = instanceConfig["cluster"]
            groupName = instanceConfig["group"]
            appName = instanceConfig["app"]
            appVersion = ""
            if instanceConfig.get("appVersion"):
                appVersion = instanceConfig["appVersion"]

            valuesString = open(containerName + "/" + "values.yaml", "r").read()
            # uri = "https://api.slateci.io:443/v1alpha3/apps/" + appName
            uri = "https://api.slateci.io:18080/v1alpha3/apps/" + appName
            print(uri)
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
            print(response, response.text)
            if response.status_code == 200:
                response_json = response.json()
                if "metadata" not in response_json or "id" not in response_json["metadata"]:
                    sys.stderr.write("Did not get an instance id in response\n")
                    sys.stdout.write("Didn't get instance id from SLATE response\n")
                    sys.stdout.write("Sleeping for 30s before querying SLATE for instance id\n")
                    instanceID = get_instance_id(clusterName, appName, retries=3)
                    if instanceID is None:
                        sys.exit(1)
                instanceID = response_json["metadata"]["id"]
                print("parsed id")
                if instanceID == "":
                    # try to get the instance from slate after waiting
                    sys.stderr.write("Got a blank instance id in response\n")
                    sys.stdout.write("Sleeping for 30s before querying SLATE for instance id\n")
                    time.sleep(30)
                    instanceID = get_instance_id(clusterName, appName, retries=3)
                    if instanceID is None:
                        sys.exit(1)
                # Open instance.yaml for writing and writeback instance ID
                try:
                    instanceFile = open(containerName + "/" + "instance.yaml", "a")
                    instanceFile.write("\ninstance: " + instanceID)
                    instanceFile.close()
                    print("wrote instance.yaml")
                    # Git add commit push
                    sys.stdout.write("::set-output name=push::true\n")
                except Exception as e:
                    print(
                        "Failed to open instance file for ID writeback:",
                        containerName + "/" + "instance.yaml",
                        e,
                    )
            else:
                sys.stderr.write("Encountered error while adding instance\n")
                sys.stderr.write(f"Got a {response.status_code} from the server\n")
                sys.exit(1)

    # Remove an instance
    elif FileStatus == "D":
        print(
            "Deletion is not implemented. Your instance is still running in SLATE despite file deletion."
        )
    else:
        sys.stderr.write("Error: Invalid file status passed by actions\n")
        sys.exit(1)
