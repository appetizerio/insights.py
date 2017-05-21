#!/usr/bin/env python3
#
# Copyright 2017 AppetizerIO (https://appetizer.io) 
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import requests
import argparse
import sys
import subprocess
import shutil
import time
import zipfile
import os
import codecs
import requests
from apk import APK
from qiniu import put_file, etag
import qiniu.config

if sys.version_info < (3, 0):
    print('Sorry, only Python3+ is supported for now')
    print('Python3 is not new; it was released on Dec. 2008')
    sys.exit(1)

ANXIETY = 5
API_BASE = 'https://api.appetizer.io/'
TOKEN_PATH = os.path.join(os.path.dirname(__file__), '.access_token')
DEVICE_LOG_BASE = '/sdcard/io.appetizer/'


def _load_token():
    access_token = ''
    try:
        with open(TOKEN_PATH, 'r') as tokenfile:
            access_token = tokenfile.readline()
            if access_token == '':
                print('no stored access token, please login')
                return None
    except:
        print('no stored access token, please login')
        return None
    authorization = 'Bearer ' + access_token
    r = requests.get(API_BASE + 'api/v1/oauth/check_token', headers={'Authorization': authorization}, verify=False)
    if r.status_code != 200:
        print(r.json())
        print('stored access token is no longer valid, please login again')
        return None
    print('valid access token: ' + access_token)
    return access_token


def login(args):
    r = requests.post(API_BASE + 'api/v1/oauth/access_token',
        data={
            'grant_type': 'password',
            'username': args.username,
            'password': args.password
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic YXBwZXRpemVyX2NsaWVudDppbnRlcm5hbA=='
        }, verify=False)
    if r.status_code != 200:
        print('Failed to login. User does not exist or bad password')
        return 1
    access_token = r.json()['access_token']
    with open(TOKEN_PATH, 'w') as tokenfile:
        tokenfile.write(access_token)
    print('Login succeeded')
    print('access token: ' + access_token)
    print('access token persisted, subsequent commands will be properly authenticated with this token')
    print('token will be valid for the following 60 days and will get renewed if any command is executed')


def logout(args):
    try:
        with open(TOKEN_PATH, 'w') as tokenfile:
            tokenfile.write('')
    except:
        pass
    print('Bye')


def process(args):
    access_token = _load_token()
    if access_token is None:
        print('Please login to AppetizerIO first')
        return 1
    authorization = 'Bearer ' + access_token
    original_name = os.path.basename(args.apk)
    pkg = APK(args.apk).get_package()
    token = None
    try:
        subprocess.check_call(['adb', 'version'])
    except:
        print('adb not available')
        return 1
    print('0. request for Appetizer Insights quality monitoring module')
    r = requests.post(API_BASE + 'api/v1/insight/upload', headers={'Authorization': authorization}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json['msg'])
        return 1
    token = r_json['token']
    key = r_json['key']

    print('1. upload APK file')
    print('apk: ' + args.apk)
    print('pkg: ' + pkg)
    print('upload......')
    ret, info = put_file(token, key, args.apk)
    print(ret)
    if ret is None or 'code' not in ret or ret['code'] != 200:
        print('upload error')
        return 1

    print('2. wait for the APK to be processed')
    r_json = None
    while True:
        r = requests.get(API_BASE + 'api/v1/insight/processed_app', headers={'Authorization': authorization}, params={'key': key})
        r_json = r.json()
        if r_json['code'] != 200:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server is downloading the APK')
        elif r_json['state'] == 'rewriting':
            print('waiting...... server is processing the APK')
        elif r_json['state'] == 'rewrite_success':
            print('waiting...... server is uploading the processed APK')
        elif r_json['state'] == 'server_upload_success':
            print('server has completed processing the APK')
            break
        else:
            print(r_json)
            print('server fails to process the APK')
            return 1
        time.sleep(ANXIETY)
    download_url = r_json['download_url']
    print(download_url)

    print('3. download processed APK')
    r = requests.get(download_url)
    if r.status_code != 200:
        print('download failed')
        return 1
    print('download completed')
    with open(args.processed_apk, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)


def install(args):
    pkg = APK(args.apk).get_package()
    serialnos = args.serialnos.split(',')
    print('This command is not useful for MIUI devices; please click on the installation popup dialog and manually grant WRITE_EXTERNAL_STROAGE permission')
    print('1. install processed APK')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'uninstall', pkg])
        subprocess.check_call(['adb', '-s', d, 'install', args.apk])  # Note: Xiaomi will pop up a dialog
    print('APK installed')

    print('2. grant permissions for logging')
    for d in serialnos:
        grantWrite = ['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.WRITE_EXTERNAL_STORAGE']
        print(" ".join(grantWrite))
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.WRITE_EXTERNAL_STORAGE'])
        grantRead = ['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.READ_EXTERNAL_STORAGE']
        print(" ".join(grantRead))
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.READ_EXTERNAL_STORAGE'])
    print('permission granted')


