"""
Python script used by Git Actions automation to apply changes to SLATE instances
described by a Git repository.

Originally written by Mitchell Steinman
"""
import sys

import requests

PathToChangedFiles = sys.argv[1]
slateToken = sys.argv[2]

try:
    ChangedFiles = open(PathToChangedFiles, "r").read().split("\n")
except Exception as e:
    sys.stderr.write(f"Failed to open temp file  {PathToChangedFiles}: {e}")
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
                "Failed to find instance ID for:", containerName + "/" + "values.yaml"
            )
        appVersion = ""
        if instanceConfig.get("appVersion"):
            appVersion = instanceConfig["appVersion"]
        if "instance" not in instanceConfig or instanceConfig["instance"] =="":
            sys.stderr.write(f"Can't find instance in config, skipping: {instanceConfig}\n")
            continue
        instanceID = instanceConfig["instance"]
        valuesString = open(containerName + "/" + "values.yaml", "r").read()
        uri = "https://api.slateci.io:443/v1alpha3/instances/" + instanceID + "/update"
        print(uri)
        response = requests.put(
            uri,
            params={"token": slateToken},
            json={"apiVersion": "v1alpha3", "configuration": valuesString},
        )
        print(response, response.text)
        if response.status_code == 200:
            sys.stdout.write(f"Successfully updated instance {instanceID}")
        else:
            sys.stderr.write("Encountered error while adding instance\n")
            sys.stderr.write(f"Got a {response.status_code} from the server")
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
            uri = "https://api.slateci.io:443/v1alpha3/apps/" + appName
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
                    sys.exit(1)
                instanceID = response.json()["metadata"]["id"]
                if instanceID == "":
                    sys.stderr.write("Got a blank instance id in response\n")
                    sys.exit(1)
                # Open instance.yaml for writing and writeback instance ID
                try:
                    instanceFile = open(containerName + "/" + "instance.yaml", "a")
                    instanceFile.write("\ninstance: " + instanceID)
                    # Git add commit push
                    print("::set-output name=push::true")
                except Exception as e:
                    print(
                        "Failed to open instance file for ID writeback:",
                        containerName + "/" + "instance.yaml",
                        e,
                    )
            else:
                sys.stderr.write("Encountered error while adding instance\n")
                sys.stderr.write(f"Got a {response.status_code} from the server")
                sys.exit(1)

    # Remove an instance
    elif FileStatus == "D":
        print(
            "Deletion is not implemented. Your instance is still running in SLATE despite file deletion."
        )
    else:
        sys.stderr.write("Error: Invalid file status passed by actions\n")
        sys.exit(1)
