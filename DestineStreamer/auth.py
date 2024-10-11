from base64 import b64decode
import json
import os
import argparse

from datetime import datetime
import requests
from lxml import html
from urllib.parse import urlparse
from urllib.parse import parse_qs
import jwt
from pydantic_settings import BaseSettings, SettingsConfigDict
import getpass

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
print(CURRENT_DIR)
SCRIPTS_DIR = os.path.dirname(CURRENT_DIR)
PREFIX = os.path.dirname(SCRIPTS_DIR)

username = input('Type your username: ')
password = getpass.getpass('Type your password: ')

class Settings(BaseSettings):
    #AUTH
    KEYCLOAK_URL: str = "https://auth.destine.eu/"
    KEYCLOAK_REALM: str = "desp"

    KEYCLOAK_REDIRECT_URL: str = "https://streamer.destine.eu/api/v1/authentication/callback"
    KEYCLOAK_CLIENTID: str = "streaming-fe"

    KEYCLOAK_USERNAME: str = username
    KEYCLOAK_PASSWORD: str = password

    model_config = SettingsConfigDict(env_file=os.path.join(PREFIX, ".env"), extra="allow")


from jwt import PyJWKClient


class Auth():
    def __init__(self) -> None:
        self.get_params = {
            "client_id": s.KEYCLOAK_CLIENTID,
            "redirect_uri": s.KEYCLOAK_REDIRECT_URL,
            "scope": "openid",
            "response_type": "code"
        }
        self.post_data = {
            "username": s.KEYCLOAK_USERNAME,
            "password": s.KEYCLOAK_PASSWORD
        }

    def get_token(self):
        access_token = None
        try:
            session = requests.Session()
            # get auth_url - form action
            auth_url = html.fromstring(
                session.get(
                    url=s.KEYCLOAK_AUTH, params=self.get_params
                ).content.decode()).forms[0].action
            # get authorization code
            code = parse_qs(urlparse(
                session.post(
                    auth_url,
                    data=self.post_data, allow_redirects=False).headers['Location']
            ).query)['code'][0]
            # get access token
            data = {
                "client_id": s.KEYCLOAK_CLIENTID,
                "redirect_uri": s.KEYCLOAK_REDIRECT_URL,
                "code": code,
                "grant_type": "authorization_code"
            }
            tokens = session.post(
                s.KEYCLOAK_TOKEN,
                data=data
            ).json()
            access_token = tokens['access_token']
            refresh_token = tokens['refresh_token']

            decoded_access_token = jwt.decode(
                access_token,
                self.getKey(access_token),
                algorithms=["RS256"]
            )
        except Exception as e:
            raise RuntimeError("Token request Failed")
        return access_token, decoded_access_token, refresh_token

    def getKey(self, access_token:str):
        json_certs = requests.get(s.KEYCLOAK_JWKS_URL).json().get("keys")
        public_keys = {}
        for jwk in json_certs:
            kid = jwk['kid']
            public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        kid = jwt.get_unverified_header(access_token)['kid']
        return public_keys[kid]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Get token from desp iam.'
    )

    default_settings = Settings()

    parser.add_argument(
        "--KEYCLOAK_URL", "-url",
        required=False,
        type=str,
        default=default_settings.KEYCLOAK_URL,
        help=f"Iam endpoint [{default_settings.KEYCLOAK_URL}]"
    )

    parser.add_argument(
        "--KEYCLOAK_REALM", "-realm",
        required=False,
        type=str,
        default=default_settings.KEYCLOAK_REALM,
        help=f"Iam realm [{default_settings.KEYCLOAK_REALM}]"
    )

    parser.add_argument(
        "--KEYCLOAK_REDIRECT_URL", "-r",
        required=False,
        type=str,
        default=default_settings.KEYCLOAK_REDIRECT_URL,
        help=f"Public client redirect uri [{default_settings.KEYCLOAK_REDIRECT_URL}]"
    )

    parser.add_argument(
        "--KEYCLOAK_CLIENTID", "-id",
        required=False,
        type=str,
        default=default_settings.KEYCLOAK_CLIENTID,
        help=f"Public client ID [{default_settings.KEYCLOAK_CLIENTID}]"
    )

    parser.add_argument(
        "--KEYCLOAK_USERNAME", "-u",
        required=False,
        type=str,
        default=default_settings.KEYCLOAK_USERNAME,
        help=f"Username [{default_settings.KEYCLOAK_USERNAME}]"
    )

    parser.add_argument(
        "--KEYCLOAK_PASSWORD", "-p",
        required=False,
        type=str,
        default=default_settings.KEYCLOAK_PASSWORD,
        help="Password"
    )

    s = parser.parse_args()

    openid_configuration = requests.get(
        s.KEYCLOAK_URL + '/' + "realms" + '/' + s.KEYCLOAK_REALM + "/.well-known/openid-configuration"
    ).json()
    s.KEYCLOAK_JWKS_URL = openid_configuration["jwks_uri"]
    s.KEYCLOAK_AUTH = openid_configuration["authorization_endpoint"]
    s.KEYCLOAK_TOKEN = openid_configuration["token_endpoint"]

    access_token, decoded_access_token, refresh_token = Auth().get_token()

    print(refresh_token)
    print(access_token)
