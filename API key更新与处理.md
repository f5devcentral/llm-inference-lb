### XInference集群 API key endpoint 示例

每个集群的该API端点都是通过类似如下方式访问：

```
GET /v1/cluster/authorizations
Accept: application/json
```



集群1(假设对应的pool member及端口是192.168.1.132_5001)响应示例：

```json
{
  "code": 200,
  "message": "Success",
  "timestamp": "2025-08-15T14:26:15.000Z",
  "data": {
    "authorization_records": [
      {
        "api_key": "sha256_sk11111",
        "model_ids:":["model-001","model-002"]
      },
      {
        "api_key": "sha256_sk2222",
        "model_ids:":["model-001","model-002"]
      }
    ],
    "count": 2
  }
}
```



集群2（假设对应的pool member及端口是192.168.1.132_5002）响应示例：

```
{
  "code": 200,
  "message": "Success",
  "timestamp": "2025-08-15T14:26:15.000Z",
  "data": {
    "authorization_records": [
      {
        "api_key": "sha256_sk3333",
        "model_ids:":["model-001","model-002"]
      },
      {
        "api_key": "sha256_sk4444",
        "model_ids:":["model-002","model-003"]
      }
    ],
    "count": 2
  }
}
```



### F5 BIG-IP datagroup格式设计:

`model_id_{pool_member_pool_member_port}`:`key1,key2`

`{pool_member_pool_member_port}`为对应pool中的每个具体member的IP地址及端口号

例如上述两个示例集群的API key，在f5 datagroup中可表示为：

```
model-001_192.168.1.132_5001:sha256_sk11111,sha256_sk2222 

model-001_192.168.1.132_5002:sha256_sk3333

model-003_192.168.1.132_5002:sha256_sk4444

model-002_192.168.1.132_5001:sha256_sk11111,sha256_sk2222

model_002_192.168.1.132_5002:sha256_sk3333,sha256_sk4444
```

同一个模型会存在不同的集群中(这里集群即对应于某一个pool member的意思），在同一个集群中同一个模型也会存在多个实例（拥有不同的API key)



### F5 Data group操作方法举例

> 说明：在以下请求中, Common 使用固定值。my-datagroup是具体的F5 data group对象名，值取自scheduler-config.yaml配置文件里的pools.model_APIkey.f5datagroup值。

1. 先查询是否存在某个data group

```
curl -u myf5:nami0518 -k -X GET https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/\~Common\~my-datagroup

如果存在：
{"kind":"tm:ltm:data-group:internal:internalstate","name":"my-datagroup","partition":"Common","fullPath":"/Common/my-datagroup","generation":177,"selfLink":"https://localhost/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup?ver=17.1.2.1","type":"string","records":[{"name":"key2","data":"value2"}]}

如果不存在：
{"code":404,"message":"01020036:3: The requested value list (/Common/my-datagroup2) was not found.","errorStack":[],"apiError":3}
```

2. POST创建新group，并同时创建具体KV内容

```
curl -u admin:admin -k -X POST -H "Content-Type: application/json" -d '{"name":"my-datagroup","partition":"Common","type":"string","records":[{"name":"key1","data":"value1"}]}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal

返回
{"kind":"tm:ltm:data-group:internal:internalstate","name":"my-datagroup","partition":"Common","fullPath":"/Common/my-datagroup","generation":175,"selfLink":"https://localhost/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup?ver=17.1.2.1","type":"string","records":[{"name":"key1","data":"value1"}]}
```

3. PUT全量更新某个datagroup的里整体（所有）records

```
curl -u admin:admin -kX PUT -H "Content-Type: application/json" -d '{"type":"string","records":[{"name":"key1","data":"value1"}]}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup

返回
{"kind":"tm:ltm:data-group:internal:internalstate","name":"my-datagroup","partition":"Common","fullPath":"/Common/my-datagroup","generation":176,"selfLink":"https://localhost/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup?ver=17.1.2.1","type":"string","records":[{"name":"key1","data":"value1"}]}%
```

4. 局部增量增加一个新的KV，需要使用options参数，且options的值需要url编码，下例中的未编码值为`?options=records add { key4 { data value44 } }`

