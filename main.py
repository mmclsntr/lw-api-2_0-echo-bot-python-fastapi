import os
import json
import uuid
import time
import sys

from logging import getLogger, StreamHandler, INFO

from requests.structures import CaseInsensitiveDict
from requests.exceptions import RequestException

from fastapi import FastAPI, Request

import lineworks

BASE_API_URL = "https://www.worksapis.com/v1.0"
BASE_AUTH_URL = "https://auth.worksmobile.com/oauth2/v2.0"
SCOPE = "bot"


global_data = {}
RETRY_COUNT_MAX = 5

app = FastAPI()
logger = getLogger(__name__)
handler = StreamHandler(sys.stdout)
handler.setLevel(INFO)
logger.addHandler(handler)
logger.setLevel(INFO)

@app.post("/callback")
async def chat_2_0(request: Request):
    body_raw = await request.body()
    body_json = await request.json()
    headers = CaseInsensitiveDict(request.headers)

    logger.info(body_json)
    logger.info(headers)

    bot_id = headers.get("x-works-botid")
    signature = headers.get("x-works-signature")

    # Load parameters
    bot_id = os.environ.get("LW_API_BOT_ID")
    bot_secret = os.environ.get("LW_API_BOT_SECRET")
    client_id = os.environ.get("LW_API_CLIENT_ID")
    client_secret = os.environ.get("LW_API_CLIENT_SECRET")
    service_account_id = os.environ.get("LW_API_SERVICE_ACCOUNT")
    privatekey = os.environ.get("LW_API_PRIVATEKEY")

    # validation
    signature = headers.get("x-works-signature")
    if not lineworks.validate_request(body_raw, signature, bot_secret):
        logger.warn("Invalid request")
        return

    user_id = body_json["source"]["userId"]
    content = body_json["content"]

    if content["type"] == "text":
        txt = content["text"]
        res_content = {
            "content": {
                "type": "text",
                "text": txt
            }
        }

    else:
        res_content = {
            "content": {
                "type": "text",
                "text": "Please send a text."
            }
        }

    if "access_token" not in global_data:
        # Get Access Token
        logger.info("Get access token")
        res = lineworks.get_access_token(client_id,
                                         client_secret,
                                         service_account_id,
                                         privatekey,
                                         SCOPE)
        global_data["access_token"] = res["access_token"]

    logger.info("reply")
    logger.info(res_content)
    for i in range(RETRY_COUNT_MAX):
        try:
            # Reply
            res = lineworks.send_message_to_user(res_content,
                                                 bot_id,
                                                 user_id,
                                                 global_data["access_token"])
        except RequestException as e:
            print(e.__dict__)
            body = e.response.json()
            status_code = e.response.status_code
            if status_code == 403:
                if body["code"] == "UNAUTHORIZED":
                    # Update Access Token
                    logger.info("Update access token")
                    res = lineworks.get_access_token(client_id,
                                                     client_secret,
                                                     service_account_id,
                                                     privatekey,
                                                     SCOPE)
                    global_data["access_token"] = res["access_token"]
                else:
                    logger.exception(e)
                    break
            elif status_code == 429:
                # Over rate limit
                logger.info("Over rate limit")
                logger.info(body)
            else:
                logger.exception(e)
                break

            time.sleep(2 ** i)
        else:
            break

    return {}
