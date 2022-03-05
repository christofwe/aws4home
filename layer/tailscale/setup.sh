#!/usr/bin/env bash

yum install -y yum-utils
yum-config-manager --add-repo https://pkgs.tailscale.com/stable/amazon-linux/2/tailscale.repo
yum -y install tailscale

mkdir /tmp/{bin,extensions}

cp /usr/bin/curl /tmp/bin/
cp /usr/bin/tailscale /tmp/bin/
cp /usr/sbin/tailscaled /tmp/bin/

cp ./extension1.sh /tmp/extensions/