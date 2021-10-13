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


def create_mail(commit_id: str = None) -> None:
  """
  Create a html and text mail body based on commit id

  :param commit_id: github commit id to use for email update
  :return: None
  """
  if not commit_id:
    sys.stderr.write("No commit to examine, exiting")
    sys.exit(1)

  r = requests.get(f"{GITHUB_URL}/{commit_id}",
                   data={"accept": "application/vnd.github.v3+json"})
  if r.status_code != requests.codes.ok:
    sys.stderr.write(f"Can't get commit got HTTP code {r.status_code}: {r.text}\n")
    sys.exit(1)
  body = r.json()
  body_vars = {"author": body['commit']['author']['name'],
               "date": body['commit']['author']['date'],
               "message": body['commit']['message'],
               "commit_url": body['html_url'],
               "sites": [],
               "changes": [] }

  change_size = 0
  sites_changed = set()
  for f in body["files"]:
    site_changes = {}
    try:
      change_size += int(f["changes"])
      site_changes["size"] = int(f["changes"])
    except:
      # don't care about errors here
      pass
    site_changes["name"] = f["filename"]
    site_changes["patch"] = f["patch"]
    body_vars["changes"].append(site_changes)
    instance_dir = f["filename"].split("/")[0]
    sites_changed.add(get_cluster(instance_dir))
  body_vars['change_size'] = change_size
  body_vars['sites'] = list(sites_changed)
  env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath="./templates"))
  text_body = env.get_template('email_template_text.jinja')
  html_body = env.get_template('email_template_html.jinja')
  with open('text_body', 'w') as f:
    f.write(text_body.render(body_vars))
  with open('html_body', 'w') as f:
    f.write(html_body.render(body_vars))


if __name__ == "__main__":
  create_mail(sys.argv[1])
