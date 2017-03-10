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

ANXIETY = 1
AUTH_BASE = 'https://api.appetizer.io/'
#AUTH_BASE = 'https://localhost/'
TOKEN_PATH = '.access_token'

DEVICE_LOG_BASE = '/sdcard/io.appetizer/'


def _load_token():
    access_token = ''
    try:
        with open(TOKEN_PATH, 'r') as tokenfile:
            access_token = tokenfile.readline()
            if access_token == '':
                print('empty access_token file, please login')
                return None
    except:
        print('not find access_token file, please login')
        return None
    print('Already login')
    print('access_token: ' + access_token)
    return access_token


def login(args):
    r = requests.post(AUTH_BASE + 'api/v1/oauth/access_token',
        data={
            'grant_type': 'password',
            'username': args.username,
            'password': args.password
        }, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic YXBwZXRpemVyX2NsaWVudDppbnRlcm5hbA=='
        }, verify=False)
    if r.status_code != 200:
        print('User login fail, not exist or password error')
        return 1
    access_token = r.json()['access_token']
    with open(TOKEN_PATH, 'w') as tokenfile:
        tokenfile.write(access_token)
        print('Login success !')
        print('access_token: ' + access_token)

def process(args):
    access_token = _load_token()
    if access_token is None:
        return 1
    authorization = 'Bearer ' + access_token
    original_name = args.apk.split('/')[-1]
    serialnos = args.serialnos.split(',')
    pkg = APK(args.apk).get_package()
    token = None
    try:
        subprocess.check_call(['adb', 'version'])
    except:
        print('adb not available')
        return 1
    print('0. upload apk authenticate with the server')
    r = requests.post(AUTH_BASE + 'api/v1/insight/upload', headers={'Authorization': authorization}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json['msg'])
        return 1
    token = r_json['token']
    key = r_json['key']

    print('1. upload APK file')
    print('apk_path: ' + args.apk)
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
        r = requests.get(AUTH_BASE + 'api/v1/insight/processed_app', headers={'Authorization': authorization}, params={'key': key})
        r_json = r.json()
        if r_json['code'] != 200:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server is downloading the APK')
        elif r_json['state'] == 'rewriting':
            print('waiting...... server is rewriting the APK')
        elif r_json['state'] == 'rewrite_success':
            print('waiting...... server is uploading the rewritten APK')
        elif r_json['state'] == 'server_upload_success':
            print('Success !')
            break
        else:
            print(r_json)
            print('rewrite fail')
            return 1
        time.sleep(ANXIETY)
    download_url = r_json['download_url']
    print(download_url)

    print('3. download rewritten APK')
    r = requests.get(download_url)
    if r.status_code != 200:
        print('download failed')
        return 1
    print('download completed')
    with open(args.processed_apk, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)

    print('4. install rewritten APK')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'uninstall', pkg])
        subprocess.check_call(['adb', '-s', d, 'install', args.processed_apk])  # Note: Xiaomi will pop up a dialog
    print('rewritten APK installed')

    print('5. grant permissions for logging')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.WRITE_EXTERNAL_STORAGE'])
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.READ_EXTERNAL_STORAGE'])
    print('permission granted')
    print('All done! Start testing now')


def analyze(args):
    access_token = _load_token()
    if access_token is None:
        return 1
    authorization = 'Bearer ' + access_token
    log_zip = args.pkg_name + '.log.zip'
    serialnos = args.serialnos.split(',')
    DEVICE_LOG = DEVICE_LOG_BASE + args.pkg_name + '.log'
    token = None
    print('0. harvest and compress device logs')
    with zipfile.ZipFile(log_zip, 'w') as myzip:
        for d in serialnos:
            subprocess.check_call(['adb', '-s', d, 'pull', DEVICE_LOG, d + '.log'])
            myzip.write(d + '.log')

    print('1. authenticate with the server')
    r = requests.post(AUTH_BASE + 'api/v1/insight/analyze', headers={'Authorization': authorization}, data={'pkg_name': args.pkg_name}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json['msg'])
        return 1
    token = r_json['token']
    key = r_json['key']


    print('2. upload log files')
    print('package name: ' + args.pkg_name)
    print('log file: ' + log_zip)
    print('uploading......')
    ret, info = put_file(token, key, log_zip)
    if (ret is None or 'code' not in ret or ret['code'] != 200):
        print('upload error')
        return 1


    print('3. server analyzing')
    r_json = None
    while True:
        r = requests.get(AUTH_BASE + 'api/v1/insight/report', headers={'Authorization': authorization}, params={'key': key})
        r_json = r.json()
        if r_json['code'] != 200:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server is downloading the log')
        elif r_json['state'] == 'analyzing':
            print('waiting...... server is analyzing')
        elif r_json['state'] == 'analyze_success':
            print('waiting...... server is uploading the report')
        elif r_json['state'] == 'server_upload_success':
            print('Success !')
            break
        else:
            print(r_json)
            print('analysis failed')
            return 1
        time.sleep(ANXIETY)
    download_url = r_json['download_url']
    print(download_url)


    print('4. download report')
    r = requests.get(download_url)
    if r.status_code != 200:
        print('download failed')
        return 1
    print('download completeed')
    with open(args.report_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)

    print('5. cleanup')
    os.remove(log_zip)
    for d in serialnos:
        os.remove(d + '.log')

    print('All done! Report file stored at: ' + args.report_path)


def pkgname(args):
    print(APK(args.apk).get_package())



def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help='sub-command help')
    
    login_parser = subparsers.add_parser('login', help='Login by AppetizerIO account, get a token')
    login_parser.add_argument('username', action='store', help='AppetizerIO account username, register at https://www.appetizer.io/')
    login_parser.add_argument('password', action='store', help='AppetizerIO account password')
    login_parser.set_defaults(func=login)

    process_parser = subparsers.add_parser('process', help='Inject appetizer into apk')
    process_parser.add_argument('apk', action='store', help='the path to the APK')
    process_parser.add_argument('processed_apk', action='store', help='the complete path to save the processed APK')
    process_parser.add_argument('serialnos', action='store', help='a list of Android devices to install the rewritten APK, devices identified by their serinal numbers, comma separated')
    process_parser.set_defaults(func=process)

    analyze_parser = subparsers.add_parser('analyze', help='Analyze device logs and generate diagnosis report')
    analyze_parser.add_argument('pkg_name', action='store', help='the package name of the Android app')
    analyze_parser.add_argument('report_path', action='store', help='the path to save the report')
    analyze_parser.add_argument('serialnos', action='store', help='a list of Android devices to install the rewritten APK, devices identified by their serinal numbers, comma separated')
    analyze_parser.set_defaults(func=analyze)

    pkgname_parser = subparsers.add_parser('pkgname', help='Get the package name of an APK file')
    pkgname_parser.add_argument('apk', action='store', help='the path to the APK file')
    pkgname_parser.set_defaults(func=pkgname)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
