#!/usr/bin/env python3
# --coding:utf-8--

from http.client import HTTPSConnection
import os
import uuid
import argparse
import json

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
HOST = "raw.githubusercontent.com"
RESOURCE_PREFIX = "ez2Code/v2ray-initializer/main/resources/docker"
LETS_ENCRYPT_CERT_PATH = "/etc/letsencrypt/live"


def exec_system(command):
    rc = os.system(command)
    if rc != 0:
        raise Exception("fail to execute command:{}".format(command))


def get_resource(resource_name):
    conn = HTTPSConnection(HOST, timeout=30)
    conn.request("GET", "/{}/{}".format(RESOURCE_PREFIX, resource_name))
    return "".join([x.decode("utf-8") for x in conn.getresponse().readlines()])


def install_docker():
    if os.system("which docker") == 0:
        return
    exec_system("apt-get update")
    exec_system("apt-get install -y ca-certificates curl gnupg lsb-release")
    exec_system("curl -fsSL https://download.docker.com/linux/debian/gpg | "
                "sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg")
    exec_system('echo "deb [arch=$(dpkg --print-architecture) '
                'signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] '
                'https://download.docker.com/linux/debian $(lsb_release -cs) stable" | '
                'tee /etc/apt/sources.list.d/docker.list > /dev/null')
    exec_system("apt-get update")
    exec_system("apt-get install -y docker-ce docker-ce-cli containerd.io")


def install_certbot():
    if os.system("which certbot") == 0:
        return
    exec_system("apt-get install snapd")
    exec_system("snap install core")
    exec_system("snap install --classic certbot")
    exec_system("ln -s /snap/bin/certbot /usr/bin/certbot")


def do_check_certs(domain):
    cert_path = "{}/{}/fullchain.pem".format(LETS_ENCRYPT_CERT_PATH, domain)
    key_path = "{}/{}/privkey.pem".format(LETS_ENCRYPT_CERT_PATH, domain)
    if not os.path.exists(cert_path):
        raise Exception("cert not found, please run:certbot certonly --standalone to generate")
    if not os.path.exists(key_path):
        raise Exception("cert key not found, please run:certbot certonly --standalone to generate")


def generate_config():
    config_file = "/etc/v2ray/config.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            config_content = json.loads("\n".join(f.readlines()))
            print("config file exists, your client id:{}".format(config_content.get("inbounds")[0].
                                                                 get("settings").get("clients")[0].get("id")))
            return
    target_uuid = str(uuid.uuid4())
    exec_system("mkdir -p /etc/v2ray")
    content = get_resource("config.json").replace("{client_id}", target_uuid)
    with open(config_file, "w") as f:
        f.write(content)
    print("your client id is:{}".format(target_uuid))


def generate_nginx_config(domain):
    config_file = "/etc/nginx/server.conf"
    if os.path.exists(config_file):
        return
    exec_system("mkdir -p /etc/nginx")
    content = get_resource("server.conf").replace("{your_domain}", domain)
    with open(config_file, "w") as f:
        f.write(content)


def create_docker_app():
    exec_system("docker network create -d bridge web")
    exec_system("docker run -d --name=v2ray --network web --restart=always "
                "-v /etc/v2ray/config.json:/etc/v2ray/config.json v2fly/v2fly-core")
    exec_system("docker run -d --name nginx -v /etc/letsencrypt:/etc/letsencrypt --restart=always "
                "-v /etc/nginx:/etc/nginx/conf.d --network web -p 80:80 -p 443:443 nginx")
    pass


def renew_cert():
    exec_system("docker stop nginx")
    exec_system("certbot renew")
    exec_system("docker start nginx")


if __name__ == "__main__":
    parse = argparse.ArgumentParser()
    parse.add_argument("-d", "--domain", type=str, required=False, help="your domain")
    parse.add_argument("-a", "--action", type=str, required=True, help="action to do")
    args, unknown = parse.parse_known_args()
    if args.action == "init":
        if not args.domain:
            print("you must declare your domain with -d or --domain")
            exit(1)
        install_certbot()
        install_docker()
        do_check_certs(args.domain)
        generate_config()
        generate_nginx_config(args.domain)
        print("init success!")
    elif args.action == "renew":
        renew_cert()
    else:
        print("no correct action specified!")
        exit(1)