```
curl -u admin:admin -kX PATCH -H "Content-Type: application/json" -d '{"name":"my-datagroup"}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup\?options\=records%20add%20%7b%20key4%20%7b%20data%20value44%20%7d%20%7d


{"kind":"tm:ltm:data-group:internal:internalstate","name":"my-datagroup","partition":"Common","fullPath":"/Common/my-datagroup","generation":15,"selfLink":"https://localhost/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup?options=records+add+%7B+key4+%7B+data+value44+%7D+%7D&ver=17.1.2.1","type":"string","records":[{"name":"key2","data":"value2"},{"name":"key3","data":"value3,value31,value32"},{"name":"key4","data":"value44"}]}
```

5. 局部修改某一个具体的record，需要使用options参数，且options值需要编码，下例中的未编码值为`?options=records modify { key4 { data value44444 } }`

```
curl -u admin:admin -kX PATCH -H "Content-Type: application/json" -d '{"name":"my-datagroup"}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup\?options\=records%20modify%20%7b%20key4%20%7b%20data%20value44444%20%7d%20%7d


{"kind":"tm:ltm:data-group:internal:internalstate","name":"my-datagroup","partition":"Common","fullPath":"/Common/my-datagroup","generation":16,"selfLink":"https://localhost/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup?options=records+modify+%7B+key4+%7B+data+value44444+%7D+%7D&ver=17.1.2.1","type":"string","records":[{"name":"key2","data":"value2"},{"name":"key3","data":"value3,value31,value32"},{"name":"key4","data":"value44444"}]}
```

6. 局部删除某给具体的record，需要使用options参数，且options值需要编码，下例中的未编码值为`?options=records delete { key4 }`

```
curl -u myf5:nami0518 -kX PATCH -H "Content-Type: application/json" -d '{"name":"my-datagroup"}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup\?options\=records%20delete%20%7b%20key4%20%7d


{"kind":"tm:ltm:data-group:internal:internalstate","name":"my-datagroup","partition":"Common","fullPath":"/Common/my-datagroup","generation":17,"selfLink":"https://localhost/mgmt/tm/ltm/data-group/internal/~Common~my-datagroup?options=records+delete+%7B+key4+%7D&ver=17.1.2.1","type":"string","records":[{"name":"key2","data":"value2"},{"name":"key3","data":"value3,value31,value32"}]}
```



7. 其它一些错误返回示例

重复创建datagroup对象：

```
curl -u myf5:nami0518 -ik -X POST -H "Content-Type: application/json" -d '{"name":"my-datagroup","partition":"Common","type":"string","records":[{"name":"key1","data":"value1"}]}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal

HTTP/1.1 409 Conflict
Date: Tue, 16 Sep 2025 04:29:58 GMT
Server: Jetty(9.4.49.v20220914)
Set-Cookie: BIGIPAuthCookie=bo6H2HTIdmm1KZ9ERWwz5qGVNSPY2t9EmZboSJKV; path=/; Secure; HttpOnly; SameSite=Strict
Set-Cookie: BIGIPAuthUsernameCookie=myf5; path=/; Secure; HttpOnly; SameSite=Strict
X-Frame-Options: SAMEORIGIN
Strict-Transport-Security: max-age=16070400; includeSubDomains
Content-Type: application/json;charset=utf-8
Allow:
Pragma: no-cache
Cache-Control: no-store
Cache-Control: no-cache
Cache-Control: must-revalidate
Expires: -1
Content-Length: 149
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'  'unsafe-inline' 'unsafe-eval' data: blob:; img-src 'self' data:  http://127.4.1.1 http://127.4.2.1

{"code":409,"message":"01020066:3: The requested value list (/Common/my-datagroup) already exists in partition Common.","errorStack":[],"apiError":3}
```



删除不存在的data group:

