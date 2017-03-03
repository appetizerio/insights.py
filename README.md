# insight-client
Appetizer Insight 的 Python 客户端

正在开发：
* 自动化上传 log 下载分析报表
* 网络上传 log（无需 USB 线）

## 要求
* Python 3.3 +
* adb

## 用法
``` Shell
python3 -m pip install -r requirements.txt
```

```
python3 client.py apk_path save_path device-list username password
```

例如
```
python3 client.py origin.apk rewrite.apk phone1,phone2,phone3 example@qq.com password
```

注意
* `device-list` 可以通过 `adb devices` 查询获取
* 非图形化客户端的用户名和密码不支持第三方账号，请在 [Appetizer.io](https://api.appetizer.io/user/register) 注册