def analyze(args):
    access_token = _load_token()
    if access_token is None:
        print('Please login to AppetizerIO first')
        return 1
    authorization = 'Bearer ' + access_token
    pkg = APK(args.apk).get_package()
    log_zip = pkg + '.log.zip'
    serialnos = args.serialnos.split(',')
    DEVICE_LOG = DEVICE_LOG_BASE + pkg + '.log'
    token = None
    print('0. harvest and compress device logs')
    with zipfile.ZipFile(log_zip, 'w') as myzip:
        for d in serialnos:
            subprocess.check_call(['adb', '-s', d, 'pull', DEVICE_LOG, d + '.log'])
            if args.clear:
                subprocess.check_call(['adb', '-s', d, 'shell', 'rm', DEVICE_LOG])
            myzip.write(d + '.log')

    print('1. request analysis from the server')
    r = requests.post(API_BASE + 'api/v1/insight/analyze', headers={'Authorization': authorization}, data={'pkg_name': pkg}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json['msg'])
        return 1
    token = r_json['token']
    key = r_json['key']

    print('2. upload log files')
    print('pkg: ' + pkg)
    print('log file: ' + log_zip)
    print('uploading......')
    ret, info = put_file(token, key, log_zip)
    if (ret is None or 'code' not in ret or ret['code'] != 200):
        print('upload error')
        return 1

    print('3. server analyzing')
    r_json = None
    while True:
        r = requests.get(API_BASE + 'api/v1/insight/report', headers={'Authorization': authorization}, params={'key': key})
        r_json = r.json()
        if r_json['code'] != 200:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server is downloading log')
        elif r_json['state'] == 'analyzing':
            print('waiting...... server is analyzing')
        elif r_json['state'] == 'analyze_success':
            print('waiting...... server is uploading the report')
        elif r_json['state'] == 'server_upload_success':
            print('server has generated and uploaded the report')
            break
        else:
            print(r_json)
            print('server fails to analyze the logs')
            return 1
        time.sleep(ANXIETY)
    download_url = r_json['download_url']
    print(download_url)

    print('4. download report')
    r = requests.get(download_url)
    if r.status_code != 200:
        print('download failed')
        return 1
    print('download completed')
    with open(args.report_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)

    print('5. cleanup')
    os.remove(log_zip)
    for d in serialnos:
        os.remove(d + '.log')

    print('All done! Report file stored at: ' + args.report_path)
    if not args.clear:
        print('Please remember to delete old logs with clearlog command to avoid repeated analysis')


def clearlog(args):
    pkg = APK(args.apk).get_package()
    devices = args.serialnos.split(',')
    DEVICE_LOG = DEVICE_LOG_BASE + pkg + '.log'
    for d in devices:
        subprocess.check_call(['adb', '-s', d, 'shell', 'rm', DEVICE_LOG]) 
    print('done')


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help='all supported commands')
    
    login_parser = subparsers.add_parser('login', help='login to AppetizerIO and cache the access token')
    login_parser.add_argument('username', action='store', help='AppetizerIO account username, register at https://appetizer.io/')
    login_parser.add_argument('password', action='store', help='AppetizerIO account password')
    login_parser.set_defaults(func=login)
    
    logout_parser = subparsers.add_parser('logout', help='logout from AppetizerIO')
    logout_parser.set_defaults(func=logout)

    process_parser = subparsers.add_parser('process', help='upload an APK to add the Appetizer Insight quality monitoring module')
    process_parser.add_argument('apk', action='store', help='the path to the APK file')
    process_parser.add_argument('processed_apk', action='store', help='the complete path to save the processed APK')
    process_parser.set_defaults(func=process)

    analyze_parser = subparsers.add_parser('analyze', help='fetch and analyze device logs and generate diagnosis report')
    analyze_parser.add_argument('apk', action='store', help='the path to the processed APK file')
    analyze_parser.add_argument('report_path', action='store', help='the path to save the report')
    analyze_parser.add_argument('serialnos', action='store', help='a list of Android devices to fetch logs, devices identified by their serial numbers, comma separated')
    analyze_parser.add_argument('--clear', action='store_true', default=False, help='delete the logs from the devices after the analysis')
    analyze_parser.set_defaults(func=analyze)

    clearlog_parser = subparsers.add_parser('clearlog', help='delete the logs generated by a particular APK on the devices')
    clearlog_parser.add_argument('apk', action='store', help='the path to the processed APK file')
    clearlog_parser.add_argument('serialnos', action='store', help='a list of Android devices to fetch logs, devices identified by their serial numbers, comma separated')
    clearlog_parser.set_defaults(func=clearlog)

    install_parser = subparsers.add_parser('install', help='install processed APK and grant necessary permissions')
    install_parser.add_argument('apk', action='store', help='the path to the processed APK file')
    install_parser.add_argument('serialnos', action='store', help='a list of Android devices to install the processed APK, devices identified by their serial numbers, comma separated')
    install_parser.set_defaults(func=install)

    args = parser.parse_args()
    if 'func' not in args:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
else:
    print("this script is inteded as a CLI not a package yet")

