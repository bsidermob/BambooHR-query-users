### Description
# This script queries BambooHR directory for newly added Software Engineers and
# Test Analysts and then adds them to Bitbucket and HockeyApp

### TODO:
# 1. Make both query functions use JSON as one of them uses XML at the moment
# 2. Add better error handling
# 3. Grab output from the HockeyApp browser emulation function
# 4. Add sending of Bitbucket invites (it's being done by HR now, I suppose)

import sys
import json
import requests
import pprint
from datetime import date, datetime, timedelta
import xml.etree.cElementTree as ET
import requests_oauthlib
from requests_oauthlib import OAuth2Session, TokenUpdated
from splinter import Browser
from pyvirtualdisplay import Display
from selenium import webdriver

### Global variables

# BambooHR API
bamboohr_url = 'https://api.bamboohr.com/api/gateway.php/FILL_IN_COMPANY_NAME/v1/employees/'
bamboohr_token_file = 'bamboohr_api_token.txt'
days_delta = 7

# Bitbucket API
oauth_key_file = 'oauth_key.txt'
bitbucket_base_api_url = 'https://api.bitbucket.org/1.0/groups/FILL_IN_COMPANY_NAME/developers/members/'
token_url = 'https://bitbucket.org/site/oauth2/access_token'

# HockeyApp
hockeyapp_url = 'https://rink.hockeyapp.net/api/2/'
hockeyapp_token_file = 'hockeyapp_api_token.txt'
hockeyapp_login_pass_file = 'hockeyapp_login_pass.txt'
# This ID is for 'Developers' distribution group
hockeyapp_main_dist_group_id = ''


### Define functions
def load_hockeyapp_token():
    with open(hockeyapp_token_file, 'r') as f:
        # Read the file
        hockeyapp_api_token = f.read().splitlines()
        hockeyapp_api_token  = hockeyapp_api_token[0]
        f.close()
    return hockeyapp_api_token

def load_bamboohr_token():
    with open(bamboohr_token_file, 'r') as f:
        # Read the file
        bamboohr_api_token = f.read().splitlines()
        bamboohr_api_token = bamboohr_api_token[0]
        f.close()
    return bamboohr_api_token

def bitbucket_obtain_token():
    # Load oauth key
    with open(oauth_key_file, 'r') as f:
        # Read the file
        API_TOKEN_BITBUCKET = f.read().splitlines()
        # Split the line in two credentials
        API_TOKEN_BITBUCKET_USER = API_TOKEN_BITBUCKET[0].split(':')[0]
        API_TOKEN_BITBUCKET_SECRET = API_TOKEN_BITBUCKET[0].split(':')[1]
        f.close()
    # Configure headers
    payload = { 'grant_type': 'client_credentials' }
    # The request
    r = requests.post(token_url, auth=(API_TOKEN_BITBUCKET_USER, API_TOKEN_BITBUCKET_SECRET), data=payload)
    # Check if status is ok
    if r.status_code != 200 and "No user with validated email" not in r.content:
        return 'Request threw an error code' + str(r.status_code)
        print r.content
        sys.exit(-1)
    else:
        # Extract token
        access_token = r.json()['access_token']
        return access_token

def hockeyapp_load_credentials(type):
    # Load oauth key
    with open(hockeyapp_login_pass_file, 'r') as f:
        # Read the file
        hockeyapp_login_pass = f.read().splitlines()
        # Split the line in two credentials
        hockeyapp_user = hockeyapp_login_pass[0].split(':')[0]
        hockeyapp_password = hockeyapp_login_pass[0].split(':')[1]
        f.close()
    if type == 'user':
        return hockeyapp_user
    elif type == 'password':
        return hockeyapp_password


def bitbucket_add_user(access_token):
    # Configure headers
    headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer %s" %access_token
              }
    data = {}
    # Add users to developers group
    for email in new_employees_email_list:
        # print email
        # Add user's email to the end of Bitbucket URL
        bitbucket_api_url = bitbucket_base_api_url + email
        #print bitbucket_api_url
        r = requests.put(bitbucket_api_url, headers=headers, json=data)
        if r.status_code != 200 and r.status_code != 409 and "No user with validated email" not in r.content:
            print 'Bitbucket request threw an error code ' + str(r.status_code)
            print r.content
            sys.exit(-1)
        elif r.status_code == 409:
            print 'Bitbucket: ' + r.content
        elif "No user with validated email" in r.content:
            print 'Bitbucket: ' + r.content + ' It means the user hasn\'t created an account in Bitbucket yet.'
        else:
            print 'Bitbucket: ' + email + ' user has been added'

def yesterday_timestamp():
    # Obtain the current date and subtract 7 days from it
    yesterday = datetime.today() - timedelta(days=days_delta)
    yesterday = yesterday.replace(microsecond=0).isoformat() + '%2B02:00'
    return yesterday

