import requests
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

def usage():
    print('insight-client apk-path save-path device-list username password')
    return 1

def main(args):
    if len(args) != 5:
        return usage()
    apk_path, rewrite_path, serialnos, username, password = tuple(args)
    original_name = apk_path.split('/')[-1]
    serialnos = serialnos.split(',')
    pkg = APK(apk_path).get_package()
    DEVICE_LOG = DEVICE_LOG_BASE + pkg + '.log'
    log_zip = pkg + '.log.zip' 
    token = None
    try:
        subprocess.check_call(['adb', 'version'])
    except:
        print('adb not available')
        return 1
    print('0. authenticate with the server')
    r = requests.post(AUTH_BASE + 'api/v1/insight/qiniu_upload_auth', data={'id': username, 'password': password}, verify=False)
    r_json = r.json()
    print(r_json)
    if r.status_code != 200:
        print(r_json['msg'])
        return 1
    token = r_json['token']
    key = r_json['key']

    print('1. upload APK file')
    print('apk_path: ' + apk_path)
    print('pkg: ' + pkg)
    print('upload......')
    ret, info = put_file(token, key, apk_path)
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
    with open(rewrite_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024000):
            f.write(chunk)

    print('4. install rewritten APK')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'uninstall', pkg])
        subprocess.check_call(['adb', '-s', d, 'install', rewritten_path])  # Note: Xiaomi will pop up a dialog

    print('5. prepare permission')
    for d in serialnos:
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.WRITE_EXTERNAL_STORAGE'])
        subprocess.check_call(['adb', '-s', d, 'shell', 'pm', 'grant', pkg, 'android.permission.READ_EXTERNAL_STORAGE'])


    print('6. run tests to get log, input anything to indicate completion')
    if (sys.version_info > (3, 0)):
        input()

    print('7. harvest logs from devices and zip')
    with zipfile.ZipFile(log_zip, 'w') as myzip:
        for d in serialnos:
            subprocess.check_call(['adb', '-s', d, 'pull', DEVICE_LOG, d + '.log'])
            myzip.write(d + '.log')

# To be refactor
'''
    print('8. upload log for analysis')
    with open(log_zip, 'rb') as logs:
        r = requests.post(API_BASE + 'insight/analyze_return_analyzeID', files={'logs': logs}, data={'userID': token, 'pkg': pkg})
        if r.status_code != 200:
            print('ERROR: server returns failure: ' + r.status_code)
            return 1
        print(r.text)
    analyzeID = r.json()['analyzeID']
 
    print('9. download report')
    while True:
        r = requests.get(API_BASE + 'insight/query_analyze_by_analyzeID', params={'analyzeID': analyzeID})
        print(r.text)
        r_json = r.json()
        if r_json['result'] != 'wait':
            break
        print('in processing')
        time.sleep(ANXIETY)
    print(r_json['msg'])
    print(r_json['doc'])
    if r_json['msg'] != 'Success':
        return 1
    download_path = r_json['doc']['outPath']
    print(download_path)
    r = requests.get(API_BASE + download_path, stream=True)
    with open(report_path, 'wb') as report_path:
        shutil.copyfileobj(r.raw, report_path)
    
    print('10. cleanup')
    os.remove(rewritten_path)
    os.remove(log_zip)
    for d in serialnos:
        os.remove(d + '.log')
'''

if __name__ == '__main__':
    main(sys.argv[1:])
