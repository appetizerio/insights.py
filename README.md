# insight-client
Appetizer Insight 的 Python 客户端

使用流程
* 将待测试的 apk 上传到服务端进行注入重写
* 下载注入重写后的 apk
* 进行任意的测试流程
* 将 log 上传至服务端进行分析
* 下载分析报表

分析功能包括
* 应用崩溃（Crash）的原因和崩溃时的状态
* 所有线程抛出的异常（即使不会造成崩溃）
* 应用未响应（ANR）的状态
* HTTP 请求的时长，包含以下库的API（更多库支持正在添加）
    - okhttp
    - retrofit
    - apache http
    - urlconnection
* 图片加载时长
* CPU 占用率和 heap 占用大小
* 弱网络模拟（正在开发）


## 要求
* Python 3.3 +
* adb

## 用法
### 安装
``` Shell
python3 -m pip install -r requirements.txt
```
### 帮助
``` Shell
python3 client.py -h
```

### login: 登录账号
``` Shell
python3 client.py login username password
```
执行 `processe` 和 `analyze` 操作均需要登录认证，执行登录后会在当年目录保存 `.access_token` 文件。

账号可在 [Appetizer.io](https://api.appetizer.io/user/register) 注册。

### process: 注入重写 apk
``` Shell
python3 client.py process apk processed_apk serialnos
```

例如
``` Shell
python3 client.py process my.apk my_processed.apk phone1,phone2,phone3 
```

注意
* `serialnos` 用于自动安装和授权，不需要的话可以随意填写
* `serialnos` 可以通过 `adb devices` 查询获取

### analyze: 上传日志获取分析报表
``` Shell
python3 client.py analyze pkg_name report_path serialnos
```

例如
``` Shell
python3 client.py analyze com.my.packagename report.json phone1,phone2,phone3 
```

注意
* `serialnos` 可以通过 `adb devices` 查询获取
* `pkgname` 可以获取应用包名

### pkgname: 获取 apk 包名
``` Shell
python3 client.py pkgname apk
```

