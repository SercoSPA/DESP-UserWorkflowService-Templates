from urllib.parse import parse_qs, urlparse
import lxml.html as html
import requests
import json


#### initialisation
# DESP params
DESP_IAM_URL = "https://auth.destine.eu/realms/desp/protocol/openid-connect"
DESP_CLIENT_ID = "highway-public"

# HIGHWAY params
HIGHWAY_REDIRECT_URL = "https://highway.esa.int/sso/auth/realms/highway/broker/DESP_IAM_PROD/endpoint"
HIGHWAY_TOKEN_URL = "https://highway.esa.int/sso/auth/realms/highway/protocol/openid-connect/token"
HIGHWAY_CLIENT_ID = "highway-public"
AUDIENCE = "highway-public"

#### DESP connection

get_params = {
    "client_id": HIGHWAY_CLIENT_ID,
    "redirect_uri": HIGHWAY_REDIRECT_URL,
    "scope": "openid",
    "response_type": "code",
}


def connection_desp(username, password):
    """
    The connection to HIGHWAY for DESP users.

    :param username: the username.
    :param password: the password.
    :return: HIGHWAY authentication token.
    """

    session = requests.Session()

    auth_url = html.fromstring(
        session.get(
            url=DESP_IAM_URL + "/auth",
            params=get_params,
        ).content.decode()
    ).forms[0].action

    # print(f"auth url: {auth_url}")

    post_data = {"username": username, "password": password}
    session_post = session.post(auth_url, data=post_data, allow_redirects=False)

    # get authorization code
    code = parse_qs(
        urlparse(
            session_post.headers["Location"]
        ).query
    )["code"][0]

    # print(f"authorization code: {code}")

    #### DESP token generation

    post_data = {
        "client_id": HIGHWAY_CLIENT_ID,
        "redirect_uri": HIGHWAY_REDIRECT_URL,
        "code": code,
        "grant_type": "authorization_code",
    }

    # get access token
    tokens = session.post(
        DESP_IAM_URL + "/token", data=post_data
    ).json()
    access_token = tokens["access_token"]
    # print(f"access token: {access_token}")

    #### DESP token convert to HIGHWAY token

    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": access_token,
        "subject_issuer": "DESP_IAM_PROD",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "client_id": HIGHWAY_CLIENT_ID,
        "audience": AUDIENCE,
    }

    response = requests.post(HIGHWAY_TOKEN_URL, data=data)
    highway_token = json.loads(response.content)['access_token']

    # print(f"HIGHWAY TOKEN: {highway_token}")
    return highway_token

def direct_connection(username, password):
    """
    The connection for HIGHWAY users.

    :param username: the username.
    :param password: the password.
    :return: HIGHWAY authentication token.
    """
    payload = 'grant_type=password&client_id='
    payload += HIGHWAY_CLIENT_ID
    payload += '&username='
    payload += username
    payload += '&password='
    payload += password
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.request("POST", HIGHWAY_TOKEN_URL, headers=headers, data=payload)

    return json.loads(response.content)['access_token']
