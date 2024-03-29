
### AMP for Endpoints Delete Stale GUIDs:

Script will query an AMP for Endpoints environment and collect all GUIDs that have not been seen for X days or more. It will write them to a CSV with the Age in days, GUID, and Hostname. The script will then delete stale GUIDs from the environment and write the results to a log file.

Both 

For large environments (50k+ GUIDs) this script may take over 30 minutes to complete.

### Before using you must update ```delete_stale_guids.cfg```:
Authentication parameters:
- client_id 
- api_key

Delete all GUIDs older than this value:
- age_treshold

Choose cloud location. Set to eu for European Union, apjc for Asia Pacific, Japan, and Greater China or leave empty for North America:
- cloud

Add email configuration for sending of log files.
- recipient
- sender_email
- smtp_server

### Usage:
```
python delete_stale_guids.py
```