```
curl -u myf5:nami0518 -ikX DELETE https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/\~Common\~my-datagroup2
HTTP/1.1 404 Not Found
Date: Tue, 16 Sep 2025 04:34:11 GMT
Server: Jetty(9.4.49.v20220914)
Set-Cookie: BIGIPAuthCookie=q1s3r4BG0FilypleEDJ8hawvVK1EgbwzDEF8wvz0; path=/; Secure; HttpOnly; SameSite=Strict
Set-Cookie: BIGIPAuthUsernameCookie=myf5; path=/; Secure; HttpOnly; SameSite=Strict
X-Frame-Options: SAMEORIGIN
Strict-Transport-Security: max-age=16070400; includeSubDomains
Content-Type: application/json;charset=utf-8
Allow:
Pragma: no-cache
Cache-Control: no-store
Cache-Control: no-cache
Cache-Control: must-revalidate
Expires: -1
Content-Length: 129
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'  'unsafe-inline' 'unsafe-eval' data: blob:; img-src 'self' data:  http://127.4.1.1 http://127.4.2.1

{"code":404,"message":"01020036:3: The requested value list (/Common/my-datagroup2) was not found.","errorStack":[],"apiError":3}%
```



全量更新不存在的data group:

```
curl -u myf5:nami0518 -ikX PUT -H "Content-Type: application/json" -d '{"type":"string","records":[{"name":"key1","data":"value1"}]}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/\~Common\~my-datagroup2
HTTP/1.1 404 Not Found
Date: Tue, 16 Sep 2025 04:36:12 GMT
Server: Jetty(9.4.49.v20220914)
Set-Cookie: BIGIPAuthCookie=q1s3r4BG0FilypleEDJ8hawvVK1EgbwzDEF8wvz0; path=/; Secure; HttpOnly; SameSite=Strict
Set-Cookie: BIGIPAuthUsernameCookie=myf5; path=/; Secure; HttpOnly; SameSite=Strict
X-Frame-Options: SAMEORIGIN
Strict-Transport-Security: max-age=16070400; includeSubDomains
Content-Type: application/json;charset=utf-8
Allow:
Pragma: no-cache
Cache-Control: no-store
Cache-Control: no-cache
Cache-Control: must-revalidate
Expires: -1
Content-Length: 129
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'  'unsafe-inline' 'unsafe-eval' data: blob:; img-src 'self' data:  http://127.4.1.1 http://127.4.2.1

{"code":404,"message":"01020036:3: The requested value list (/Common/my-datagroup2) was not found.","errorStack":[],"apiError":3}
```



json语法错误:

```
curl -u myf5:nami0518 -ikX PUT -H "Content-Type: application/json" -d '{"type":"string","records":[{"name":"key1","data":"value1"]}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/\~Common\~my-datagroup
HTTP/1.1 400 Bad Request
Date: Tue, 16 Sep 2025 04:38:16 GMT
Server: Jetty(9.4.49.v20220914)
Set-Cookie: BIGIPAuthCookie=q1s3r4BG0FilypleEDJ8hawvVK1EgbwzDEF8wvz0; path=/; Secure; HttpOnly; SameSite=Strict
Set-Cookie: BIGIPAuthUsernameCookie=myf5; path=/; Secure; HttpOnly; SameSite=Strict
X-Frame-Options: SAMEORIGIN
Strict-Transport-Security: max-age=16070400; includeSubDomains
Content-Type: application/json;charset=utf-8
Allow:
Pragma: no-cache
Cache-Control: no-store
Cache-Control: no-cache
Cache-Control: must-revalidate
Expires: -1
Content-Length: 93
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'  'unsafe-inline' 'unsafe-eval' data: blob:; img-src 'self' data:  http://127.4.1.1 http://127.4.2.1
Connection: close

{"code":400,"message":"Found invalid JSON body in the request.","errorStack":[],"apiError":1}%
```



局部新增一个重复的key:

```
curl -u myf5:nami0518 -kX PATCH -H "Content-Type: application/json" -d '{"name":"my-datagroup"}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/\~Common\~my-datagroup\?options\=records%20add%20%7b%20key1%20%7b%20data%20value1%20%7d%20%7d
{"code":409,"message":"01020066:3: The requested class string item (/Common/my-datagroup key1) already exists in partition Common.","errorStack":[],"apiError":3}
```



局部删除一个不存在的key:

```
curl -u myf5:nami0518 -kX PATCH -H "Content-Type: application/json" -d '{"name":"my-datagroup"}' https://f5.f5se.io:8443/mgmt/tm/ltm/data-group/internal/\~Common\~my-datagroup\?options\=records%20delete%20%7b%20key4%20%7d
{"code":404,"message":"01020036:3: The requested class string item (/Common/my-datagroup key4) was not found.","errorStack":[],"apiError":3}
```

