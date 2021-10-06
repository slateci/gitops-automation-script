# gitops-automation-script
This repository holds the script used for GitOps-Automation.  

PushUpdates will send out updates to the slate api server.  Note we use the same port as the slate client, 
if the standard ports (443) is used, the nginx proxy will often timeout.  The proxy is only needed if we need
to talk to the api server from sites like TACC that only allow outgoing connections to whitelisted ports (80, 443, etc).


mailgun.py will send out an email using mailgun.  This is used by services like the atlas squid gitops repo in order to 
update admins when changes are made.
