# insight-client
Appetizer Insight 的 Python 客户端

使用流程
1. 将待测试的 apk 上传到服务端进行注入重写
2. 下载注入重写后的 apk
3. 进行任意的测试流程
4. 将 log 上传至服务端进行分析
5. 下载分析报表

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
* `serialnos` 用于自动安装和授权，不需要的话可以随意填写
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

### 获取 apk 包名
``` Shell
python3 client.py pkgname apk
```

