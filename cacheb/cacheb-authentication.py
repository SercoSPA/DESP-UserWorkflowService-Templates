#! /usr/bin/env python3

from typing import Annotated
from urllib.parse import parse_qs, urlparse

import requests
from conflator import CLIArg, ConfigModel, Conflator, EnvVar
from lxml import html
from pydantic import Field
import getpass

SERVICE_URL = "https://cacheb.dcms.destine.eu/"


class Config(ConfigModel):
    user: Annotated[
        str | None,
        Field(description="Your DESP username"),
        CLIArg("-u", "--user"),
        EnvVar("USER"),
    ] = None
    password: Annotated[
        str | None,
        Field(description="Your DESP password"),
        CLIArg("-p", "--password"),
        EnvVar("PASSWORD"),
    ] = None
    iam_url: Annotated[
        str,
        Field(description="The URL of the IAM server"),
        CLIArg("--iam-url"),
        EnvVar("IAM_URL"),
    ] = "https://auth.destine.eu"
    iam_realm: Annotated[
        str,
        Field(description="The realm of the IAM server"),
        CLIArg("--iam-realm"),
        EnvVar("REALM"),
    ] = "desp"
    iam_client: Annotated[
        str,
        Field(description="The client ID of the IAM server"),
        CLIArg("--iam-client"),
        EnvVar("CLIENT_ID"),
    ] = "edh-public"


config = Conflator("despauth", Config).load()

if config.user is None:
    user = input("Username: ")
else:
    user = config.user

if config.password is None:
    password = getpass.getpass("Password: ")
else:
    password = config.password


print(f"# Authenticating on {config.iam_url} with user {user}")

with requests.Session() as s:

    # Get the auth url
    response = s.get(
        url=config.iam_url
        + "/realms/"
        + config.iam_realm
        + "/protocol/openid-connect/auth",
        params={
            "client_id": config.iam_client,
            "redirect_uri": SERVICE_URL,
            "scope": "openid offline_access",
            "response_type": "code",
        },
    )
    response.raise_for_status()
    auth_url = html.fromstring(response.content.decode()).forms[0].action

    # Login and get auth code
    login = s.post(
        auth_url,
        data={
            "username": user,
            "password": password,
        },
        allow_redirects=False,
    )

    # We expect a 302, a 200 means we got sent back to the login page and there's probably an error message
    if login.status_code == 200:
        tree = html.fromstring(login.content)
        error_message_element = tree.xpath('//span[@id="input-error"]/text()')
        error_message = (
            error_message_element[0].strip()
            if error_message_element
            else "Error message not found"
        )
        raise Exception(error_message)

    if login.status_code != 302:
        raise Exception("Login failed")

    auth_code = parse_qs(urlparse(login.headers["Location"]).query)["code"][0]

    # Use the auth code to get the token
    response = requests.post(
        config.iam_url
        + "/realms/"
        + config.iam_realm
        + "/protocol/openid-connect/token",
        data={
            "client_id": config.iam_client,
            "redirect_uri": SERVICE_URL,
            "code": auth_code,
            "grant_type": "authorization_code",
            "scope": "",
        },
    )

    if response.status_code != 200:
        raise Exception("Failed to get token")

    # instead of storing the access token, we store the offline_access (kind of "refresh") token
    token = response.json()["refresh_token"]

    print(
        f"""
machine cacheb.dcms.destine.eu
    login anonymous
    password {token}
"""
    )
