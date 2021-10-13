#Instructions on using gitops automation

## Requirements

The automation here requires a mailgun api key to send out email with the changes.  The
repo with the configurations should have a secret called MAILGUN_API_KEY with the api key.

## Github actions 

Create a github action in the repository that has the configurations.  The 
actions file should be similar to the following:

```yaml
name: SLATE Deployment

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v2
        with:
          fetch-depth: 0

      - name: Pull down automation script
        run: curl -fsSL https://raw.githubusercontent.com/slateci/gitops-automation-script/main/PushUpdates.py -o PushUpdates.py

      - name: Install Python dependencies
        run: pip install -U requests jinja2

      - name: Deploy to SLATE
        id: deploy
        run: |
          BEFORE="${{ github.event.before }}"
          AFTER="${{ github.event.after }}"

          # https://stackoverflow.com/questions/40883798/how-to-get-git-diff-of-the-first-commit
          if [[ $BEFORE = "0000000000000000000000000000000000000000" ]]; then
            BEFORE="4b825dc642cb6eb9a060e54bf8d69288fbee4904"
          fi

          if [[ $AFTER = "0000000000000000000000000000000000000000" ]]; then
            AFTER="4b825dc642cb6eb9a060e54bf8d69288fbee4904"
          fi

          git diff --name-status --pretty="format:" "$BEFORE" "$AFTER" > .changed
          DEBUG="TRUE"
          python3 PushUpdates.py ".changed" "${{ secrets.SLATE_API_TOKEN }}"
          rm .changed
          rm PushUpdates.py

      - name: Commit SLATE Instance ID
        if: ${{ steps.deploy.outputs.push == 'true' }}
        run: |
          git config user.name github-actions
          git config user.email github-actions@github.com
          git add .
          git commit -m "append new SLATE instance ID" --allow-empty
          git push

      - name: Pull down mailgun
        run: curl -fsSL https://raw.githubusercontent.com/slateci/gitops-automation-script/main/mailgun.py -o mailgun.py

      - name: Email Changes
        if: ${{ steps.deploy.outputs.push == 'true' }}
        run: |
          python3 generate_mail_body.py ${{ github.event.after }}
          python3 mailgun.py 
        env:
          MAILGUN_SUBJECT: "SLATE GitOps Change Summary"
          # fill these out appropriately
          MAILGUN_API_KEY: ${{ secrets.MAILGUN_API_KEY }}
          MAILGUN_DOMAIN: slateci.io
          MAILGUN_FROM: "GitOps Notification <noreply@slateci.io>"
          # this can be a comma delimited list
          MAILGUN_SEND_TO: "RECIPIENTS"


```

## Mail script

Copy the `generate_mail_body.py` script and `templates` directory to the repository with the 
configuration files.  Modify the script and templates to match the desired output.  This 
should be sufficient.

## Testing

You can test the scripts by making a change to the configuration file and then pushing the 
changes to github.  This should be sufficient to trigger the action and make sure the 
action is working correctly.
=======
# gitops-automation-script
This repository holds the script used for GitOps-Automation.  

PushUpdates will send out updates to the slate api server.  Note we use the same port as the slate client, 
if the standard ports (443) is used, the nginx proxy will often timeout.  The proxy is only needed if we need
to talk to the api server from sites like TACC that only allow outgoing connections to whitelisted ports (80, 443, etc).


mailgun.py will send out an email using mailgun.  This is used by services like the atlas squid gitops repo in order to 
update admins when changes are made.
