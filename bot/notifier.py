"""
告警通知: 飞书 / Telegram
"""
from __future__ import annotations
import requests
import json


class Notifier:
    def __init__(self, feishu_webhook: str = "", tg_token: str = "", tg_chat_id: str = ""):
        self.feishu = feishu_webhook
        self.tg_token = tg_token
        self.tg_chat_id = tg_chat_id

    def send(self, title: str, content: str, level: str = "info"):
        """level: info / warn / error"""
        icon = {"info": "INFO", "warn": "WARN", "error": "ERR"}[level]
        msg = f"[{icon}] {title}\n{content}"
        print(msg)
        self._feishu(title, content, level)
        self._telegram(msg)

    def _feishu(self, title: str, content: str, level: str):
        if not self.feishu:
            return
        color = {"info": "blue", "warn": "orange", "error": "red"}[level]
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title},
                           "template": color},
                "elements": [{"tag": "markdown", "content": content}],
            }
        }
        try:
            requests.post(self.feishu, json=payload, timeout=5)
        except Exception as e:
            print(f"[飞书通知失败] {e}")

    def _telegram(self, msg: str):
        if not (self.tg_token and self.tg_chat_id):
            return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.tg_chat_id, "text": msg}, timeout=5)
        except Exception as e:
            print(f"[TG通知失败] {e}")
