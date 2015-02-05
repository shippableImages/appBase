#!/bin/bash -e

echo "================= Installing core binaries ==================="
apt-get update
apt-get install wget curl texinfo make openssh-server gdb git-core;
apt-get install -y software-properties-common
add-apt-repository ppa:chris-lea/node.js
apt-get update

apt-get install -y nodejs sudo
apt-get install -y openssh-client
npm install -g forever grunt grunt-cli

mkdir -p /root/.ssh
echo "================== Adding empty known hosts file =============="
touch /root/.ssh/known_hosts

echo "================== Disabling scrict host checking for ssh ====="
echo -e "Host * \n\t StrictHostKeyChecking no" > /root/.ssh/config
