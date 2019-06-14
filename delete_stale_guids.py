from collections import namedtuple
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTPException
import argparse
import configparser
import email
import requests
import smtplib
import sys


def calculate_time_delta(timestamp):
    '''Calculate how long it has been since the GUID was last seen
    '''
    time_format = '%Y-%m-%dT%H:%M:%SZ'
    datetime_object = datetime.strptime(timestamp, time_format)
    age = (datetime.utcnow() - datetime_object).days
    return age

def should_delete(age, threshold):
    '''Check if the GUID age is greater than the configured threshold
    '''
    if age > threshold:
        return True
    return False

def process_guid_json(guid_json):
    '''Process the individual GUID entry
    '''
    computer = namedtuple('computer', ['hostname', 'guid', 'age'])
    connector_guid = guid_json.get('connector_guid')
    hostname = guid_json.get('hostname')
    last_seen = guid_json.get('last_seen')
    age = calculate_time_delta(last_seen)
    return computer(hostname, connector_guid, age)

def process_response_json(json, age_threshold):
    '''Process the decoded JSON blob from /computers
    '''
    computers_to_delete = set()
    for entry in json['data']:
        computer = process_guid_json(entry)
        if should_delete(computer.age, age_threshold):
            computers_to_delete.add(computer)
    return computers_to_delete

def delete_guid(session, guid, hostname, computers_url):
    '''Delete the supplied GUID
    '''
    url = computers_url + '{}'.format(guid)
    response = session.delete(url)
    response_json = response.json()
    now = datetime.now()
    daytime_string = now.strftime("%Y-%m-%d %H:%M:%S")
    with open('deletion-log.txt', 'a+', encoding='utf-8') as file_output:
        if response.status_code == 200 and response_json['data']['deleted']:
            file_output.write(daytime_string + ' - Succesfully deleted: {}'.format(hostname) + '\n')
        else:
            file_output.write(daytime_string + ' - Something went wrong deleting: {}'.format(hostname) + '\n')

def get(session, url):
    '''HTTP GET the URL and return the decoded JSON
    '''
    response = session.get(url)
    response_json = response.json()
    return response_json

def send_report(recipient, sender_email, smtp_server):
    '''Send email with the created log files as attachments
    '''
    subject = 'Delete stale GUIDs report'
    body = 'Log files from script "delete_stale_guids.py"'
    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient
    message["Subject"] = subject
    #message["Bcc"] = receiver_email  # Recommended for mass emails

    # Add body to email
    message.attach(MIMEText(body, "plain"))

    files = ['stale_guids.csv', 'deletion-log.txt']

    for a_file in files:
        attachment = open(a_file, 'rb')
        part = MIMEBase('application','octet-stream')
        part.set_payload(attachment.read())
        part.add_header('Content-Disposition',
                    'attachment',
                    filename=a_file)
        encoders.encode_base64(part)
        message.attach(part)

    #sends email
    try:
        smtpObj = smtplib.SMTP(smtp_server)
        smtpObj.sendmail(sender_email, recipient, message.as_string())

    except SMTPException:
        pass

def main():
    '''The main logic of the script
    '''
    # Check arguments
    ## parser = argparse.ArgumentParser()
    ## parser

    # Specify the config file
    config_file = 'delete_stale_guids.cfg'

    # Reading the config file to get settings
    config = configparser.RawConfigParser()
    config.read(config_file)
    client_id = config.get('AMPE', 'client_id')
    api_key = config.get('AMPE', 'api_key')
    age_threshold = int(config.get('AMPE', 'age_threshold'))
    cloud = config.get('AMPE', 'cloud')
    recipient = config.get('AMPE', 'recipient')
    sender_email = config.get('AMPE', 'sender_email')
    smtp_server = config.get('AMPE', 'smtp_server')

    # Instantiate requestions session object
    amp_session = requests.session()
    amp_session.auth = (client_id, api_key)

    # Set to store the computer tuples in
    computers_to_delete = set()

    # URL to query AMP
    cloud = config.get('AMPE', 'cloud')

    if cloud == '':
        computers_url = 'https://api.amp.cisco.com/v1/computers/'
    else:
        computers_url = 'https://api.' + cloud + '.amp.cisco.com/v1/computers/'

    # Query the API
    response_json = get(amp_session, computers_url)

    # Process the returned JSON
    initial_batch = process_response_json(response_json, age_threshold)

    # Store the returned stale GUIDs
    computers_to_delete = computers_to_delete.union(initial_batch)

    # Check if there are more pages and repeat
    while 'next' in response_json['metadata']['links']:
        next_url = response_json['metadata']['links']['next']
        response_json = get(amp_session, next_url)
        next_batch = process_response_json(response_json, age_threshold)
        computers_to_delete = computers_to_delete.union(next_batch)

    if computers_to_delete:
        with open('stale_guids.csv', 'w', encoding='utf-8') as file_output:
            file_output.write('Age in days,GUID,Hostname\n')
            for computer in computers_to_delete:
                file_output.write('{},{},{}\n'.format(computer.age,
                                                      computer.guid,
                                                      computer.hostname))
        # Delete GUIDs
        for computer in computers_to_delete:
            delete_guid(amp_session, computer.guid, computer.hostname, computers_url)

    send_report(recipient, sender_email, smtp_server)        


if __name__ == "__main__":
    main()
