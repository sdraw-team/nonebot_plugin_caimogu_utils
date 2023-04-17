from enum import IntEnum
import aiohttp
import asyncio
from typing import List, Dict
from lxml import etree
import re

from .errorx import UnfollowedError, UnpaidError

CAIMOGU_BASEURL = "https://www.caimogu.cc"
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.39",
           "x-requested-with": "XMLHttpRequest"}


class Caimogu(object):
    """踩蘑菇爬虫实例 管理连接
    """
    def __init__(self, cookies: str) -> None:
        self.cookie = self.load_cookies(cookies)
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)

    def load_cookies(self, cookies: str) -> Dict[str, str]:
        cookie_pairs = {}
        cookie_ = cookies.strip().strip(';').split(';')
        for c in cookie_:
            _c = c.strip().split('=')
            cookie_pairs[_c[0]] = _c[1]
        return cookie_pairs

    def new_session(self, headers=HEADERS):
        return aiohttp.ClientSession(base_url=CAIMOGU_BASEURL,
                                cookies=self.cookie,
                                cookie_jar=self.cookie_jar,
                                headers=headers)
    
class ServiceContext(object):
    def __init__(self, conn: Caimogu, log) -> None:
        self.conn = conn
        self.log = log

class AttachmentStatus(IntEnum):
    unfollowed = -3
    unpaid = -2
    ok = 1

class Attachment(object):
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.attachment_id = id
        self.name = ''
        self.point = -1
        self.status = 0
        self.download_link = ''
        self.pwd = ''
        self.download_number = 0
    
    async def _get_status(self):
        async with self.ctx.conn.new_session() as session:
            async with session.get(f"/post/attachment/{self.attachment_id}", allow_redirects=False) as resp:
                try:
                    reply = await resp.json()
                    self.status = reply['status']
                    if self.status == AttachmentStatus.ok:
                        self.pwd = reply['data']['pwd']
                        self.download_number = int(reply['data']['download_number'])
                except Exception as e:
                    raise RuntimeError("获取附件状态出错: " + str(e))

    async def pay(self) -> None:
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        data = {"id": self.attachment_id}
        
        async with self.ctx.conn.new_session() as session:
            async with session.post("/post/act/buy_attachment", headers=headers, data=data) as resp:
                try:
                    reply = await resp.json()
                    if reply['status'] != 1:
                        raise RuntimeError("未知的返回状态=" + reply.status)
                except Exception as e:
                    raise RuntimeError("购买附件出错: " + str(e))
    
    async def check_status(self) -> str:
        """检查附件状态

        Raises:
            UnfollowedError: 需要关注
            UnpaidError: 需要购买
            RuntimeError: 其他错误
        """
        if self.status == 0 or self.pwd == '' or self.download_number == 0:
            await self._get_status()

        if self.status == AttachmentStatus.unfollowed:
            raise UnfollowedError()
        elif self.status == AttachmentStatus.unpaid:
            raise UnpaidError()
        elif self.status != AttachmentStatus.ok: # 未处理的状态
            raise RuntimeError("无法获取该附件下载链接: 附件状态码=" + str(self.status))

    async def get_download_link(self):
        try:
            await self.check_status()
        except Exception as e:
            return ""
        
        headers = HEADERS.copy()
        headers["x-requested-with"] = ""
        async with self.ctx.conn.new_session(headers=headers) as session:
            async with session.get(f"/post/attachment/{self.attachment_id}.html",
                                   allow_redirects=False) as resp:
                if resp.status != 302:
                    print(await resp.text())
                    return ""
        location = resp.headers.get("location", "")
        return location


class Post(object):
    RE_AUTHOR_ID = re.compile(r"/user/(\d+).html")
    
    def __init__(self, ctx: ServiceContext, post_id: int) -> None:
        self.ctx = ctx
        self.post_id = post_id
        self.page = ""
        self.attachments: List[Attachment] = []
        self.author_id = 0
        
    async def get_page(self) -> str:
        if self.page == "":
            async with self.ctx.conn.new_session() as session:
                async with session.get(f"/post/{self.post_id}.html") as resp:
                    self.page = await resp.text()
        return self.page
        
    async def get_author_id(self) -> int:
        if self.author_id == 0:
            page = await self.get_page()
            root = etree.HTML(page)
            # https://www.caimogu.cc/user/16027.html
            homepage = root.xpath("//div[@class='author-container']/a/@href")[0]
            id_str = self.RE_AUTHOR_ID.findall(homepage)[0]
            self.author_id = int(id_str)
        return self.author_id

    async def get_attachments(self) -> List[Attachment]:
        if len(self.attachments) != 0:
            return self.attachments
        
        page = await self.get_page()

        root = etree.HTML(page)
        # TODO: 细粒度错误处理
        try:
            attachments = root.xpath("//div[@class='attachment-container']/div[@class='item']")
            for a_elem in attachments:
                a = Attachment(ctx=self.ctx)
                a.name = a_elem.xpath("div[@class='info-container']/div[@class='info']/div[@class='name']/text()")[0]
                point_text = a_elem.xpath("div[@class='info-container']/div[@class='info']/div[@class='point']/text()")[0]
                if point_text.find("免费") != -1:
                    a.point = 0
                else:
                    a.point = int(a_elem.xpath("div[@class='info-container']/div[@class='info']/div[@class='point']/span/text()")[0])
                a.attachment_id = int(a_elem.xpath("div[@class='icon']/div[contains(@class,'download')]/@data-id")[0])
                self.attachments.append(a)
        except Exception as e:
            raise RuntimeError("解析页面出错: " + str(e))

        return self.attachments

    async def follow_author(self):
        headers = HEADERS.copy()
        headers['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        data = {'id': self.author_id}
        async with self.ctx.conn.new_session(headers=headers) as session:
            async with session.post('/user/act/follow',data=data) as resp:
                try:
                    reply = await resp.json()
                    if reply['status'] != 1:
                        raise RuntimeError("status=" + str(reply['status']))
                except Exception as e:
                    raise RuntimeError("关注用户失败: " + str(e))

