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
DEVICE_LOG_BASE = '/sdcard/io.appetizer/'


def rewrite(args):
    original_name = args.apk.split('/')[-1]
    serialnos = args.serialnos.split(',')
    pkg = APK(args.apk).get_package()
    token = None
    try:
        subprocess.check_call(['adb', 'version'])
    except:
        print('adb not available')
        return 1
    print('0. authenticate with the server')
    r = requests.post(AUTH_BASE + 'api/v1/insight/qiniu_rewrite_upload_auth', data={'id': args.username, 'password': args.password}, verify=False)
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
    if (ret is None or 'code' not in ret or ret['code'] != 200):
        print('upload error')
        return 1

    print('2. wait for the APK to be processed')
    r_json = None
    while True:
        r = requests.get(AUTH_BASE + 'api/v1/insight/client_query_rewrite_state', params={'key': key})
        r_json = r.json()
        if r_json['code'] != 200:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server download apk')
        elif r_json['state'] == 'rewriting':
            print('waiting...... server rewriting apk')
        elif r_json['state'] == 'rewrite_success':
            print('waiting...... server uploading apk')
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
        print('download fail')
        return 1
    print('download complete')
    with open(args.rewrited_apk, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)

    print('4. install rewritten APK')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'uninstall', pkg])
        subprocess.check_call(['adb', '-s', d, 'install', args.rewrited_apk])  # Note: Xiaomi will pop up a dialog

    print('5. prepare permission')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.WRITE_EXTERNAL_STORAGE'])
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.READ_EXTERNAL_STORAGE'])


def analyze(args):
    log_zip = args.pkg_name + '.log.zip'
    serialnos = args.serialnos.split(',')
    DEVICE_LOG = DEVICE_LOG_BASE + args.pkg_name + '.log'
    token = None
    print('0. harvest logs from devices and zip')
    with zipfile.ZipFile(log_zip, 'w') as myzip:
        for d in serialnos:
            subprocess.check_call(['adb', '-s', d, 'pull', DEVICE_LOG, d + '.log'])
            myzip.write(d + '.log')

    print('1. authenticate with the server')
    r = requests.post(AUTH_BASE + 'api/v1/insight/qiniu_analyze_upload_auth', data={'id': args.username, 'password': args.password, 'pkg_name': args.pkg_name}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json['msg'])
        return 1
    token = r_json['token']
    key = r_json['key']


    print('2. upload log zip file')
    print('pkg: ' + args.pkg_name)
    print('zip file: ' + log_zip)
    print('upload......')
    ret, info = put_file(token, key, log_zip)
    if (ret is None or 'code' not in ret or ret['code'] != 200):
        print('upload error')
        return 1


    print('3. wait for analyze to be processed')
    r_json = None
    while True:
        r = requests.get(AUTH_BASE + 'api/v1/insight/client_query_analyze_state', params={'key': key})
        r_json = r.json()
        if r_json['code'] != 200:
            print(r_json)
            return 1
        if r_json['state'] == 'return_upload_auth' or r_json['state'] == 'upload_finish' or r_json['state'] == 'server_download':
            print('waiting...... server download log')
        elif r_json['state'] == 'analyzing':
            print('waiting...... server analyzing report')
        elif r_json['state'] == 'analyze_success':
            print('waiting...... server uploading report')
        elif r_json['state'] == 'server_upload_success':
            print('Success !')
            break
        else:
            print(r_json)
            print('analyze fail')
            return 1
        time.sleep(ANXIETY)
    download_url = r_json['download_url']
    print(download_url)


    print('4. download insight report')
    r = requests.get(download_url)
    if r.status_code != 200:
        print('download fail')
        return 1
    print('download complete')
    with open(args.report_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)

    print('5. cleanup')
    os.remove(log_zip)
    for d in serialnos:
        os.remove(d + '.log')


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help='sub-command help')
    
    rewrite_parser = subparsers.add_parser('rewrite', help='Inject appetizer into apk')
    rewrite_parser.add_argument('username', action='store', help='Appetizer.io account username, register from https://appetizer.io/')
    rewrite_parser.add_argument('password', action='store', help='Appetizer.io account password')
    rewrite_parser.add_argument('apk', action='store', help='the path of apk to be rewrited')
    rewrite_parser.add_argument('rewrited_apk', action='store', help='the path and file name for rewrited apk save to')
    rewrite_parser.add_argument('serialnos', action='store', help='android devices\' serinal number, multi devices split with comma')
    rewrite_parser.set_defaults(func=rewrite)

    analyze_parser = subparsers.add_parser('analyze', help='Analyze log from devices')
    analyze_parser.add_argument('username', action='store', help='Appetizer.io account username, register from https://appetizer.io/')
    analyze_parser.add_argument('password', action='store', help='Appetizer.io account password')
    analyze_parser.add_argument('pkg_name', action='store', help='the android application package name')
    analyze_parser.add_argument('report_path', action='store', help='the path for report.json save to')
    analyze_parser.add_argument('serialnos', action='store', help='android devices\' serinal number, multi devices split with comma')
    analyze_parser.set_defaults(func=analyze)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()