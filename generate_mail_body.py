import sys

import requests
import jinja2

GITHUB_URL = "https://api.github.com/repos/slateci/atlas-squid/commits"


def get_cluster(instance_dir: str = None) -> str:
  """
  Get the instance information given a path to the directory

  :param instance_dir: path to directory
  :return:  string with name of cluster
  """
  if not instance_dir:
    return "Unknown Cluster"
  with open(f"{instance_dir}/instance.yaml") as f:
    for line in f:
      if line.strip().startswith('cluster'):
        return line.split(':')[1].strip()
    return instance_dir


def get_git_commit(commit_id: str = None) -> dict:
  """
  Get commit information given a commit
  :param commit_id: sha hash for commit
  :return: dict with json response
  """
  r = requests.get(f"{GITHUB_URL}/{commit_id}",
                   data={"accept": "application/vnd.github.v3+json"})
  if r.status_code != requests.codes.ok:
    sys.stderr.write(f"Can't get commit {commit_id} got HTTP code {r.status_code}: {r.text}\n")
    sys.exit(1)
  body = r.json()
  body_vars = {"author": body['commit']['author']['name'],
               "date": body['commit']['author']['date'],
               "message": body['commit']['message'],
               "commit_url": body['html_url'],
               "sites": [],
               "changes": [],
               "files": body["files"]}
  return body_vars


def get_prior_commit(commit_id: str = None) -> dict:
  """
  Get prior commit message (used when a merge happens)
  :param commit_id: sha hash of merge commit
  :return: dict with json response
  """
  r = requests.get(f"{GITHUB_URL}",
                   data={"accept": "application/vnd.github.v3+json"})
  if r.status_code != requests.codes.ok:
    sys.stderr.write(f"Can't get commits got HTTP code {r.status_code}: {r.text}\n")
    sys.exit(1)
  commits = r.json()
  found_commit = False
  prior_commit = {"message": f"Can't find commit prior to merge commit: {commit_id}",
                  "files": []}
  for commit in commits:
    if commit['sha'] == commit_id:
      found_commit = True
      continue
    if found_commit:
      prior_commit["message"] = commit["commit"]["message"]
      old_commit_info = get_git_commit(commit["sha"])
      prior_commit["files"] = old_commit_info["files"]
  return prior_commit


def create_mail(commit_id: str = None) -> None:
  """
  Create a html and text mail body based on commit id

  :param commit_id: github commit id to use for email update
  :return: None
  """
  if not commit_id:
    sys.stderr.write("No commit to examine, exiting")
    sys.exit(1)

  commit_vars = get_git_commit(commit_id)
  if commit_vars['message'].startswith("Merge branch"):
    prior_commit_info = get_prior_commit(commit_id)
    commit_vars["message"] = prior_commit_info["message"]
    commit_vars["files"] = prior_commit_info["files"]

  change_size = 0
  sites_changed = set()
  for f in commit_vars["files"]:
    if f['filename'].startswith(".") or f['filename'].startswith('templates') or '/' not in f['filename']:
      sys.stdout.write(f"Skipping {f['filename']} since it's not related to a site config\n")
      continue

    site_changes = {}
    try:
      change_size += int(f["changes"])
      site_changes["size"] = int(f["changes"])
    except:
      # don't care about errors here
      pass
    site_changes["name"] = f["filename"]
    site_changes["patch"] = f["patch"]
    commit_vars["changes"].append(site_changes)
    instance_dir = f["filename"].split("/")[0]
    sites_changed.add(get_cluster(instance_dir))
  commit_vars['change_size'] = change_size
  commit_vars['sites'] = list(sites_changed)
  env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath="./templates"))
  text_body = env.get_template('email_template_text.jinja')
  html_body = env.get_template('email_template_html.jinja')
  with open('text_body', 'w') as f:
    f.write(text_body.render(commit_vars))
  with open('html_body', 'w') as f:
    f.write(html_body.render(commit_vars))


if __name__ == "__main__":
  create_mail(sys.argv[1])
