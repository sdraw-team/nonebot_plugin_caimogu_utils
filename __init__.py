import re
import nonebot
from nonebot.log import logger
from nonebot import on_command, require
from nonebot.adapters.onebot.v11 import Message, Bot, MessageEvent
from nonebot.rule import Rule
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg
from nonebot.typing import T_State
from pathlib import Path

from .data_source import ServiceContext, Attachment, Post, Caimogu
from .config import Config
from .errorx import UnfollowedError, UnpaidError

caimogu_dl = on_command('踩蘑菇下载', rule=Rule(),
                        aliases={'cmgdl'}, priority=5)

data_path = Path().absolute() / "data" / "caimogu"
config = Config.parse_obj(nonebot.get_driver().config.dict())

conn = Caimogu(config.caimogu_cookies)
ctx = ServiceContext(conn=conn, log=logger)

RE_POST_URL = re.compile(r"www.caimogu.cc/post/(\d+).html")


def parse_post_id_from_url(post_url: str) -> int:
    result = RE_POST_URL.findall(post_url)
    if len(result) == 0:
        return -1
    return int(result[0])


@caimogu_dl.handle()
async def _(matcher: Matcher, event: MessageEvent, state: T_State, arg: Message = CommandArg()):
    if event.message_type not in ['group', 'private']:
        logger.info('不支持的消息类型: {}', event.message_type)
        await matcher.finish()

    # 命令参数处理
    args = arg.extract_plain_text()
    state['args_len'] = len(args)
    if len(args) == 0:
        return

    args = args.split()
    state['url'] = args[0]
    matcher.set_arg('url', Message(args[0]))
    
    # 先简单用第二个参数作为选项，后面选项多了会用ShellCommandArgs，参数多了就取消问答模式，换成命令行参数
    if len(args) >= 2:
        state['choice'] = args[1]
        matcher.set_arg('choice', Message(args[1]))
    return


@caimogu_dl.got('url', prompt='请发送帖子链接')
async def handle_attlist(matcher: Matcher, state: T_State, post_url: Message = Arg('url')):
    if post_url[0].type != 'text':
        await matcher.finish("不支持的消息类型")

    post_id = parse_post_id_from_url(str(post_url[0]))
    if post_id == -1:
        await matcher.finish("解析失败，无效的帖子链接")

    p = Post(ctx, post_id)
    state['post'] = p
    attachments = await p.get_attachments()
    if len(attachments) == 0:
        await matcher.finish("此贴未检测到附件")

    # 已经提供了所需的参数，跳过消息发送
    if 'choice' in state:
        return
    
    message = Message("此贴包含以下附件：\n")
    for i, a in enumerate(attachments):
        price = '免费' if a.point == 0 else str(a.point)
        message.append('{}. {} 价格: {}\n'.format(i+1, a.name, price))
    await matcher.send(message)
    return

@caimogu_dl.got('choice', prompt='发送序号下载，或发送q结束会话')
async def handle_dl(matcher: Matcher, state: T_State, choice_msg: Message = Arg('choice')):
    if choice_msg[0].type != 'text':
        await matcher.finish("不支持的消息类型")

    choice = str(choice_msg[0])
    if choice == 'q':
        await matcher.finish()
    elif choice.isnumeric():
        choice = int(choice)
        p: Post = state['post']
        attachments = await p.get_attachments()
        if choice > len(attachments) or choice <= 0:
            await matcher.reject("序号指定的附件不存在，请重新选择（或输入q结束）")
        
        att = attachments[choice-1]
        try:
            await att.check_status()
        except UnfollowedError:
            await p.follow_author()
            logger.info("关注了用户{}", p.author_id)
        except UnpaidError:
            await att.pay()
            logger.info("花费{}影响力购买了帖子{}下的附件{}({})", att.point, p.post_id, att.attachment_id, att.name)
        except Exception as e:
            logger.error("检查附件{}状态失败: {}",att.attachment_id,str(e))
            await matcher.finish(str(e))
        
        dl_link = await att.get_download_link()
        if dl_link == "":
            logger.error('没有成功获取到下载链接: {}', att.attachment_id)
            matcher.finish("很可惜没有成功获取到下载链接呢，可能是插件内部错误")
        await matcher.finish('附件{}(id={})\n下载链接: {}\n密码: {}'.format(att.name, att.attachment_id, dl_link, att.pwd))
        
    else:
        await matcher.reject("序号选择错误，请重新选择（或输入q结束）")
    