FROM ubuntu:14.04
MAINTAINER Avi "avi@shippable.com"

ENV DEBIAN_FRONTEND noninteractive
RUN dpkg-divert --local --rename --add /sbin/initctl
RUN locale-gen en_US en_US.UTF-8
RUN dpkg-reconfigure locales
RUN echo "deb http://archive.ubuntu.com/ubuntu trusty main universe restricted multiverse" > /etc/apt/sources.list

# force all apt-get commands with a yes
ADD 90forceyes /etc/apt/apt.conf.d/

RUN echo "================= Installing core binaries ==================="
RUN apt-get update
RUN apt-get install python-dev;

RUN apt-get install wget \
                    curl \
                    texinfo \
                    make \
                    openssh-server \
                    openssh-client \
                    gdb \
                    sudo \
                    git-core \
                    software-properties-common;

RUN apt-get install python-pip \
                    python-software-properties;


RUN echo "================= Installing Node ==================="
RUN add-apt-repository ppa:chris-lea/node.js
RUN apt-get update

RUN apt-get install -y nodejs
RUN npm install -g forever grunt grunt-cli

RUN echo "================== Adding empty known hosts file =============="
RUN mkdir -p /root/.ssh
RUN touch /root/.ssh/known_hosts

RUN echo "================== Disabling scrict host checking for ssh ====="
RUN echo -e "Host * \n\t StrictHostKeyChecking no" > /root/.ssh/config

RUN echo 'ALL ALL=(ALL) NOPASSWD:ALL' | tee -a /etc/sudoers
RUN mkdir -p /home/shippable/
