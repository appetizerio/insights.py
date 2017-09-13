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
from qiniu import put_file, etag
import qiniu.config
import gzip
import json

ANXIETY = 5
API_BASE = 'https://api.appetizer.io/v2'
TOKEN_PATH = os.path.join(os.path.dirname(__file__), '.access_token')
APKDUMP = os.path.join(os.path.dirname(__file__), 'apkdump.js')
DEVICE_LOG_BASE = '/sdcard/io.appetizer/'
try:
    subprocess.check_output(['node', '-v']); 
except:
    print('Node.js is not installed and some functionality might not work properly')


def version(args):
    print('1.2.2')


def get_apk_manifest(apk):
    return subprocess.check_output(['node', APKDUMP, apk]).decode('utf-8')


def get_apk_package(apk):
    manifest = get_apk_manifest(apk)
    return json.loads(manifest)['package']


def adb(cmd, d=None, showCmd=False):
    dselector = [] if d is None else ['-s', d]
    fullCmd = ['adb'] + dselector + cmd
    if showCmd: print(fullCmd)
    return subprocess.check_call(fullCmd)


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
    r = requests.get(API_BASE + '/oauth/check_token', headers={'Authorization': authorization}, verify=False)
    if r.status_code != 200:
        print(r.json())
        print('stored access token is no longer valid, please login again')
        return None
    print('valid access token: ' + access_token)
    return access_token


