# insight-client
Appetizer Insight 的 Python 客户端

正在开发：
* 网络上传 log（无需 USB 线）

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

### 注入重写 apk
``` Shell
python3 client.py rewrite username password apk rewrited_apk serialnos
```

例如
``` Shell
python3 client.py rewrite example@mail.com password my.apk my-rewrited.apk phone1,phone2,phone3 
```

注意
* `serialnos` 可以通过 `adb devices` 查询获取
* 非图形化客户端的用户名和密码不支持第三方账号，请在 [Appetizer.io](https://api.appetizer.io/user/register) 注册

### 上传日志获取分析报表
``` Shell
python3 client.py analyze username password pkg_name report_path serialnos
```

例如
``` Shell
python3 client.py analyze example@mail.com password com.my.packagename report.json phone1,phone2,phone3 
```

注意
* `serialnos` 可以通过 `adb devices` 查询获取
* 非图形化客户端的用户名和密码不支持第三方账号，请在 [Appetizer.io](https://api.appetizer.io/user/register) 注册