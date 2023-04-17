# 开发文档

## 流程

### 帖子ID

帖子链接样例：
https://www.caimogu.cc/post/52805.html

帖子ID为52805

### 获取附件

`//div[@class='attachment-container']`

```HTML
<div class="attachment-container">
    <div class="item">
        <div class="info-container">
            <div class="label">附件</div>
            <div class="info">
                <div class="name" title="简易白刀光">简易白刀光</div>
                <div class="point">
                                                    免费
                                                </div>
            </div>
        </div>
        <div class="icon">
            <span class="btn-loading-icon-primary" style="left: 35%;"></span>
            <div class="download active" data-id="37071"></div>
        </div>
    </div>
</div>
```

如上片段，附件ID为37071

附件可能有多个，应遍历多item

### 下载附件

1. 检查附件状态
2. 支付/关注/直接下载（1,2 请求参考API章节）
3. 获取下载链接

> GET https://www.caimogu.cc/post/attachment/37071.html
> 
> 302跳转到网盘地址。如果不是302响应，则说明此附件没买过。

## RESTful API

以下API如未标注，默认header带cookie。应使用session管理连接以便服务器更新cookie。

***

### GET https://www.caimogu.cc/post/attachment/{附件ID}

获取附件状态

**:header:**

x-requested-with: XMLHttpRequest

**:response:**

已经购买/免费

```json
{"status":1,"data":{"id":37071,"name":"简易白刀光","pwd":"9p92","point":0,"download_number":791},"info":""}
```

没买过

```json
{"status":-2,"data":{"point":2},"info":"你还未购买该附件"}
```

***

### POST https://www.caimogu.cc/post/act/buy_attachment

购买附件

**:header:**

content-type: application/x-www-form-urlencoded; charset=UTF-8

**:payload:**

id: {附件ID}

**:response:**

购买成功

```json
{"status":1,"data":[],"info":""}
```

买不起

```json
{"status":999,"data":[],"info":"在踩蘑菇下载附件是需要影响力的，你的影响力不够<br>想要获取影响力可以<a href=\"https:\/\/www.caimogu.cc\/post\/82554.html\" target=\"_blank\">查看影响力获取教程<\/a>"}
```

***

### POST https://www.caimogu.cc/user/act/follow

关注某人

**:header:**

content-type: application/x-www-form-urlencoded; charset=UTF-8
x-requested-with: XMLHttpRequest

**:payload:**

id: {用户ID}
mutual: 0

**:response:**

关注成功

```json
{"status":1,"data":{"status":1,"mutual":0},"info":""}
```