# Query API and put the contents into a list
def query_bamboohr_changed(bamboohr_api_token):
    # create a blank list
    new_employees_list = []
    # Configure BambooHR URL
    url = bamboohr_url + 'changed/?since=' + yesterday_timestamp()
    r = requests.get(url, auth=(bamboohr_api_token, 'x'))
    if r.status_code != 200:
        print 'Request threw an error code ' + str(r.status_code)
        sys.exit(-1)
    else:
        data_root = ET.fromstring(r.content)
        # Get a list of newly added employee IDs
        for employee in data_root.findall(".//*[@action='Inserted']"):
            id = employee.get('id')
            new_employees_list.append(id)
        return new_employees_list

def query_bamboohr_directory(bamboohr_api_token):
    # create a blank list
    new_employees_email_list = []
    # Retrive user list from BambooHR corporate directory
    url = bamboohr_url + 'directory/'
    r = requests.get(url, auth=(bamboohr_api_token, 'x'), headers={"Accept": "application/json"})
    if r.status_code != 200:
        print 'Request threw an error code ' + str(r.status_code)
        print r.content
        sys.exit(-1)
    else:
        data_root = json.loads(r.content)
        # Filter the results with new employee list
        for employee in data_root["employees"]:
            if employee["id"] in new_employees_list and type(employee["jobTitle"]) == unicode:
                if "Engineer" in employee["jobTitle"]:
                    print 'Found new employee ' + employee["jobTitle"] + ' ' + employee["workEmail"]
                    new_employees_email_list.append(employee["workEmail"].lower())
                elif "Test" in employee["jobTitle"]:
                    print 'Found new employee ' + employee["jobTitle"] + ' ' + employee["workEmail"]
                    new_employees_email_list.append(employee["workEmail"].lower())
        if len(new_employees_email_list) == 0:
            print 'No new employees added in the last ' + str(days_delta) + ' days. Finishing.'
            quit()
        else:
            return new_employees_email_list

def query_hockeyapp_apps(hockey_app_api_token):
    # create a blank list
    hockeyapp_app_list = []
    url = hockeyapp_url + 'apps'
    # Headers
    headers = { "X-HockeyAppToken": hockey_app_api_token }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print 'Request threw an error code' + str(r.status_code)
        print r.content
        sys.exit(-1)
    else:
        data_root = json.loads(r.content)
        # Get list of all app IDs
        for app in data_root["apps"]:
            print app["id"]
            hockeyapp_app_list.append(app["id"])
        return hockeyapp_app_list

def add_users_to_hockeyapp_app(hockey_app_api_token, app_id):
    ### THIS IS NOT FINISHED YET
    url = hockeyapp_url + 'apps/' + app_id + '/app_users'
    # Headers
    headers = { "X-HockeyAppToken": hockey_app_api_token }
    for user in new_employees_email_list:
        data = {"email": "%s" %user}
        print data
        r = requests.post(url, headers=headers, data=data)
        if r.status_code != 200:
            print 'Request threw an error code' + str(r.status_code)
            print r.content
            sys.exit(-1)
        else:
            print r.content

# This is a dirty workaround as HockeyApp doesn't support adding new users to distribution
# groups through API. It uses just a plain browser emulation.
def add_users_to_hockeyapp_group(user_email, user_password):
    # Initiliase virtual browser
    display = Display(visible=0, size=(1366, 768))
    display.start()
    browser = webdriver.Chrome()
    browser.set_window_size(1366, 768)
    for user in new_employees_email_list:
        with Browser('chrome') as browser:
            # Visit Login page
            url = "https://rink.hockeyapp.net/users/sign_in"
            browser.visit(url)
            browser.find_by_id('user_email').fill(user_email)
            browser.find_by_id('user_password').fill(user_password)
            button = browser.find_by_name('commit')
            button.first.click()
            # Add users
            url = "https://rink.hockeyapp.net/manage/teams/" + hockeyapp_main_dist_group_id + "/team_users/bulk_new"
            browser.visit(url)
            browser.find_by_id('email').fill(user)
            button = browser.find_by_name('commit')
            button.first.click()
            # Print to log
            print 'Hockeyapp: ' + user + ' has been added'


### Start of functions
# Obtain all new employees that were added recently and save them into a list
new_employees_list = query_bamboohr_changed(load_bamboohr_token())
# Get new employees emails from the corporate directory and save them into a list
new_employees_email_list = query_bamboohr_directory(load_bamboohr_token())
# Add user emails to Bitbucket access group
bitbucket_add_user(bitbucket_obtain_token())
# Add users to HockeyApp distribution group with the help of browser emulation
add_users_to_hockeyapp_group(hockeyapp_load_credentials('user'), hockeyapp_load_credentials('password'))
