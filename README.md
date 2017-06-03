# insights.py
Appetizer 质量监控的 Python 客户端

使用流程
* 将待测试的 apk 上传到服务端进行插桩
* 下载插桩后的 apk
* 安装插桩后的应用，授权，进行测试流程（自动化测试，人工测试都可以），log会存在手机本地
* 将设备通过USB连接到开发机，并使用本客户端将 log 上传至服务端进行分析
* 下载分析报告文件（JSON格式，可通过Appetizer Platform > 1.1.0进行简单可视化），报告格式以及样例报告详细见Wiki

插桩和分析包括
* 应用崩溃（Crash）的原因和崩溃时的状态
* 所有线程抛出的异常（即使不会造成崩溃）
* 应用未响应（ANR）的状态
* HTTP 请求以及回复的详细信息，包含以下库的API（更多库支持正在添加）
    - okhttp3
    - retrofit（基于okhttp3的）
    - apache http
    - urlconnection
* 图片加载较长
* CPU 占用率和 heap 占用大小


## 环境要求
* Python 3.3 +
* adb已经安装并已经添加到环境变量PATH中
* 支持Windows, MacOS, Linux
* APK文件名尽量用英文，APP本身状态、字符串等可以有中文

## 用法
### 安装依赖
``` Shell
python3 -m pip install -r requirements.txt
```
### 帮助
``` Shell
python3 insights.py -h
```
确认不会有错误即依赖安装正确

### login: 登录账号
``` Shell
python3 insights.py login username password
```
所有客户端操作均需要登录认证，执行登录后登录用token保存在当前 `.access_token` 文件。token默认60天有效，使用任意操作会自动续期。60天后token过期需要重新登录。

账号可在 [Appetizer.io](https://api.appetizer.io/user/register) 注册。

### 插桩 apk
``` Shell
python3 insights.py process apk processed_apk
```

例如
``` Shell
python3 insights.py process my.apk my_processed.apk 
```

插桩需要上传、处理、下载，需要一定时间，依据网络情况与APK大小不同大致在1分钟-3分钟内，期间会有输出表示进展情况。

### 安装插桩后的APK并授权

``` Shell
python3 insights.py install my_processed.apk serialno1,serialno2
```
其中 `serialno1` 等是设备的串号，通过 `adb devices` 获得，需要安装到多个设备可以用逗号隔开不要有空格，安装后会自动授权log （小米无法自动化授权，建议在安装完成后授权读写SDCARD）


### 测试
Appetizer 质量监控客户端对测试没有特别限制，可以是简单的人工测试，也可以是复杂的回归测试，测试长度不限。插桩后的APK会自动log

### 上传log获取分析报告
``` Shell
python3 insights.py analyze my_processed.apk report_path.zip serialno1,serialno2 --clear
```
* serialno1等是串号同上
* report_path.zip 是分析报告存放的路径，需要文件名，注意这是一个压缩包
* `--clear`是可选参数，用于从设备下载log后将设备上log清空

### 其他功能
``` Shell
python3 insights.py clearlog my_processed.apk serialno1,serialno2 --clear
```
将设备上有指定插桩后的APK的log清除