def login(args):
    r = requests.post(API_BASE + '/oauth/access_token',
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


def is_fortified(apk, *args, **kwargs):
    with zipfile.ZipFile(apk) as zip_obj:
        solist = [s.rsplit('/')[-1] for s in zip_obj.namelist() if s.endswith('.so')]
	packer = None
	if 'libexecmain.so' in solist and 'libexec.so' in solist:
		packer = 'aijiami'
	elif 'libDexHelper.so' in solist and 'libDexHelper-x86.so' in solist:
		packer = 'bangbang enterprise'
	elif 'libsecmain.so' in solist and 'libsecexe.so' in solist:
		packer = 'bangbang'
	elif 'libtup.so' in solist or 'libexec.so' in solist:
		packer = 'tencent'
	elif ('libprotectClass.so' in solist and 'libprotectClass_x86.so' in solist) or ('libjiagu.so' in solist and 'libjiagu_art.so' in solist) or ('libjiagu.so' in solist and 'libjiagu_x86.so' in solist):
		packer = '360'
	elif 'libbaiduprotect.so' in solist and 'ibbaiduprotect_x86.so' in solist:
		packer = 'baidu'
	elif ('libddog.so' in solist and 'libfdog.so' in solist) or 'libchaosvmp.so' in solist:
		packer = 'najia'
	elif 'libnqshieldx86.so' in solist and 'libnqshield.so' in solist:
		packer = 'netqin'
	elif 'libmobisec.so' in solist or 'libmobisecx.so' in solist:
		packer = 'alibaba'
	elif 'libegis.so' in solist:
		packer = 'tongfudun'
	elif 'libAPKProtect.so' in solist:
		packer = 'apkprotect'
    return packer


def process(args):
    access_token = _load_token()
    if access_token is None:
        print('Please login to AppetizerIO first')
        return 1
    # validate APK file
    try:
        manifest = json.loads(get_apk_manifest(args.apk))
    except:
        print('not a valid APK')
        return 1
    with zipfile.ZipFile(args.apk) as checkf:
        try:
            checkf.getinfo('assets/appetizer.cfg')
            print('input APK is already instrumented')
            return 1
        except:
            pass
    if is_fortified(args.apk) is not None:
        print("the apk is fortified")
        return 1
    if 'android.permission.WRITE_EXTERNAL_STORAGE' not in manifest['usesPermissions']:
        print("the apk does not have READ/WRITE external storage permission")
        return 1

    authorization = 'Bearer ' + access_token
    original_name = os.path.basename(args.apk)
    pkg = get_apk_package(args.apk)
    token = None
    print('0. request Appetizer Insights upload permission')
    r = requests.post(API_BASE + '/insight/process/qiniu', headers={'Authorization': authorization}, verify=False)
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
    if ret is None or 'success' not in ret or ret['success'] != True:
        print('upload error')
        return 1

    print('2. wait for the APK to be processed')
    r_json = None
    while True:
        r = requests.get(API_BASE + '/insight/process', headers={'Authorization': authorization}, params={'key': key})
        r_json = r.json()
        if r_json['success'] != True:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server is downloading the APK')
        elif r_json['state'] == 'rewriting':
            print('waiting...... server is processing the APK')
        elif r_json['state'] == 'rewrite_success' or r_json['state'] == 'server_upload':
            print('waiting...... server is uploading the processed APK')
        elif r_json['state'] == 'server_upload_success':
            print('server has completed processing the APK')
            break
        else:
            print(r_json)
            print('server fails to process the APK')
            return 1
        time.sleep(ANXIETY)
    print(r_json)
    downloadURL = r_json['downloadURL']
    print(downloadURL)

    print('3. download processed APK')
    r = requests.get(downloadURL)
    if r.status_code != 200:
        print('download failed')
        return 1
    print('download completed')
    with open(args.processed_apk, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)


def install(args):
    try:
        adb(['version'])
    except:
        print('adb not available')
        return 1
    pkg = get_apk_package(args.apk)
    serialnos = args.serialnos if len(args.serialnos) > 0 else [None]
    print('This command is not useful for MIUI devices; please click on the installation popup dialog and manually grant WRITE_EXTERNAL_STROAGE permission')
    print('1. install processed APK')
    for d in serialnos:
        adb(['uninstall', pkg], d)
        adb(['install', args.apk], d) # Note: Xiaomi will pop up a dialog
    print('APK installed')

    print('2. grant permissions for logging')
    for d in serialnos:
        adb(['shell', 'pm', 'grant', pkg, 'android.permission.WRITE_EXTERNAL_STORAGE'], d, True)
        adb(['shell', 'pm', 'grant', pkg, 'android.permission.READ_EXTERNAL_STORAGE'], d, True)
    print('permission granted')


def analyze(args):
    try:
        adb(['version'])
    except:
        print('adb not available')
        return 1
    access_token = _load_token()
    if access_token is None:
        print('Please login to AppetizerIO first')
        return 1
    authorization = 'Bearer ' + access_token
    pkg = get_apk_package(args.apk)
    with open('AndroidManifest.json', 'w') as f:
         f.write(get_apk_manifest(args.apk).encode('utf-8'))
    log_zip = pkg + '.log.zip'
    serialnos = args.serialnos if len(args.serialnos) > 0 else [None]
    DEVICE_LOG = DEVICE_LOG_BASE + pkg + '.log'
    token = None
    print('0. harvest and compress device logs')
    with zipfile.ZipFile(log_zip, 'w') as myzip:
        myzip.write('AndroidManifest.json')
        for d in serialnos:
            fname = d if d is not None else "devicelog"
            adb(['pull', DEVICE_LOG, fname + '.log'], d)
            if args.clear:
                adb(['shell', 'rm', DEVICE_LOG], d)
            myzip.write(fname + '.log')
    os.remove('AndroidManifest.json')

    print('1. request analysis from the server')
    r = requests.post(API_BASE + '/insight/analyze/qiniu', headers={'Authorization': authorization}, data={'pkgName': pkg}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json)
        return 1
    token = r_json['token']
    key = r_json['key']

    print('2. upload log files')
    print('pkg: ' + pkg)
    print('log file: ' + log_zip)
    print('uploading......')
    ret, info = put_file(token, key, log_zip)
    if (ret is None or 'success' not in ret or ret['success'] != True):
        print('upload error')
        return 1

    print('3. server analyzing')
    r_json = None
    while True:
        r = requests.get(API_BASE + '/insight/analyze', headers={'Authorization': authorization}, params={'key': key})
        r_json = r.json()
        if r_json['success'] != True:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server is downloading log')
        elif r_json['state'] == 'analyzing':
            print('waiting...... server is analyzing')
        elif r_json['state'] == 'analyze_success' or r_json['state'] == 'server_upload':
            print('waiting...... server is uploading the report')
        elif r_json['state'] == 'server_upload_success':
            print('server has generated and uploaded the report')
            if 'reportExport' in r_json:
                print('exported reports available at:')
                print(r_json['reportExport'])
            break
        else:
            print(r_json)
            print('server fails to analyze the logs')
            return 1
        time.sleep(ANXIETY)

    print('4. cleanup')
    os.remove(log_zip)
    for d in serialnos:
        if d is None:
            os.remove('devicelog.log')
        else:
            os.remove(d + '.log')

    print('All done! You can now view the report via Appetizer Desktop')
    if not args.clear:
        print('Please remember to delete old logs with clearlog command to avoid repeated analysis')


def clearlog(args):
    pkg = get_apk_package(args.apk)
    serialnos = args.serialnos if len(args.serialnos) > 0 else [None]
    DEVICE_LOG = DEVICE_LOG_BASE + pkg + '.log'
    for d in serialnos:
        adb(['shell', 'rm', DEVICE_LOG], d)
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
    analyze_parser.add_argument('-s', dest='serialnos', default=[], action='append', help='device serial number, see adb devices output')
    analyze_parser.add_argument('--clear', action='store_true', default=False, help='delete the logs from the devices after the analysis')
    analyze_parser.set_defaults(func=analyze)

    clearlog_parser = subparsers.add_parser('clearlog', help='delete the logs generated by a particular APK on the devices')
    clearlog_parser.add_argument('apk', action='store', help='the path to the processed APK file')
    clearlog_parser.add_argument('-s', dest='serialnos', default=[], action='append', help='device serial number, see adb devices output')
    clearlog_parser.set_defaults(func=clearlog)

    install_parser = subparsers.add_parser('install', help='install processed APK and grant necessary permissions')
    install_parser.add_argument('apk', action='store', help='the path to the processed APK file')
    install_parser.add_argument('-s','--serialno', dest='serialnos', default=[], action='append', help='device serial number, see adb devices output')
    install_parser.set_defaults(func=install)

    version_parser = subparsers.add_parser('version', help='print version and exit')
    version_parser.set_defaults(func=version)

    args = parser.parse_args()
    if 'func' not in args:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
else:
    print("this script is inteded as a CLI not a package yet")

